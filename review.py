"""
Interactive Review CLI Runner for Diwas.
Run: python review.py
"""

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).parent / "src"))

from decision import init_decision_store, DEFAULT_STORE_PATH
from review_cli import prepare_review_queue, render_review_card, apply_review_decision


def main():
    store = init_decision_store()
    pending = prepare_review_queue(store)

    print(f"\n=======================================================")
    print(f"  EMAIL-SLM REVIEW CLI — REVIEWER: DIWAS")
    print(f"  Pending Leads Requiring Review: {len(pending)}")
    print(f"=======================================================\n")

    if not pending:
        print("No pending reviews! All 48 leads have been reviewed.")
        print("Run 'python export_dataset.py' to generate artifacts/slm_train.jsonl.")
        return

    for idx, item in enumerate(pending, start=1):
        lead = item["lead"]
        sid = lead["source_id"]
        labels = item["labels"]

        print(f"\n[{idx}/{len(pending)}] " + render_review_card(item))
        print("\nChoose Action: [a]ccept | [r]evise | [j]reject | [u]ncertain | [s]kip | [q]uit")

        try:
            choice = input("Decision > ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nSession paused. Progress saved to artifacts/decisions.json.")
            break

        if choice in {"q", "quit", "exit"}:
            print("Review session ended. Safe to resume anytime.")
            break
        elif choice in {"s", "skip"}:
            print(f"Skipped {sid} for now.")
            continue
        elif choice in {"a", "accept"}:
            notes = input("Optional review notes (press enter to skip): ").strip()
            apply_review_decision(store, sid, "accept", reviewer="Diwas", notes=notes)
            print(f"-> ACCEPTED: {sid}")
        elif choice in {"j", "reject"}:
            reason = input("Rejection reason: ").strip() or "Disqualified lead"
            apply_review_decision(store, sid, "reject", reviewer="Diwas", notes=reason)
            print(f"-> REJECTED: {sid}")
        elif choice in {"u", "uncertain"}:
            notes = input("Uncertainty note: ").strip()
            apply_review_decision(store, sid, "uncertain", reviewer="Diwas", notes=notes)
            print(f"-> MARKED UNCERTAIN: {sid}")
        elif choice in {"r", "revise"}:
            print("\nEditing 4-field taxonomy (press Enter to keep candidate value):")
            new_pain = input(f"Pain Point [{labels['pain_point'][:50]}...]: ").strip() or labels["pain_point"]
            new_angle = input(f"Personalization Angle [{labels['personalization_angle'][:50]}...]: ").strip() or labels["personalization_angle"]
            new_subject = input(f"Subject [{labels['subject']}]: ").strip() or labels["subject"]
            print("Body (enter new body or press Enter to keep current):")
            new_body = input().strip() or labels["body"]

            revised = {
                "pain_point": new_pain,
                "personalization_angle": new_angle,
                "subject": new_subject,
                "body": new_body,
            }
            notes = input("Revision note: ").strip() or "Edited for voice/hook precision"
            apply_review_decision(store, sid, "revise", reviewer="Diwas", notes=notes, revised_labels=revised)
            print(f"-> REVISED: {sid}")
        else:
            print("Unrecognized action, skipping to next lead.")

    print("\nSession saved. Run 'python export_dataset.py' when ready to export.")


if __name__ == "__main__":
    main()

