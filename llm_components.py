"""
llm_components.py — ALL LLM calls. Exactly two functions.

Discipline:
- LLM receives already-classified data from rules_engine.py (task statuses,
  lab flags, condition alerts) and handles LANGUAGE GENERATION only.
- LLM never determines done/overdue/no_data status — that's rules_engine.
- All outputs are JSON-only, no markdown fences. Pattern: few-shot system
  prompt sets the schema, user prompt is raw input, response is parsed directly.
- Uses OpenAI client. Swap model by changing MODEL constant below.
  To use Claude: install anthropic SDK, swap client init — function signatures
  and JSON contracts are identical.
"""

import json
import os
from openai import OpenAI

# Model to use. Swap to "gpt-4o-mini" for faster/cheaper dev runs.
MODEL = os.getenv("LLM_MODEL", "gpt-4o")

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY environment variable not set. "
                "Create a .env file with OPENAI_API_KEY=sk-..."
            )
        _client = OpenAI(api_key=api_key)
    return _client


def _parse_json_response(content: str, function_name: str) -> dict:
    """Strip any accidental markdown fences and parse JSON."""
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1])
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"{function_name}: LLM returned non-JSON response. "
            f"Parse error: {e}. Raw response: {content[:300]}"
        )


# ---------------------------------------------------------------------------
# FUNCTION 1 — Flow A: structure in-visit conversation into named bins
# ---------------------------------------------------------------------------

_INTAKE_SYSTEM_PROMPT = """You are a medical scribe AI. Your only job is to read a raw
doctor-patient conversation and extract structured information into exactly four bins.

Output ONLY a valid JSON object with these exact keys (no markdown, no extra text):
{
  "social_history": {
    "<category_name>": "<extracted value or null if not mentioned>"
  },
  "medical_history": {
    "conditions": ["<condition 1>", "..."],
    "past_surgeries": ["<surgery 1>", "..."],
    "hospitalizations": ["<event 1>", "..."]
  },
  "medications": [
    {"name": "<drug name>", "dose": "<dose or null>", "frequency": "<frequency or null>"}
  ],
  "vaccines": [
    {"name": "<vaccine name>", "date": "<date or 'unknown'>"}
  ]
}

Rules:
- Include only information explicitly stated in the conversation.
- Do not infer, assume, or add clinical interpretations.
- If a category is not mentioned at all, use null for that field.
- Empty arrays [] are fine if nothing was mentioned in that category.
- social_history keys come from the category_hints list provided by the caller.

Example input:
"Doctor: Do you smoke? Patient: I quit about 5 years ago. Doctor: Any alcohol? Patient: Maybe a beer on weekends. Doctor: Are you on any medications? Patient: Just lisinopril 10mg once a day."

Example output:
{"social_history": {"smoking": "Former smoker, quit approximately 5 years ago", "alcohol_use": "Occasional, approximately 1 drink per week"}, "medical_history": {"conditions": [], "past_surgeries": [], "hospitalizations": []}, "medications": [{"name": "lisinopril", "dose": "10mg", "frequency": "once daily"}], "vaccines": []}"""


def transcribe_and_structure_intake(
    conversation_text: str,
    category_hints: list[str],
) -> dict:
    """
    Flow A — structure raw in-visit conversation into named EMR bins.

    Args:
        conversation_text: raw transcribed conversation (doctor + patient)
        category_hints: list of social history categories to extract
                        (from SOCIAL_HISTORY_CATEGORIES config)

    Returns:
        {
          "social_history": {"<category>": "<value>", ...},
          "medical_history": {"conditions": [...], "past_surgeries": [...], "hospitalizations": [...]},
          "medications": [{"name": ..., "dose": ..., "frequency": ...}],
          "vaccines": [{"name": ..., "date": ...}]
        }

    JSON-only output, no markdown fences. Modeled on parse_symptoms pattern.
    """
    user_prompt = (
        f"Social history categories to extract: {json.dumps(category_hints)}\n\n"
        f"Conversation transcript:\n{conversation_text}"
    )

    client = _get_client()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _INTAKE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,  # deterministic structuring task
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    return _parse_json_response(content, "transcribe_and_structure_intake")


# ---------------------------------------------------------------------------
# FUNCTION 2 — Flow B step 7: dual chart/patient output from visit notes
# ---------------------------------------------------------------------------

_DUAL_NOTE_SYSTEM_PROMPT = """You are a medical documentation AI. Given visit notes written by a GP,
produce TWO outputs from the same notes — one for the permanent medical record, one for the patient.

Output ONLY a valid JSON object with exactly these two keys (no markdown, no extra text):
{
  "chart_entry": "<technical clinical language for the permanent record>",
  "patient_summary": "<plain language checklist for the patient>"
}

Rules for chart_entry:
- Use proper clinical/medical language appropriate for a permanent medical record.
- Include: presenting complaint, relevant findings, assessment, plan, medications adjusted, follow-up instructions.
- Write in third person (e.g. "Patient presents with...").
- Include specific values, dosages, and dates where provided in the notes.

Rules for patient_summary:
- Use plain, friendly language a patient can understand without medical training.
- Structure as a checklist with checkboxes [ ] for each action the patient must take.
- Include: brief summary of what was discussed, list of tasks with due dates if mentioned, follow-up request.
- End with exactly this sentence: "Your care team will review this with you at your next visit."
- Address the patient by name using the patient_name field provided.

Example output structure:
{
  "chart_entry": "Patient presents for routine diabetes follow-up. HbA1c 7.8% (above target of 7.0%). Blood pressure 134/86 mmHg. Current medications include Metformin 500mg BID. Plan: increase Metformin to 1000mg BID, repeat HbA1c in 3 months, refer to dietitian.",
  "patient_summary": "Hi [Name],\\n\\nHere's a summary from today's visit:\\n\\nYour blood sugar (HbA1c) was 7.8% — we're aiming for below 7.0%.\\n\\nYour tasks before the next visit:\\n[ ] Increase your Metformin to 1000mg twice daily, starting today\\n[ ] Book a follow-up lab test for HbA1c in 3 months\\n[ ] See a dietitian — your GP will send a referral\\n\\nYour care team will review this with you at your next visit."
}"""


def generate_dual_output_note(
    visit_notes_text: str,
    patient_context: dict,
) -> dict:
    """
    Flow B step 7 — ONE prompt, ONE call, TWO keys in the response.

    This is intentionally a single generation step with two rendering targets.
    Do NOT split into two separate prompts — they would drift out of sync.

    Args:
        visit_notes_text: raw visit notes entered by the doctor
        patient_context: dict with at minimum {"name": str, "condition": str}
                         (used for personalization — patient name, condition label)

    Returns:
        {
          "chart_entry": "<technical language for chart>",
          "patient_summary": "<plain language checklist + follow-up ask>"
        }

    JSON-only output, no markdown fences.
    """
    patient_name = patient_context.get("name", "Patient")
    condition = patient_context.get("condition", "chronic condition")

    user_prompt = (
        f"Patient name: {patient_name}\n"
        f"Primary condition: {condition}\n\n"
        f"Visit notes:\n{visit_notes_text}"
    )

    client = _get_client()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _DUAL_NOTE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,  # slight creativity for natural patient-facing language
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    result = _parse_json_response(content, "generate_dual_output_note")

    # Validate both required keys are present
    if "chart_entry" not in result or "patient_summary" not in result:
        raise ValueError(
            f"generate_dual_output_note: missing required keys. "
            f"Got keys: {list(result.keys())}"
        )

    return result
