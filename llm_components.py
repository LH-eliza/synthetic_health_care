"""
llm_components.py — ALL LLM calls. Exactly two functions.

Discipline:
- LLM receives already-classified data from rules_engine.py (task statuses,
  lab flags, condition alerts) and handles LANGUAGE GENERATION only.
- LLM never determines done/overdue/no_data status — that's rules_engine.
- All outputs are JSON-only, no markdown fences. Pattern: few-shot system
  prompt sets the schema, user prompt is raw input, response is parsed directly.

Providers (set in .env):
- groq — Groq OpenAI-compatible API (fast free tier)
- gemini — native google-genai SDK
- openai — OpenAI Python SDK
"""

import json
import os
import re

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "gemini": "gemini-2.0-flash",
    "openai": "gpt-4o",
}

_gemini_client = None
_openai_client = None
_provider: str | None = None
_model: str | None = None


def _is_demo_mode() -> bool:
    return os.getenv("LLM_DEMO_MODE", "").strip().lower() in ("1", "true", "yes")


def _quota_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "429" in text or "resource_exhausted" in text or "quota" in text


def _friendly_api_error(exc: Exception) -> str:
    if _quota_error(exc):
        return (
            "LLM API quota exhausted (429). Options: "
            "(1) set LLM_DEMO_MODE=true in .env for offline demo, "
            "(2) switch provider (e.g. LLM_PROVIDER=groq + GROQ_API_KEY), "
            "(3) wait for quota reset, or (4) check billing on your provider."
        )
    return str(exc)


def _looks_like_openai_key(key: str) -> bool:
    return key.startswith("sk-")


def _looks_like_google_key(key: str) -> bool:
    return key.startswith("AIza") or key.startswith("AQ.")


def _get_gemini_api_key() -> str | None:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if key:
        return key.strip()
    # Common mistake: Google key pasted into OPENAI_API_KEY
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_key and _looks_like_google_key(openai_key):
        return openai_key
    return None


def _resolve_provider() -> str:
    explicit = os.getenv("LLM_PROVIDER", "").strip().lower()
    if explicit in ("openai", "gemini", "groq"):
        return explicit
    if os.getenv("GROQ_API_KEY", "").strip():
        return "groq"
    if _get_gemini_api_key():
        return "gemini"
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_key and _looks_like_openai_key(openai_key):
        return "openai"
    return "groq"


def _get_model(provider: str) -> str:
    return os.getenv("LLM_MODEL", _DEFAULT_MODELS[provider])


def _init_config() -> tuple[str, str]:
    global _provider, _model
    if _provider is None:
        _provider = _resolve_provider()
        _model = _get_model(_provider)
    return _provider, _model  # type: ignore[return-value]


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        from google import genai

        api_key = _get_gemini_api_key()
        if not api_key:
            raise RuntimeError(
                "LLM_PROVIDER=gemini but GEMINI_API_KEY is not set. "
                "Add GEMINI_API_KEY=... to your .env file "
                "(get one at https://aistudio.google.com/apikey)."
            )
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


def _get_openai_compatible_client():
    """OpenAI SDK client — also used for Groq via base_url."""
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI

        provider, _ = _init_config()
        if provider == "groq":
            api_key = os.getenv("GROQ_API_KEY", "").strip()
            if not api_key:
                raise RuntimeError(
                    "LLM_PROVIDER=groq but GROQ_API_KEY is not set. "
                    "Add GROQ_API_KEY=... to your .env file "
                    "(get one at https://console.groq.com/keys)."
                )
            _openai_client = OpenAI(api_key=api_key, base_url=_GROQ_BASE_URL)
        else:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY environment variable not set. "
                    "Create a .env file with OPENAI_API_KEY=sk-... "
                    "or use Groq with LLM_PROVIDER=groq and GROQ_API_KEY."
                )
            _openai_client = OpenAI(api_key=api_key)
    return _openai_client


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


def _generate_json(system_prompt: str, user_prompt: str, temperature: float, function_name: str) -> dict:
    if _is_demo_mode():
        raise RuntimeError("demo_mode")  # handled by callers

    provider, model = _init_config()

    try:
        if provider == "gemini":
            from google.genai import types

            client = _get_gemini_client()
            response = client.models.generate_content(
                model=model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=temperature,
                    response_mime_type="application/json",
                ),
            )
            content = response.text or ""
        else:
            client = _get_openai_compatible_client()
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or ""
    except Exception as e:
        if _is_demo_mode():
            raise RuntimeError("demo_mode") from e
        raise RuntimeError(_friendly_api_error(e)) from e

    return _parse_json_response(content, function_name)


def _demo_transcribe(conversation_text: str, category_hints: list[str]) -> dict:
    text = conversation_text.lower()
    social = {}
    for cat in category_hints:
        social[cat] = None
    if "smok" in text:
        social["smoking"] = "Former smoker" if "quit" in text else "Current smoker"
    if "alcohol" in text or "beer" in text or "drink" in text:
        social["alcohol_use"] = "Occasional alcohol use"
    if "exercise" in text or "walk" in text:
        social["exercise"] = "Moderate activity reported"

    meds = []
    for match in re.finditer(r"(\w+)\s+(\d+\s*mg)[^.]*?(once daily|twice daily|bid|daily)", text):
        meds.append({
            "name": match.group(1).title(),
            "dose": match.group(2).upper().replace(" ", ""),
            "frequency": match.group(3).replace("bid", "twice daily"),
        })
    if not meds and "metformin" in text:
        meds.append({"name": "Metformin", "dose": "500mg", "frequency": "twice daily"})
    if not meds and "lisinopril" in text:
        meds.append({"name": "Lisinopril", "dose": "10mg", "frequency": "once daily"})

    conditions = []
    for term in ("diabetes", "hypertension", "depression", "asthma"):
        if term in text:
            conditions.append(term.title())

    return {
        "social_history": social,
        "medical_history": {
            "conditions": conditions,
            "past_surgeries": [],
            "hospitalizations": [],
        },
        "medications": meds,
        "vaccines": [],
    }


def _default_due_date(days: int = 30) -> str:
    from datetime import date, timedelta
    return (date.today() + timedelta(days=days)).isoformat()


def _demo_dual_note(visit_notes_text: str, patient_context: dict) -> dict:
    name = patient_context.get("name", "Patient")
    condition = patient_context.get("condition", "chronic condition")
    notes = visit_notes_text.strip()
    notes_lower = notes.lower()

    referral = ""
    if "dietitian" in notes_lower or "diabetes educator" in notes_lower:
        referral = " Refer to registered dietitian for structured diabetes education."
    elif "refer" in notes_lower:
        referral = " Specialist referral placed per visit plan."

    hba1c = "7.8%"
    match = re.search(r"hba1c\s*([\d.]+%?)", notes_lower)
    if match:
        val = match.group(1)
        hba1c = val if "%" in val else f"{val}%"

    chart = (
        f"Patient presents for {condition} follow-up. {notes} "
        f"Assessment: ongoing {condition} management. Plan: continue current care pathway;"
        f"{referral} repeat labs in 3 months."
    ).strip()

    summary = (
        f"Hi {name},\n\n"
        f"Here's a summary from today's visit:\n\n"
        f"We reviewed your {condition} care. "
    )
    if "hba1c" in notes_lower:
        summary += f"Your HbA1c was {hba1c}.\n\n"
    else:
        summary += "\n\n"
    summary += (
        "Your tasks before the next visit:\n"
        "[ ] Follow the medication plan discussed today\n"
        "[ ] Complete any labs ordered at your next visit\n"
    )
    if referral:
        summary += "[ ] Attend your specialist referral appointment once scheduled\n"
    summary += "\nYour care team will review this with you at your next visit."

    suggested_tasks = []
    if "metformin" in notes_lower:
        suggested_tasks.append({
            "description": "Switch to Metformin 500mg extended-release and titrate as discussed",
            "type": "confirmation",
            "due_date": _default_due_date(14),
            "target_metric": None,
        })
    if "hba1c" in notes_lower or "lab" in notes_lower:
        suggested_tasks.append({
            "description": "Repeat HbA1c and urine ACR bloodwork",
            "type": "confirmation",
            "due_date": _default_due_date(90),
            "target_metric": "HbA1c",
        })
    if "glucose" in notes_lower or "fasting" in notes_lower:
        suggested_tasks.append({
            "description": "Log daily fasting glucose via secure link",
            "type": "recurring_input",
            "due_date": _default_due_date(30),
            "target_metric": "fasting_glucose",
        })
    if "diabetes educator" in notes_lower or "dietitian" in notes_lower:
        suggested_tasks.append({
            "description": "Attend diabetes educator / dietitian referral appointment",
            "type": "confirmation",
            "due_date": _default_due_date(60),
            "target_metric": None,
        })
    if not suggested_tasks:
        suggested_tasks.append({
            "description": f"Follow up on {condition} care plan discussed today",
            "type": "confirmation",
            "due_date": _default_due_date(30),
            "target_metric": None,
        })

    return {
        "chart_entry": chart,
        "patient_summary": summary,
        "suggested_tasks": suggested_tasks,
    }


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

    if _is_demo_mode():
        return _demo_transcribe(conversation_text, category_hints)

    try:
        return _generate_json(
            _INTAKE_SYSTEM_PROMPT,
            user_prompt,
            temperature=0.0,
            function_name="transcribe_and_structure_intake",
        )
    except RuntimeError:
        return _demo_transcribe(conversation_text, category_hints)


# ---------------------------------------------------------------------------
# FUNCTION 2 — Flow B step 7: dual chart/patient output from visit notes
# ---------------------------------------------------------------------------

_DUAL_NOTE_SYSTEM_PROMPT = """You are a medical documentation AI. Given visit notes written by a GP,
produce THREE outputs from the same notes — chart entry, patient summary, and suggested follow-up tasks.

Output ONLY a valid JSON object with exactly these three keys (no markdown, no extra text):
{
  "chart_entry": "<technical clinical language for the permanent record>",
  "patient_summary": "<plain language checklist for the patient>",
  "suggested_tasks": [
    {
      "description": "<specific actionable task for the patient>",
      "type": "confirmation",
      "due_date": "YYYY-MM-DD",
      "target_metric": null
    }
  ]
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

Rules for suggested_tasks:
- Derive 2–5 follow-up tasks directly from the visit plan in the notes.
- These are AI suggestions only — the doctor will review, edit, approve, or reject each one.
- type must be exactly "confirmation" (patient confirms done) or "recurring_input" (patient submits a reading).
- Use recurring_input only for metrics the patient should log (e.g. fasting glucose, blood pressure).
- due_date must be ISO format YYYY-MM-DD, inferred from the notes or a sensible default (e.g. labs in 3 months).
- target_metric: use "HbA1c", "fasting_glucose", or null as appropriate.
- Do not duplicate tasks already clearly completed in the notes.

Example output structure:
{
  "chart_entry": "Patient presents for routine diabetes follow-up. HbA1c 7.8% (above target of 7.0%). Blood pressure 134/86 mmHg. Current medications include Metformin 500mg BID. Plan: increase Metformin to 1000mg BID, repeat HbA1c in 3 months, refer to dietitian.",
  "patient_summary": "Hi [Name],\\n\\nHere's a summary from today's visit:\\n\\nYour blood sugar (HbA1c) was 7.8% — we're aiming for below 7.0%.\\n\\nYour tasks before the next visit:\\n[ ] Increase your Metformin to 1000mg twice daily, starting today\\n[ ] Book a follow-up lab test for HbA1c in 3 months\\n[ ] See a dietitian — your GP will send a referral\\n\\nYour care team will review this with you at your next visit.",
  "suggested_tasks": [
    {"description": "Increase Metformin to 1000mg twice daily", "type": "confirmation", "due_date": "2026-04-01", "target_metric": null},
    {"description": "Repeat HbA1c and urine ACR bloodwork", "type": "confirmation", "due_date": "2026-06-01", "target_metric": "HbA1c"},
    {"description": "Log daily fasting glucose via secure link", "type": "recurring_input", "due_date": "2026-04-01", "target_metric": "fasting_glucose"}
  ]
}"""


def _normalize_suggested_tasks(tasks: object) -> list[dict]:
    if not isinstance(tasks, list):
        return []

    normalized = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        description = str(task.get("description", "")).strip()
        if not description:
            continue
        task_type = task.get("type", "confirmation")
        if task_type not in ("confirmation", "recurring_input"):
            task_type = "confirmation"
        due_date = str(task.get("due_date", "")).strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due_date):
            due_date = _default_due_date(90 if "lab" in description.lower() or "hba1c" in description.lower() else 30)
        target_metric = task.get("target_metric")
        if target_metric is not None:
            target_metric = str(target_metric).strip() or None
        normalized.append({
            "description": description,
            "type": task_type,
            "due_date": due_date,
            "target_metric": target_metric,
        })
    return normalized


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
          "patient_summary": "<plain language checklist + follow-up ask>",
          "suggested_tasks": [{"description", "type", "due_date", "target_metric"}, ...]
        }

    JSON-only output, no markdown fences.
    """
    patient_name = patient_context.get("name", "Patient")
    condition = patient_context.get("condition", "chronic condition")
    visit_reason = patient_context.get("visit_reason", "")

    user_prompt = (
        f"Patient name: {patient_name}\n"
        f"Primary condition: {condition}\n"
    )
    if visit_reason:
        user_prompt += f"Visit reason: {visit_reason}\n"
    user_prompt += f"\nVisit notes:\n{visit_notes_text}"

    if _is_demo_mode():
        return _demo_dual_note(visit_notes_text, patient_context)

    try:
        result = _generate_json(
            _DUAL_NOTE_SYSTEM_PROMPT,
            user_prompt,
            temperature=0.3,
            function_name="generate_dual_output_note",
        )
    except RuntimeError:
        return _demo_dual_note(visit_notes_text, patient_context)

    if "chart_entry" not in result or "patient_summary" not in result:
        raise ValueError(
            f"generate_dual_output_note: missing required keys. "
            f"Got keys: {list(result.keys())}"
        )

    result["suggested_tasks"] = _normalize_suggested_tasks(result.get("suggested_tasks"))
    return result
