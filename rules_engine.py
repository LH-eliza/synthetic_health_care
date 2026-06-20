from datetime import date

def get_last_visit(patient: dict) -> dict | None:
    visits = patient.get("visits", [])
    if not visits:
        return None
    return visits[-1]

def compute_task_diff(prior_tasks: list[dict], today: date = None) -> list[dict]:
    today = today or date.today()
    results = []
    for task in prior_tasks:
        status = task.get("status", "no_data")
        if status == "done":
            reasoning = f"\"{task['description']}\" — confirmed complete."
        elif status == "overdue":
            reasoning = f"\"{task['description']}\" — expected by {task.get('due_date')}, not received."
        else:
            reasoning = f"\"{task['description']}\" — no response yet, due {task.get('due_date')}."
        results.append({
            "task_description": task["description"],
            "status": status,
            "reasoning": reasoning,
        })
    return results

def build_pre_visit_dashboard(patient: dict) -> dict:
    last_visit = get_last_visit(patient)

    dashboard = {
        "name": patient.get("name", "Unknown"),
        "age": patient.get("age", "Unknown"),
        "sex": patient.get("sex", "Unknown"),
        "pre_existing_conditions": patient.get("pre_existing_conditions", []),
        "allergies": patient.get("allergies", []),
        "current_medications": patient.get("current_medications", []),
        "last_visit": None,
        "task_diff": [],
    }

    if last_visit:
        dashboard["last_visit"] = {
            "date": last_visit.get("date"),
            "reason": last_visit.get("reason"),
            "diagnosis": last_visit.get("diagnosis"),
            "vitals": last_visit.get("vitals", {}),
            "summary": last_visit.get("chart_entry"),
        }
        dashboard["task_diff"] = compute_task_diff(last_visit.get("follow_up_tasks", []))

    return dashboard

def print_dashboard(dashboard: dict) -> None:
    print("\n" + "=" * 60)
    print(f"  PRE-VISIT DASHBOARD — {dashboard['name']}")
    print("=" * 60)
    print(f"Age/Sex: {dashboard['age']} / {dashboard['sex']}")
    print(f"Pre-existing conditions: {', '.join(dashboard['pre_existing_conditions']) or 'none on file'}")
    print(f"Allergies: {', '.join(dashboard['allergies']) or 'NKDA'}")
    print(f"Current medications: {', '.join(dashboard['current_medications']) or 'none on file'}")

    lv = dashboard["last_visit"]
    if lv:
        print(f"\n--- Last visit: {lv['date']} ---")
        print(f"Reason: {lv['reason']}")
        print(f"Diagnosis: {lv['diagnosis']}")
        if lv.get("vitals"):
            v = lv["vitals"]
            print(f"Vitals: temp {v.get('temp_c')}C, HR {v.get('hr')}, BP {v.get('bp')}")
        print(f"Summary: {lv['summary']}")

        print("\n--- Follow-up status (since last visit) ---")
        for t in dashboard["task_diff"]:
            flag = {"done": "[OK]", "overdue": "[!! OVERDUE]", "no_data": "[? NO DATA]"}.get(t["status"], "[?]")
            print(f"  {flag} {t['reasoning']}")
    else:
        print("\nNo chart history exists — this is a new patient.")
    print("=" * 60 + "\n")
