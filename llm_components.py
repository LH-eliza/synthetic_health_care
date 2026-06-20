import json
import re
import ollama

MODEL = "llama3.1"

def _strip_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()

def transcribe_and_structure_intake(conversation_text: str, category_hints: list) -> dict:
    system_prompt = f"""You are a clinical scribe assistant supporting a family physician.
Your job is to parse a raw conversation with a new patient and structure it into EMR bins.
Return ONLY a JSON object in exactly this shape, with no markdown fences:

{{
  "social_history": {{
    "summary": "<plain text summary of social factors>"
  }},
  "medical_history": {{
    "summary": "<plain text summary of past medical conditions>"
  }},
  "medications": ["<med 1>", "<med 2>"],
  "vaccines": ["<vax 1>", "<vax 2>"]
}}"""

    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": conversation_text}
        ],
        options={"temperature": 0.1}
    )

    raw_text = response['message']['content']
    cleaned = _strip_json_fences(raw_text)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"error": "Could not parse model output as JSON.", "raw_output": raw_text}

def generate_visit_report(dashboard: dict, doctor_notes: str) -> dict:
    system_prompt = """You are a clinical scribe assistant supporting a family physician.
You will be given (1) background context about a patient including their last visit, and (2) the doctor's free-text notes from today's visit.
Your job is ONLY language structuring and generation.
Return ONLY a JSON object, no markdown fences, no preamble, in exactly this shape:

{
  "working_diagnosis": "<string, the doctor's apparent diagnosis from today's notes>",
  "chart_entry": "<technical clinical language, suitable for the permanent record, written in the doctor's voice as if dictated>",
  "patient_summary": "<plain language, no jargon, written as: what happened, what it means, and a short checklist of what the patient should do next>",
  "follow_up_tasks": [
    {"description": "<plain task description>", "type": "confirmation" or "recurring_input", "suggested_review_days": 7}
  ],
  "lab_or_monitoring_requests": [
    {"test_or_metric": "<e.g. CBC, WBC, O2 saturation, average daily temp>", "reason": "<short reason tied to today's notes>"}
  ],
  "red_flags_noted": ["<any explicit red-flag symptoms mentioned in the notes, plain list, empty array if none>"]
}"""

    # Format the prompt context safely
    last_visit_info = ""
    task_diff_info = ""
    
    if dashboard.get("last_visit"):
        lv = dashboard["last_visit"]
        last_visit_info = f"""LAST VISIT:
Date: {lv.get('date')}
Reason: {lv.get('reason')}
Diagnosis given: {lv.get('diagnosis')}
Chart note: {lv.get('summary')}"""

    if dashboard.get("task_diff"):
        task_diff_info = "FOLLOW-UP STATUS SINCE LAST VISIT:\n" + "\n".join('- ' + t.get('reasoning', '') for t in dashboard['task_diff'])

    user_content = f"""PATIENT BACKGROUND (from pre-visit dashboard):
Name: {dashboard.get('name')}, Age/Sex: {dashboard.get('age')}/{dashboard.get('sex')}
Pre-existing conditions: {', '.join(dashboard.get('pre_existing_conditions', [])) or 'none'}
Allergies: {', '.join(dashboard.get('allergies', [])) or 'NKDA'}
Current medications: {', '.join(dashboard.get('current_medications', [])) or 'none'}

{last_visit_info}

{task_diff_info}

---

TODAY'S VISIT -- DOCTOR'S RAW NOTES:
{doctor_notes}
"""

    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        options={"temperature": 0.1}
    )

    raw_text = response['message']['content']
    cleaned = _strip_json_fences(raw_text)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"error": "Could not parse model output as JSON.", "raw_output": raw_text}
