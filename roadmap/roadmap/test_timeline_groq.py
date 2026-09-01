"""
test_timeline_groq.py

Standalone real-Groq end-to-end test for timeline.py.

Runs the FULL pipeline with actual network calls to Groq (not stubs):

    adapter (inline profile) -> level_rules -> retrieval -> planner (Groq)
        -> timeline (Groq)

Run it from inside the `roadmap` folder:

    python test_timeline_groq.py

What to look for:
    - PLAN SOURCE:     should print "groq"     (planner.py used the real model)
    - TIMELINE SOURCE: should print "groq"     (timeline.py used the real model)

If either prints "deterministic_fallback" instead, the script prints the
exact "_fallback_reason" so you know exactly why the model call failed
(missing key, network error, invalid JSON, validation failure, etc.)
without needing to dig through a traceback.
"""

import json

from retrieval import load_resources
from planner import plan_from_profile
from timeline import generate_timeline


def main() -> None:

    print("=" * 70)
    print("MINERVA — REAL GROQ END-TO-END TEST (planner + timeline)")
    print("=" * 70)

    resources = load_resources()

    # A realistic multi-skill profile so both planner.py and timeline.py
    # have enough to actually exercise phase ordering, dependencies, and
    # multi-week resource distribution — not just a single trivial skill.
    profile = {
        "journey": "career-in-mind",
        "career": "development",
        "target_role": None,
        "current_experience_level": None,
        "goal": "Become job-ready as a Developer",
        "weekly_hours": None,
        "skills": [
            {
                "skill_id": "python",
                "current_level": 1,
                "target_level": 3,
                "gap": 2,
                "gap_label": "Moderate Gap",
                "priority": "Critical",
                "category": "core",
                "weight": 1.0,
                "confidence": 0.75,
                "evidence_status": "measured",
            },
            {
                "skill_id": "git",
                "current_level": 1,
                "target_level": 2,
                "gap": 1,
                "gap_label": "Low Gap",
                "priority": "Medium",
                "category": "tool",
                "weight": 0.6,
                "confidence": 0.75,
                "evidence_status": "measured",
            },
        ],
        "strengths": [],
        "weak_areas": [],
        "preferences": {},
    }

    hours_per_week = 8

    # ------------------------------------------------------------------
    # STEP 1 — planner.py, real Groq call
    # ------------------------------------------------------------------

    print("\n--- STEP 1: planner.py (real Groq call) ---\n")

    plan = plan_from_profile(profile, resources=resources, use_model=True)

    print("PLAN SOURCE:", plan["_source"])

    if plan["_source"] != "groq":
        print("PLAN FALLBACK REASON:", plan.get("_fallback_reason"))

    print(f"Phases: {len(plan.get('phases', []))}")
    for phase in plan.get("phases", []):
        print(f"  Phase {phase.get('phase')}: {phase.get('title')} "
              f"({len(phase.get('resources', []))} resources)")

    if not plan.get("phases"):
        print("\nNo phases were generated (empty plan) — nothing to schedule. Stopping.")
        return

    # ------------------------------------------------------------------
    # STEP 2 — timeline.py, real Groq call
    # ------------------------------------------------------------------

    print(f"\n--- STEP 2: timeline.py (real Groq call, {hours_per_week} hrs/week) ---\n")

    timeline = generate_timeline(
        plan,
        hours_per_week=hours_per_week,
        resources=resources,
        use_model=True,
    )

    print("TIMELINE SOURCE:", timeline["_source"])

    if timeline["_source"] != "groq":
        print("TIMELINE FALLBACK REASON:", timeline.get("_fallback_reason"))

    print(f"Total duration: {timeline.get('total_duration_weeks')} weeks")
    print(f"Total estimated hours: {timeline.get('total_estimated_hours')}")

    # ------------------------------------------------------------------
    # STEP 3 — sanity summary + full JSON dump
    # ------------------------------------------------------------------

    print("\n--- WEEK-BY-WEEK SUMMARY ---\n")

    for week in timeline.get("weeks", []):
        focus = ", ".join(week.get("focus", []))
        print(
            f"Week {week['week']:>2}: {week['estimated_hours']:>5} hrs | "
            f"{focus:<20} | {week.get('milestone', '')}"
        )

    print("\n--- FULL TIMELINE JSON ---\n")
    print(json.dumps(timeline, indent=2))

    print("\n" + "=" * 70)
    if plan["_source"] == "groq" and timeline["_source"] == "groq":
        print("RESULT: FULL PIPELINE RAN ON REAL GROQ — PRODUCTION READY")
    else:
        print("RESULT: ONE OR BOTH STAGES FELL BACK TO DETERMINISTIC MODE")
        print("(Pipeline still works and did not crash — check the reasons above.)")
    print("=" * 70)


if __name__ == "__main__":
    main()