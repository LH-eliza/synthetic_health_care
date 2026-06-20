import json
import os
import sys
from datetime import date
from rules_engine import build_pre_visit_dashboard, print_dashboard
from llm_components import generate_visit_report, transcribe_and_structure_intake

PATIENTS_FILE = os.path.join(os.path.dirname(__file__), "patients.json")

def load_patients() -> dict:
    with open(PATIENTS_FILE, "r") as f:
        return json.load(f)

def save_patients(data: dict) -> None:
    with open(PATIENTS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def read_multiline_input(prompt: str) -> str:
    print(prompt)
    print("(Paste your notes. Press Enter on an empty line, then Ctrl-D / Ctrl-Z on Windows to finish.)\n")
    lines = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass
    return "\n".join(lines).strip()

def print_section(title: str) -> None:
    print("\n" + "-" * 60)
    print(f"  {title}")
    print("-" * 60)

def print_ai_report(report: dict) -> None:
    if "error" in report:
        print("\n[!] Model output could not be parsed as JSON. Raw output:")
        print(report["raw_output"])
        return

    print_section("AI-GENERATED VISIT REPORT (draft — doctor must confirm)")

    print(f"\nWorking diagnosis (AI read of your notes): {report.get('working_diagnosis', '')}")
    if report.get("red_flags_noted"):
        print(f"\n⚠ Red flags noted in your input: {', '.join(report['red_flags_noted'])}")

    print("\n[CHART ENTRY — technical, for the permanent record]")
    print(report.get("chart_entry", ""))

    print("\n[PATIENT SUMMARY — plain language, for the secure link]")
    print(report.get("patient_summary", ""))

    if report.get("lab_or_monitoring_requests"):
        print("\n[SUGGESTED LABS / MONITORING — review before ordering]")
        for item in report["lab_or_monitoring_requests"]:
            print(f"  - {item.get('test_or_metric')}: {item.get('reason')}")

    if report.get("follow_up_tasks"):
        print("\n[SUGGESTED FOLLOW-UP TASKS — these seed next visit's dashboard]")
        for t in report["follow_up_tasks"]:
            print(f"  - [{t.get('type')}] {t.get('description')}  (review in ~{t.get('suggested_review_days', 7)}d)")

def confirm(prompt: str) -> bool:
    ans = input(f"{prompt} [y/n]: ").strip().lower()
    return ans == "y"

def demo_flow_a(patient: dict, data: dict):
    print_section(f"FLOW A: NEW PATIENT ({patient['name']})")
    dashboard = build_pre_visit_dashboard(patient)
    print_dashboard(dashboard)
    
    input("Press Enter to start today's encounter...")
    
    doctor_notes = read_multiline_input(
        "\nDoctor/Scribe: paste the conversation with the patient covering Social and Medical history."
    )
    
    if not doctor_notes:
        print("No notes entered, exiting.")
        return
        
    print("\nGenerating AI scribe intake structure...")
    report = transcribe_and_structure_intake(doctor_notes, ["social_history", "medical_history", "medications", "vaccines"])
    
    if "error" in report:
        print("\n[!] Model output could not be parsed as JSON. Raw output:")
        print(report["raw_output"])
        return
        
    print_section("AI-GENERATED INTAKE BINS")
    print(json.dumps(report, indent=2))
    
    print_section("DOCTOR REVIEW")
    if not confirm("\nConfirm these baseline chart bins?"):
        print("Edits would happen here in the full app. Nothing saved. Exiting.")
        return
        
    print("\n✅ Baseline record established.")
    
    # Save base info
    patient["pre_existing_conditions"] = report.get("medical_history", {}).get("summary", "")
    patient["current_medications"] = report.get("medications", [])
    save_patients(data)

def demo_flow_b(patient: dict, data: dict):
    print_section(f"FLOW B: RETURNING PATIENT ({patient['name']})")
    dashboard = build_pre_visit_dashboard(patient)
    print_dashboard(dashboard)

    input("Press Enter to start today's encounter...")

    doctor_notes = read_multiline_input(
        "\nDoctor: paste your raw notes from today's conversation with the patient."
    )

    if not doctor_notes:
        print("No notes entered, exiting.")
        return

    print("\nGenerating AI scribe report...")
    report = generate_visit_report(dashboard, doctor_notes)
    print_ai_report(report)

    if "error" in report:
        return

    print_section("DOCTOR REVIEW")
    if not confirm("\nConfirm this diagnosis and chart entry as final?"):
        print("Edits would happen here in the full app. Nothing saved. Exiting.")
        return

    if confirm("Send the patient summary via the secure link now?"):
        print("\n✅ [SIMULATED] Secure link sent to patient.")
        print("   Patient will see the plain-language summary and can reply")
        print("   to confirm tasks or submit readings (e.g. temp, symptoms).")
    else:
        print("\nSecure link not sent.")

    # Append today's visit so it becomes visit N-1 for next time.
    today_visit = {
        "visit_id": f"v{len(patient['visits']) + 1}",
        "date": str(date.today()),
        "reason": "follow-up — worsening symptoms",
        "vitals": {},
        "chart_entry": report.get("chart_entry", ""),
        "diagnosis": report.get("working_diagnosis", ""),
        "follow_up_tasks": [
            {
                "description": t.get("description"),
                "type": t.get("type"),
                "status": "no_data",
                "due_date": None,
            }
            for t in report.get("follow_up_tasks", [])
        ],
    }
    patient["visits"].append(today_visit)
    save_patients(data)

    print_section("DONE")
    print("Today's visit saved. Next run of this script will show this visit")
    print("as the 'last visit' on the dashboard, closing the loop.")

def main():
    data = load_patients()
    patients = data.get("patients", [])
    
    print("Select a patient flow to demo:")
    print("1) Flow B: Returning patient (John Carter) - Last visit: Flu")
    print("2) Flow A: New patient (Sarah Jenkins) - No chart history")
    choice = input("Enter 1 or 2: ").strip()
    
    if choice == "1":
        demo_flow_b(patients[0], data)
    elif choice == "2":
        demo_flow_a(patients[1], data)
    else:
        print("Invalid choice. Exiting.")

if __name__ == "__main__":
    main()