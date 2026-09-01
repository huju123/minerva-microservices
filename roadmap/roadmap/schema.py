"""
MINERVA — Personalized Roadmap RAG
schema.py

Purpose:
    Define the ONE strict, canonical structure for a complete
    PERSONALIZED ROADMAP — the combination of planner.py's Learning Plan
    (WHAT + ORDER) and timeline.py's Timeline (WHEN + HOW LONG) — and
    provide the single place that assembles and structurally validates
    that combined object.

Architecture boundary:
    adapter.py      -> common profile
    level_rules.py   -> learner state / suitable resource levels
    retrieval.py     -> WHICH real resources match those rules
    planner.py       -> WHAT + ORDER learning plan
    timeline.py       -> WHEN + HOW LONG
    schema.py          -> Complete roadmap's strict structured format (this file)
    validator.py       -> deep/semantic validation of the assembled roadmap (future)
    roadmap_engine.py  -> wires the whole pipeline together (future)

IMPORTANT ARCHITECTURE RULES:
    - schema.py does NOT calculate skill gaps, retrieve resources, plan
      WHAT to learn, or schedule WHEN to learn it. Those are already
      done by adapter.py / level_rules.py / retrieval.py / planner.py /
      timeline.py respectively.
    - schema.py does NOT re-run planner.py's or timeline.py's own
      grounding/hallucination/ordering checks (validate_plan_structure,
      validate_timeline_structure) — those already ran and already
      passed before a plan/timeline reaches this file. schema.py only
      checks STRUCTURE (required keys present, correct types, internally
      self-consistent counts) — deep semantic/business-rule validation
      of the fully assembled roadmap belongs to validator.py.
    - schema.py does NOT invent fields. Every field in the canonical
      roadmap comes directly from planner.py's plan or timeline.py's
      timeline; nothing is fabricated here.
    - The canonical shape reuses planner.py's and timeline.py's own
      required-key constants (imported, not redefined) so the schema
      can never silently drift out of sync with what those two files
      actually produce.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .planner import REQUIRED_PHASE_KEYS as PLAN_REQUIRED_PHASE_KEYS
from .timeline import REQUIRED_WEEK_KEYS as TIMELINE_REQUIRED_WEEK_KEYS


# ============================================================================
# CONFIGURATION
# ============================================================================

REQUIRED_ROADMAP_KEYS = {
    "career",
    "goal",
    "starting_level",
    "target_level",
    "learning_objectives",
    "phases",
    "certifications",
    "job_preparation",
    "recommended_jobs",
    "timeline",
    "meta",
}

REQUIRED_LEARNING_OBJECTIVE_KEYS = {"skill", "priority"}

REQUIRED_TIMELINE_SECTION_KEYS = {
    "total_duration_weeks",
    "hours_per_week",
    "total_estimated_hours",
    "weeks",
}

REQUIRED_META_KEYS = {"plan_source", "timeline_source"}

# The exact set of "_source" values planner.py / timeline.py are allowed
# to stamp onto their output. Kept here (not imported) because planner.py
# and timeline.py don't currently expose this as a named constant — if
# they ever do, this should be switched to an import for the same
# drift-proofing reason as the phase/week key imports above.
VALID_SOURCE_VALUES = {"groq", "deterministic", "deterministic_fallback", "empty"}


# ============================================================================
# ERRORS
# ============================================================================

class SchemaError(Exception):
    """Base error for schema.py."""


class SchemaValidationError(SchemaError):
    """
    Raised when a roadmap object does not conform to the canonical
    PERSONALIZED ROADMAP structure — missing keys, wrong types, or
    internally inconsistent counts (e.g. total_duration_weeks not
    matching the number of week entries).
    """


# ============================================================================
# STEP 1 — BUILD THE CANONICAL ROADMAP (deterministic assembly, no model)
# ============================================================================

def build_final_roadmap(
    plan: Dict[str, Any],
    timeline: Dict[str, Any],
    profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Combine planner.py's plan dict + timeline.py's timeline dict into ONE
    canonical roadmap dict matching REQUIRED_ROADMAP_KEYS.

    This is pure assembly — every value is copied straight from `plan` or
    `timeline` (or, for "career", from the optional `profile`, since
    planner.py's returned plan dict does not itself carry a "career"
    field). Nothing is computed, inferred, or invented here.

    `plan` is expected to be the dict returned by
    planner.plan_from_profile() (or an equivalent hand-built dict with
    the same shape). `timeline` is expected to be the dict returned by
    timeline.generate_timeline() for that same plan.
    """

    if not isinstance(plan, dict):
        raise TypeError("plan must be a dictionary (planner.py output).")

    if not isinstance(timeline, dict):
        raise TypeError("timeline must be a dictionary (timeline.py output).")

    timeline_section = {
        "total_duration_weeks": timeline.get("total_duration_weeks"),
        "hours_per_week": timeline.get("hours_per_week"),
        "total_estimated_hours": timeline.get("total_estimated_hours"),
        "weeks": timeline.get("weeks", []),
    }

    roadmap = {
        "career": profile.get("career") if isinstance(profile, dict) else None,
        "goal": plan.get("goal"),
        "starting_level": plan.get("starting_level"),
        "target_level": plan.get("target_level"),
        "learning_objectives": plan.get("learning_objectives", []),
        "phases": plan.get("phases", []),
        "certifications": plan.get("certifications", []),
        "job_preparation": plan.get("job_preparation", []),
        "recommended_jobs": plan.get("recommended_jobs", []),
        "timeline": timeline_section,
        "meta": {
            "plan_source": plan.get("_source"),
            "timeline_source": timeline.get("_source"),
            "plan_fallback_reason": plan.get("_fallback_reason"),
            "timeline_fallback_reason": timeline.get("_fallback_reason"),
        },
    }

    return roadmap


# ============================================================================
# STEP 2 — VALIDATE THE CANONICAL ROADMAP (structure only)
# ============================================================================

def _require_type(value: Any, expected_type: Any, field_name: str) -> None:
    if not isinstance(value, expected_type):
        raise SchemaValidationError(
            f"'{field_name}' must be of type {expected_type}, got {type(value)}."
        )


def _validate_learning_objectives(learning_objectives: Any) -> None:

    _require_type(learning_objectives, list, "learning_objectives")

    for index, objective in enumerate(learning_objectives):

        if not isinstance(objective, dict):
            raise SchemaValidationError(
                f"learning_objectives[{index}] must be an object."
            )

        missing = REQUIRED_LEARNING_OBJECTIVE_KEYS - objective.keys()
        if missing:
            raise SchemaValidationError(
                f"learning_objectives[{index}] is missing keys: {sorted(missing)}"
            )

        _require_type(objective["skill"], str, f"learning_objectives[{index}].skill")
        _require_type(objective["priority"], str, f"learning_objectives[{index}].priority")


def _validate_phases(phases: Any) -> None:

    _require_type(phases, list, "phases")

    for index, phase in enumerate(phases):

        if not isinstance(phase, dict):
            raise SchemaValidationError(f"phases[{index}] must be an object.")

        missing = PLAN_REQUIRED_PHASE_KEYS - phase.keys()
        if missing:
            raise SchemaValidationError(
                f"phases[{index}] is missing keys: {sorted(missing)}"
            )

        _require_type(phase["phase"], int, f"phases[{index}].phase")
        _require_type(phase["title"], str, f"phases[{index}].title")
        _require_type(phase["objectives"], list, f"phases[{index}].objectives")
        _require_type(phase["resources"], list, f"phases[{index}].resources")

        for j, item in enumerate(phase["objectives"]):
            _require_type(item, str, f"phases[{index}].objectives[{j}]")

        for j, item in enumerate(phase["resources"]):
            _require_type(item, str, f"phases[{index}].resources[{j}]")


def _validate_resource_id_list(value: Any, field_name: str) -> None:

    _require_type(value, list, field_name)

    for index, item in enumerate(value):
        _require_type(item, str, f"{field_name}[{index}]")


def _validate_timeline_section(timeline_section: Any) -> None:

    _require_type(timeline_section, dict, "timeline")

    missing = REQUIRED_TIMELINE_SECTION_KEYS - timeline_section.keys()
    if missing:
        raise SchemaValidationError(f"'timeline' is missing keys: {sorted(missing)}")

    _require_type(timeline_section["total_duration_weeks"], int, "timeline.total_duration_weeks")
    _require_type(timeline_section["hours_per_week"], (int, float), "timeline.hours_per_week")
    _require_type(
        timeline_section["total_estimated_hours"], (int, float), "timeline.total_estimated_hours"
    )
    _require_type(timeline_section["weeks"], list, "timeline.weeks")

    weeks = timeline_section["weeks"]

    if timeline_section["total_duration_weeks"] != len(weeks):
        raise SchemaValidationError(
            "'timeline.total_duration_weeks' "
            f"({timeline_section['total_duration_weeks']}) does not match the "
            f"number of week entries ({len(weeks)})."
        )

    seen_week_numbers: set = set()

    for index, week in enumerate(weeks):

        if not isinstance(week, dict):
            raise SchemaValidationError(f"timeline.weeks[{index}] must be an object.")

        missing_week_keys = TIMELINE_REQUIRED_WEEK_KEYS - week.keys()
        if missing_week_keys:
            raise SchemaValidationError(
                f"timeline.weeks[{index}] is missing keys: {sorted(missing_week_keys)}"
            )

        _require_type(week["week"], int, f"timeline.weeks[{index}].week")
        _require_type(week["focus"], list, f"timeline.weeks[{index}].focus")
        _require_type(week["resources"], list, f"timeline.weeks[{index}].resources")
        _require_type(
            week["estimated_hours"], (int, float), f"timeline.weeks[{index}].estimated_hours"
        )
        _require_type(week["milestone"], str, f"timeline.weeks[{index}].milestone")

        for j, item in enumerate(week["focus"]):
            _require_type(item, str, f"timeline.weeks[{index}].focus[{j}]")

        for j, item in enumerate(week["resources"]):
            _require_type(item, str, f"timeline.weeks[{index}].resources[{j}]")

        if week["week"] in seen_week_numbers:
            raise SchemaValidationError(
                f"timeline.weeks contains duplicate week number {week['week']}."
            )
        seen_week_numbers.add(week["week"])


def _validate_meta(meta: Any) -> None:

    _require_type(meta, dict, "meta")

    missing = REQUIRED_META_KEYS - meta.keys()
    if missing:
        raise SchemaValidationError(f"'meta' is missing keys: {sorted(missing)}")

    for key in ("plan_source", "timeline_source"):
        value = meta[key]
        if value is not None and value not in VALID_SOURCE_VALUES:
            raise SchemaValidationError(
                f"meta.{key} = {value!r} is not one of {sorted(VALID_SOURCE_VALUES)}."
            )

    for key in ("plan_fallback_reason", "timeline_fallback_reason"):
        # Optional fields: absent is fine (schema.py's own builder always
        # sets them, possibly to None), but if present they must be a
        # string or None — never some other invented type.
        if key in meta and meta[key] is not None:
            _require_type(meta[key], str, f"meta.{key}")


def validate_roadmap_schema(roadmap: Dict[str, Any]) -> None:
    """
    Structural validation ONLY — required keys present, correct types,
    and internally self-consistent counts (e.g. total_duration_weeks
    matching the number of week entries).

    This deliberately does NOT re-check things planner.py's
    validate_plan_structure() and timeline.py's validate_timeline_structure()
    already guaranteed before this roadmap was assembled — no hallucinated
    resource_id checks, no prerequisite-order checks, no cross-referencing
    against resources.json. Those are semantic/business-rule checks that
    belong to validator.py, which validates the fully assembled roadmap
    against the live resource pool. schema.py only enforces SHAPE.

    Raises SchemaValidationError on the first problem found so callers get
    an immediately actionable message.
    """

    if not isinstance(roadmap, dict):
        raise SchemaValidationError("Roadmap must be a JSON object.")

    missing = REQUIRED_ROADMAP_KEYS - roadmap.keys()
    if missing:
        raise SchemaValidationError(f"Roadmap is missing required keys: {sorted(missing)}")

    if roadmap["career"] is not None:
        _require_type(roadmap["career"], str, "career")

    if roadmap["goal"] is not None:
        _require_type(roadmap["goal"], str, "goal")

    if roadmap["starting_level"] is not None:
        _require_type(roadmap["starting_level"], str, "starting_level")

    if roadmap["target_level"] is not None:
        _require_type(roadmap["target_level"], str, "target_level")

    _validate_learning_objectives(roadmap["learning_objectives"])
    _validate_phases(roadmap["phases"])
    _validate_resource_id_list(roadmap["certifications"], "certifications")
    _validate_resource_id_list(roadmap["job_preparation"], "job_preparation")
    _validate_resource_id_list(roadmap["recommended_jobs"], "recommended_jobs")
    _validate_timeline_section(roadmap["timeline"])
    _validate_meta(roadmap["meta"])


# ============================================================================
# STEP 3 — SERIALIZATION HELPERS
# ============================================================================

def to_json(roadmap: Dict[str, Any], indent: int = 2) -> str:
    """Canonical serialization boundary for a validated roadmap."""

    return json.dumps(roadmap, indent=indent)


def from_json(text: str) -> Dict[str, Any]:
    """
    Canonical deserialization boundary. Does NOT validate — callers should
    run validate_roadmap_schema() on the result before trusting it, since
    the text may have come from storage, a network call, or a hand-edited
    file rather than build_final_roadmap().
    """

    parsed = json.loads(text)

    if not isinstance(parsed, dict):
        raise SchemaError("Deserialized roadmap JSON root must be an object.")

    return parsed


# ============================================================================
# STEP 4 — ORCHESTRATION
# ============================================================================

def build_and_validate_roadmap(
    plan: Dict[str, Any],
    timeline: Dict[str, Any],
    profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convenience wrapper: assemble the canonical roadmap from a plan +
    timeline, structurally validate it, and return it. Raises
    SchemaValidationError if the assembled roadmap does not conform —
    this should only ever happen if plan/timeline came from somewhere
    other than planner.py / timeline.py's own functions, since those
    already guarantee shapes this builder relies on.
    """

    roadmap = build_final_roadmap(plan, timeline, profile=profile)
    validate_roadmap_schema(roadmap)
    return roadmap


# ============================================================================
# SELF TEST (deterministic only — no network / no API key required)
# ============================================================================

def run_self_test() -> None:

    print("=" * 70)
    print("MINERVA ROADMAP RAG — SCHEMA SELF TEST")
    print("=" * 70)

    from retrieval import load_resources
    from planner import plan_from_profile
    from timeline import generate_timeline

    resources = load_resources()

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
        ],
        "strengths": [],
        "weak_areas": [],
        "preferences": {},
    }

    plan = plan_from_profile(profile, resources=resources, use_model=False)
    timeline = generate_timeline(plan, hours_per_week=10, resources=resources, use_model=False)

    # ------------------------------------------------------------------
    # 1. Normal assembly + validation of a real plan+timeline pair
    # ------------------------------------------------------------------

    roadmap = build_and_validate_roadmap(plan, timeline, profile=profile)

    assert roadmap["career"] == "development"
    assert roadmap["meta"]["plan_source"] == "deterministic"
    assert roadmap["meta"]["timeline_source"] == "deterministic"
    assert roadmap["timeline"]["total_duration_weeks"] == len(roadmap["timeline"]["weeks"])

    print("build_and_validate_roadmap: PASS")

    # ------------------------------------------------------------------
    # 2. Round-trip through JSON serialization must still validate
    # ------------------------------------------------------------------

    round_tripped = from_json(to_json(roadmap))
    validate_roadmap_schema(round_tripped)

    print("JSON round-trip validation: PASS")

    # ------------------------------------------------------------------
    # 3. Missing top-level key must be rejected
    # ------------------------------------------------------------------

    from copy import deepcopy

    missing_key_roadmap = deepcopy(roadmap)
    del missing_key_roadmap["phases"]

    try:
        validate_roadmap_schema(missing_key_roadmap)
        raise AssertionError("Missing top-level key was not caught.")
    except SchemaValidationError:
        pass

    print("Missing top-level key rejection: PASS")

    # ------------------------------------------------------------------
    # 4. Wrong type must be rejected
    # ------------------------------------------------------------------

    wrong_type_roadmap = deepcopy(roadmap)
    wrong_type_roadmap["phases"] = "not a list"

    try:
        validate_roadmap_schema(wrong_type_roadmap)
        raise AssertionError("Wrong-type field was not caught.")
    except SchemaValidationError:
        pass

    print("Wrong-type field rejection: PASS")

    # ------------------------------------------------------------------
    # 5. Missing phase key must be rejected
    # ------------------------------------------------------------------

    if roadmap["phases"]:
        bad_phase_roadmap = deepcopy(roadmap)
        del bad_phase_roadmap["phases"][0]["title"]

        try:
            validate_roadmap_schema(bad_phase_roadmap)
            raise AssertionError("Missing phase key was not caught.")
        except SchemaValidationError:
            pass

        print("Missing phase key rejection: PASS")

    # ------------------------------------------------------------------
    # 6. total_duration_weeks / week-count mismatch must be rejected
    # ------------------------------------------------------------------

    mismatched_roadmap = deepcopy(roadmap)
    mismatched_roadmap["timeline"]["total_duration_weeks"] += 5

    try:
        validate_roadmap_schema(mismatched_roadmap)
        raise AssertionError("Duration/week-count mismatch was not caught.")
    except SchemaValidationError:
        pass

    print("Duration/week-count mismatch rejection: PASS")

    # ------------------------------------------------------------------
    # 7. Missing week key must be rejected
    # ------------------------------------------------------------------

    if roadmap["timeline"]["weeks"]:
        bad_week_roadmap = deepcopy(roadmap)
        del bad_week_roadmap["timeline"]["weeks"][0]["milestone"]

        try:
            validate_roadmap_schema(bad_week_roadmap)
            raise AssertionError("Missing week key was not caught.")
        except SchemaValidationError:
            pass

        print("Missing week key rejection: PASS")

    # ------------------------------------------------------------------
    # 8. Invalid meta.plan_source value must be rejected
    # ------------------------------------------------------------------

    bad_meta_roadmap = deepcopy(roadmap)
    bad_meta_roadmap["meta"]["plan_source"] = "made_up_source"

    try:
        validate_roadmap_schema(bad_meta_roadmap)
        raise AssertionError("Invalid meta.plan_source value was not caught.")
    except SchemaValidationError:
        pass

    print("Invalid meta.plan_source rejection: PASS")

    # ------------------------------------------------------------------
    # 9. Duplicate week number must be rejected
    # ------------------------------------------------------------------

    if len(roadmap["timeline"]["weeks"]) >= 2:
        dup_week_roadmap = deepcopy(roadmap)
        dup_week_roadmap["timeline"]["weeks"][1]["week"] = (
            dup_week_roadmap["timeline"]["weeks"][0]["week"]
        )
        # total_duration_weeks would now legitimately mismatch too, but we
        # want to isolate the duplicate-week-number check specifically, so
        # bump total_duration_weeks down by one to keep that check passing
        # and force validation to fail on the duplicate instead.
        dup_week_roadmap["timeline"]["total_duration_weeks"] = len(
            dup_week_roadmap["timeline"]["weeks"]
        )

        try:
            validate_roadmap_schema(dup_week_roadmap)
            raise AssertionError("Duplicate week number was not caught.")
        except SchemaValidationError:
            pass

        print("Duplicate week number rejection: PASS")

    # ------------------------------------------------------------------
    # 10. Empty plan + empty timeline must still assemble to a valid,
    #     schema-conforming (just empty) roadmap.
    # ------------------------------------------------------------------

    empty_plan = {
        "goal": None,
        "starting_level": None,
        "target_level": None,
        "learning_objectives": [],
        "phases": [],
        "certifications": [],
        "job_preparation": [],
        "recommended_jobs": [],
        "_source": "empty",
    }
    empty_timeline = {
        "total_duration_weeks": 0,
        "hours_per_week": 10,
        "total_estimated_hours": 0,
        "weeks": [],
        "_source": "empty",
    }

    empty_roadmap = build_and_validate_roadmap(empty_plan, empty_timeline)
    assert empty_roadmap["phases"] == []
    assert empty_roadmap["timeline"]["weeks"] == []

    print("Empty plan/timeline assembly: PASS")

    print("=" * 70)
    print("ALL SCHEMA TESTS PASSED")
    print("=" * 70)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    run_self_test()
