"""
MINERVA — Personalized Roadmap RAG
timeline.py

Purpose:
    Turn planner.py's ordered, phase-based Learning Plan (WHAT to learn +
    in WHAT order) into a realistic, week-by-week schedule (WHEN to learn
    it + HOW LONG it takes), using a hybrid of deterministic rules and a
    Groq model call — following the exact same pattern as planner.py.

Architecture boundary:
    adapter.py      -> common profile
    level_rules.py   -> learner state / suitable resource levels
    retrieval.py     -> WHICH real resources match those rules
    planner.py       -> WHAT + ORDER learning plan
    timeline.py       -> WHEN + HOW LONG              (this file)

IMPORTANT ARCHITECTURE RULES:
    - timeline.py does NOT retrieve resources. No second retrieval call.
      It only reads resource metadata (estimated_hours, level, title,
      type) for resource_ids that planner.py already selected.
    - timeline.py does NOT invent, add, or remove resources. Every
      resource_id scheduled must come from planner.py's output, and every
      resource_id planner.py selected must be scheduled exactly once.
    - timeline.py does NOT change planner.py's order. Planner decided
      WHAT + in WHAT ORDER; timeline only distributes that fixed sequence
      across weeks according to hours_per_week.
    - timeline.py does NOT recalculate skill gaps or produce a new
      learning plan. That is adapter.py / level_rules.py / planner.py's
      job, not this file's.
    - timeline.py combines deterministic hour-budgeting rules with a Groq
      model call for realistic pacing, milestone naming, and week framing.
    - If the Groq call fails or returns an invalid/hallucinated timeline,
      timeline.py falls back to a fully deterministic timeline rather than
      crashing the pipeline — exactly like planner.py's fallback design.
    - timeline.py never changes WHAT is scheduled to make the output look
      nicer. Presentation cleanup (deduping repeated focus labels, folding
      a stray zero-hour week into a neighbour) only touches display
      fields and week numbering — it can never add, drop, reorder, or
      resize a resource's workload. Every cleanup pass is re-validated
      against the same grounding rules as the raw output before it is
      returned.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from dotenv import load_dotenv

load_dotenv()

from .planner import (
    DEFAULT_GROQ_MODEL,
    DEFAULT_MAX_COMPLETION_TOKENS,
    PlannerError,
    call_groq,
)
from .retrieval import load_resources


# ============================================================================
# CONFIGURATION
# ============================================================================

DEFAULT_TIMELINE_MODEL = DEFAULT_GROQ_MODEL  # same Groq model/config as planner.py

# Small float tolerance so 10.0000001 hours doesn't falsely fail a
# "<= hours_per_week" check due to floating point rounding.
HOURS_TOLERANCE = 1e-6


# ============================================================================
# ERRORS
# ============================================================================

class TimelineError(Exception):
    """Base error for timeline.py."""


class TimelineValidationError(TimelineError):
    """
    Raised when a model-produced (or hand-built) timeline fails structural
    or grounding validation — e.g. it schedules a resource_id the planner
    never selected, reorders the plan, or exceeds the weekly hour budget.
    """


# ============================================================================
# STEP 1 — BUILD TIMELINE INPUT (deterministic)
# ============================================================================

def _strip_phase_suffix(title: str) -> str:
    """'Python Development' -> 'Python'. Used only as a display focus label."""

    if title.endswith(" Development"):
        return title[: -len(" Development")]
    return title


def _flatten_planner_order(plan: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Produce the single, fixed (resource_id, focus_label) sequence that
    timeline.py must preserve. Built by walking planner.py's "phases" in
    order (this is the authoritative WHAT+ORDER decision), then appending
    any resource_ids that planner.py only listed in "certifications" /
    "job_preparation" / "recommended_jobs" without also placing them in a
    phase (this happens with real Groq planner output — those resources
    still must be scheduled, just with a best-effort focus label).
    """

    seen: Dict[str, str] = {}  # resource_id -> focus_label, insertion-ordered

    for phase in plan.get("phases", []):
        focus_label = _strip_phase_suffix(str(phase.get("title", "")))
        for resource_id in phase.get("resources", []):
            if resource_id not in seen:
                seen[resource_id] = focus_label

    for resource_id in plan.get("certifications", []) or []:
        if resource_id not in seen:
            seen[resource_id] = "Certification"

    for extra_key, label in (
        ("job_preparation", "Job Readiness"),
        ("recommended_jobs", "Job Readiness"),
    ):
        for resource_id in plan.get(extra_key, []) or []:
            if resource_id not in seen:
                seen[resource_id] = label

    return list(seen.items())


def build_timeline_input(
    plan: Dict[str, Any],
    resources: Sequence[Dict[str, Any]],
    hours_per_week: float,
    preferred_days: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Merge planner.py's plan with real resource metadata (estimated_hours,
    level, difficulty, resource_type) into ONE deterministic context
    package that is safe to hand to the model and to the deterministic
    fallback scheduler.

    Raises TimelineError if the plan references a resource_id that does
    not exist anywhere in the fixed resource pool — that would indicate
    an upstream bug (planner.py should never let this happen), and it is
    not something a fallback schedule could recover from either.
    """

    if not isinstance(plan, dict):
        raise TypeError("plan must be a dictionary.")

    if not isinstance(plan.get("phases"), list):
        raise TimelineError("plan is missing a valid 'phases' list.")

    if hours_per_week is None or hours_per_week <= 0:
        raise TimelineError("hours_per_week must be a positive number.")

    resource_by_id = {
        resource["resource_id"]: resource
        for resource in resources
        if isinstance(resource, dict) and resource.get("resource_id")
    }

    ordered_pairs = _flatten_planner_order(plan)

    ordered_resources: List[Dict[str, Any]] = []

    for resource_id, focus_label in ordered_pairs:
        resource = resource_by_id.get(resource_id)

        if resource is None:
            raise TimelineError(
                f"Plan references resource_id '{resource_id}' which does not "
                "exist in the fixed resource pool. This indicates an "
                "upstream (planner.py) bug — timeline.py cannot recover "
                "from a resource it cannot look up metadata for."
            )

        ordered_resources.append({
            "resource_id": resource_id,
            "focus": focus_label,
            "resource_type": resource.get("resource_type"),
            "title": resource.get("title"),
            "level": resource.get("level"),
            "difficulty": resource.get("difficulty"),
            "estimated_hours": resource.get("estimated_hours"),
        })

    total_estimated_hours = sum(
        r["estimated_hours"] for r in ordered_resources
        if isinstance(r["estimated_hours"], (int, float))
    )

    return {
        "goal": plan.get("goal"),
        "hours_per_week": hours_per_week,
        "preferred_days": preferred_days,
        "ordered_resources": ordered_resources,
        "planner_resource_order": [r["resource_id"] for r in ordered_resources],
        "total_estimated_hours": total_estimated_hours,
    }


def _model_facing_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """Everything the model needs, nothing it doesn't (no internal-only fields)."""

    return {
        "goal": context["goal"],
        "hours_per_week": context["hours_per_week"],
        "preferred_days": context["preferred_days"],
        "total_estimated_hours": context["total_estimated_hours"],
        "ordered_resources": context["ordered_resources"],
        "required_resource_ids": context["planner_resource_order"],
    }


# ============================================================================
# STEP 2 — GROQ MODEL CALL (reuses planner.py's call_groq / Groq config)
# ============================================================================

TIMELINE_SYSTEM_PROMPT = """\
You are the timeline stage of a deterministic learning-roadmap engine \
called MINERVA. You receive a FIXED, ORDERED list of resources that an \
upstream planner has already selected and sequenced, each with its real \
estimated_hours, plus the learner's available hours_per_week.

Your job is to convert this fixed learning plan into a realistic, \
week-by-week SCHEDULE. You do NOT decide what to learn or in what order \
— that has already been decided.

STRICT RULES:
1. Use ONLY the resource_id values given in "ordered_resources". Never \
   add, remove, replace, or invent a resource, title, URL, or \
   resource_id that was not provided.
2. Preserve the given order exactly. The order resources first appear \
   across your "weeks" must match "ordered_resources" — do not move a \
   later resource earlier or an earlier resource later.
3. Every resource in "ordered_resources" must be scheduled at least once, \
   and its scheduled weeks must be contiguous (no gaps, no reappearing \
   after it has already finished).
4. A week's total "estimated_hours" must never exceed "hours_per_week".
5. Use each resource's real "estimated_hours" to size its schedule. If \
   "estimated_hours" is null, make a conservative, clearly-labelled \
   estimate rather than inventing false precision — never claim a null- \
   hours resource has an exact numeric duration you were not given.
6. A resource whose estimated_hours exceeds hours_per_week MUST be split \
   across multiple consecutive weeks. Never cram it unrealistically into \
   one week.
7. Give each week a short "focus" list (skill/topic names, each one \
   listed only ONCE per week even if multiple resources share it) and a \
   short "milestone" string describing what was started or completed \
   that week.
8. Every week must carry real, positive "estimated_hours". Never emit a \
   trailing week whose only purpose is to list a resource with 0 hours \
   of work — fold that resource into the last week that still has \
   capacity, or give it a small honest hour allocation instead.
9. Before returning JSON, perform a RESOURCE COVERAGE CHECK:
   - The set of resource_ids appearing in weeks MUST equal the set of
     resource_ids in "required_resource_ids".
   - The first time each resource_id appears MUST follow the exact order
     in "required_resource_ids".
   - Do not omit a resource because it looks optional, is a certification,
     is a job-preparation item, or another resource seems more important.
10. If a resource has known estimated_hours, allocate its full workload.
    The timeline is not allowed to silently drop a selected resource.
11. Output STRICT JSON matching this schema and NOTHING else — no
    markdown fences, no commentary, no extra keys:

{
  "total_duration_weeks": integer,
  "hours_per_week": number,
  "weeks": [
    {
      "week": integer,
      "focus": [string, ...],
      "resources": [resource_id, ...],
      "estimated_hours": number,
      "milestone": string
    }
  ]
}
"""


def _build_timeline_messages(context: Dict[str, Any]) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": TIMELINE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(_model_facing_context(context), indent=2),
        },
    ]


def _build_timeline_repair_messages(
    context: Dict[str, Any],
    candidate: Optional[Dict[str, Any]],
    error: str,
) -> List[Dict[str, str]]:
    """Ask Groq once to repair a rejected timeline without changing WHAT+ORDER."""

    repair_system = TIMELINE_SYSTEM_PROMPT + """\

REPAIR MODE:
The previous timeline failed deterministic validation. Repair the complete
JSON using the exact same fixed resource list. Do not redesign the learning
plan. Every resource_id in required_resource_ids must appear, and its first
appearance must follow required_resource_ids exactly. No other resource_id
may appear.
"""

    repair_payload = {
        **_model_facing_context(context),
        "validation_error": error,
        "previous_candidate": candidate,
        "repair_instruction": (
            "Return a complete replacement timeline, not a patch. "
            "Preserve every required resource and the required first-appearance order."
        ),
    }

    return [
        {"role": "system", "content": repair_system},
        {"role": "user", "content": json.dumps(repair_payload, indent=2)},
    ]


def _parse_model_json(raw_text: str) -> Dict[str, Any]:
    """Parse the model's JSON reply, tolerating stray markdown fences."""

    cleaned = raw_text.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise TimelineValidationError(
            f"Model did not return valid JSON: {exc}"
        ) from exc

    if not isinstance(parsed, dict):
        raise TimelineValidationError("Model JSON root must be an object.")

    return parsed


# ============================================================================
# STEP 3 — VALIDATE TIMELINE STRUCTURE (deterministic, no trust in the model)
# ============================================================================

REQUIRED_TIMELINE_KEYS = {"total_duration_weeks", "hours_per_week", "weeks"}
REQUIRED_WEEK_KEYS = {"week", "focus", "resources", "estimated_hours", "milestone"}


def validate_timeline_structure(
    timeline: Dict[str, Any],
    context: Dict[str, Any],
) -> None:
    """
    Structural + grounding validation of a candidate timeline.

    Raises TimelineValidationError on the first problem found. Checks:
      - required top-level / week keys are present and well-typed
      - week numbers are sequential starting at 1, no gaps, no duplicates
      - every referenced resource_id was actually selected by planner.py
      - every planner.py resource_id is scheduled at least once
      - each resource's scheduled weeks are contiguous (no reappearing)
      - the first-appearance order of resources matches planner.py's order
      - no week's estimated_hours exceeds hours_per_week
      - total_duration_weeks matches the number of week entries
    """

    if not isinstance(timeline, dict):
        raise TimelineValidationError("Timeline must be a JSON object.")

    missing = REQUIRED_TIMELINE_KEYS - timeline.keys()
    if missing:
        raise TimelineValidationError(
            f"Timeline is missing required keys: {sorted(missing)}"
        )

    weeks = timeline["weeks"]
    if not isinstance(weeks, list):
        raise TimelineValidationError("'weeks' must be a list.")

    hours_per_week = context["hours_per_week"]
    valid_ids = set(context["planner_resource_order"])
    planner_order = context["planner_resource_order"]

    seen_weeks: set = set()
    resource_weeks: Dict[str, List[int]] = {}
    first_appearance_order: List[str] = []
    seen_first_appearance: set = set()

    for entry in weeks:

        if not isinstance(entry, dict):
            raise TimelineValidationError("Each week entry must be an object.")

        missing_week_keys = REQUIRED_WEEK_KEYS - entry.keys()
        if missing_week_keys:
            raise TimelineValidationError(
                f"Week entry is missing keys: {sorted(missing_week_keys)}"
            )

        week_number = entry["week"]
        if not isinstance(week_number, int):
            raise TimelineValidationError("'week' must be an integer.")

        if week_number in seen_weeks:
            raise TimelineValidationError(f"Week {week_number} appears more than once.")
        seen_weeks.add(week_number)

        if not isinstance(entry["resources"], list):
            raise TimelineValidationError(f"Week {week_number}: 'resources' must be a list.")

        estimated_hours = entry["estimated_hours"]
        if not isinstance(estimated_hours, (int, float)):
            raise TimelineValidationError(
                f"Week {week_number}: 'estimated_hours' must be numeric."
            )

        if estimated_hours > hours_per_week + HOURS_TOLERANCE:
            raise TimelineValidationError(
                f"Week {week_number} allocates {estimated_hours} hours, exceeding "
                f"the learner's hours_per_week budget of {hours_per_week}."
            )

        if estimated_hours < 0:
            raise TimelineValidationError(
                f"Week {week_number}: 'estimated_hours' cannot be negative."
            )

        for resource_id in entry["resources"]:

            if resource_id not in valid_ids:
                raise TimelineValidationError(
                    f"Timeline references resource_id '{resource_id}' which planner.py "
                    "never selected. This is a hallucinated / invented resource."
                )

            resource_weeks.setdefault(resource_id, []).append(week_number)

            if resource_id not in seen_first_appearance:
                seen_first_appearance.add(resource_id)
                first_appearance_order.append(resource_id)

    # Week numbers sequential starting at 1, no gaps.
    expected_weeks = set(range(1, len(weeks) + 1))
    if seen_weeks != expected_weeks:
        raise TimelineValidationError(
            f"Week numbers must be sequential starting at 1 with no gaps. "
            f"Got {sorted(seen_weeks)}, expected {sorted(expected_weeks)}."
        )

    # Every planner resource_id must be scheduled at least once.
    missing_resources = set(planner_order) - set(resource_weeks.keys())
    if missing_resources:
        raise TimelineValidationError(
            f"Timeline is missing required planner resources: {sorted(missing_resources)}"
        )

    # No timeline-only resource_ids beyond what planner selected.
    extra_resources = set(resource_weeks.keys()) - set(planner_order)
    if extra_resources:
        raise TimelineValidationError(
            f"Timeline schedules resource_ids planner.py never selected: "
            f"{sorted(extra_resources)}"
        )

    # Each resource's weeks must be contiguous (no gaps / no reappearing later).
    for resource_id, week_list in resource_weeks.items():
        span = sorted(week_list)
        if span != list(range(span[0], span[-1] + 1)):
            raise TimelineValidationError(
                f"resource_id '{resource_id}' is scheduled non-contiguously "
                f"across weeks {span}; it must occupy a single unbroken span."
            )

    # First-appearance order must match planner.py's fixed order exactly.
    if first_appearance_order != planner_order:
        raise TimelineValidationError(
            "Timeline changed planner.py's resource order. Expected first-"
            f"appearance order {planner_order}, got {first_appearance_order}."
        )

    # total_duration_weeks must match the number of week entries.
    if timeline["total_duration_weeks"] != len(weeks):
        raise TimelineValidationError(
            f"'total_duration_weeks' ({timeline['total_duration_weeks']}) does not "
            f"match the number of week entries ({len(weeks)})."
        )


# ============================================================================
# STEP 4 — DETERMINISTIC FALLBACK TIMELINE (no model, no network)
# ============================================================================

def deterministic_fallback_timeline(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a fully deterministic, capacity-constrained week-by-week
    schedule with no model involved.

    Greedily fills each week's hours_per_week budget with the next
    resource(s) in planner.py's fixed order, splitting any resource whose
    estimated_hours exceeds one week's budget across consecutive weeks.
    Resources with unknown estimated_hours are conservatively scheduled
    as a single full week each, rather than inventing false precision.

    Used when use_model=False, when no API key is configured, or as an
    automatic fallback if the Groq call fails or returns an invalid
    timeline.
    """

    hours_per_week = context["hours_per_week"]
    ordered_resources = context["ordered_resources"]

    weeks: List[Dict[str, Any]] = []
    current_week_resources: List[str] = []
    current_week_focus: List[str] = []
    current_week_hours = 0.0
    current_week_milestones: List[str] = []

    def _flush_week() -> None:
        nonlocal current_week_resources, current_week_focus
        nonlocal current_week_hours, current_week_milestones

        if not current_week_resources:
            return

        weeks.append({
            "week": len(weeks) + 1,
            "focus": list(dict.fromkeys(current_week_focus)),  # dedup, keep order
            "resources": list(current_week_resources),
            "estimated_hours": round(current_week_hours, 2),
            "milestone": "; ".join(current_week_milestones) if current_week_milestones else "In progress",
        })

        current_week_resources = []
        current_week_focus = []
        current_week_hours = 0.0
        current_week_milestones = []

    for resource in ordered_resources:

        resource_id = resource["resource_id"]
        title = resource.get("title") or resource_id
        focus = resource.get("focus") or "General"
        raw_hours = resource.get("estimated_hours")

        has_known_hours = isinstance(raw_hours, (int, float)) and raw_hours > 0
        remaining_hours = float(raw_hours) if has_known_hours else hours_per_week

        started_note_added = False

        while remaining_hours > 0:

            capacity_left = hours_per_week - current_week_hours

            if capacity_left <= HOURS_TOLERANCE:
                _flush_week()
                capacity_left = hours_per_week

            allocation = min(capacity_left, remaining_hours)

            if resource_id not in current_week_resources:
                current_week_resources.append(resource_id)
                current_week_focus.append(focus)
                if not started_note_added:
                    current_week_milestones.append(f"{title} started")
                    started_note_added = True

            current_week_hours += allocation
            remaining_hours -= allocation

            if not has_known_hours:
                # Unknown-duration resource: treat as "one week, done", rather
                # than looping indefinitely or inventing a fake hour count.
                remaining_hours = 0
                # Replace the "started" note with a clearer one since we
                # can't claim real completion math for an unknown duration.
                if current_week_milestones and current_week_milestones[-1] == f"{title} started":
                    current_week_milestones[-1] = f"{title} allocated (duration unknown)"

            if remaining_hours <= HOURS_TOLERANCE:
                if has_known_hours:
                    current_week_milestones.append(f"{title} completed")
                remaining_hours = 0

    _flush_week()

    total_hours = sum(week["estimated_hours"] for week in weeks)

    timeline = {
        "goal": context.get("goal"),
        "total_duration_weeks": len(weeks),
        "hours_per_week": hours_per_week,
        "total_estimated_hours": round(total_hours, 2),
        "weeks": weeks,
    }

    return timeline


def _empty_timeline(context: Dict[str, Any]) -> Dict[str, Any]:
    """No resources to schedule at all (planner.py returned an empty plan)."""

    return {
        "goal": context.get("goal"),
        "total_duration_weeks": 0,
        "hours_per_week": context.get("hours_per_week"),
        "total_estimated_hours": 0,
        "weeks": [],
        "_source": "empty",
        "_reason": "Planner output contained no resources to schedule.",
    }


# ============================================================================
# STEP 4.5 — PRESENTATION CLEANUP (cosmetic only, always re-validated)
# ============================================================================
#
# Two purely cosmetic issues can slip through structural validation because
# they are not grounding violations — a week with a repeated focus label, or
# a trailing week with 0 estimated_hours (e.g. a certification/job-prep
# resource with no real duration landing alone in its own week), are both
# *valid* per validate_timeline_structure(), just ugly for the learner to
# read. normalize_timeline_presentation() fixes both without touching WHAT
# is scheduled, in what order, or how many hours any resource is allocated:
#
#   1. Dedupe repeated focus labels within a single week.
#   2. Fold any zero-hour week into an adjacent week and renumber, so the
#      learner never sees a "Week N — 0 hrs" entry.
#
# The result is re-validated with the exact same grounding rules before
# being returned, so a bug here can never silently produce an invalid
# timeline — generate_timeline()'s existing exception handling will fall
# back to the deterministic timeline if re-validation ever fails.
# ============================================================================

def _dedupe_preserve_order(items: Sequence[Any]) -> List[Any]:
    return list(dict.fromkeys(items))


def _is_zero_hours(value: Any) -> bool:
    return not isinstance(value, (int, float)) or value <= HOURS_TOLERANCE


def _merge_week_into(target: Dict[str, Any], extra: Dict[str, Any]) -> None:
    """Fold `extra` week's resources/focus/milestone into `target` week in place."""

    target["resources"] = _dedupe_preserve_order(
        list(target.get("resources", [])) + list(extra.get("resources", []))
    )
    target["focus"] = _dedupe_preserve_order(
        list(target.get("focus", [])) + list(extra.get("focus", []))
    )
    extra_milestone = (extra.get("milestone") or "").strip()
    if extra_milestone:
        target_milestone = (target.get("milestone") or "").strip()
        target["milestone"] = (
            f"{target_milestone}; {extra_milestone}" if target_milestone else extra_milestone
        )


def _merge_zero_hour_weeks(weeks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Fold any week with ~0 estimated_hours into a neighbouring week (backward
    if one exists, otherwise forward into the next week), then let the
    caller renumber. Never drops a resource, focus label, or milestone —
    only relocates them into a week that has real hours attached.
    """

    result: List[Dict[str, Any]] = []
    i = 0
    n = len(weeks)

    while i < n:
        week = deepcopy(weeks[i])

        if _is_zero_hours(week.get("estimated_hours")):
            if result:
                # Fold backward into the last kept (non-zero) week.
                _merge_week_into(result[-1], week)
            elif i + 1 < n:
                # Zero-hour week is first with nothing before it yet — fold
                # it forward into the next week instead of dropping it.
                nxt = deepcopy(weeks[i + 1])
                merged_forward: Dict[str, Any] = {
                    "resources": [],
                    "focus": [],
                    "milestone": "",
                }
                _merge_week_into(merged_forward, week)
                _merge_week_into(merged_forward, nxt)
                merged_forward["estimated_hours"] = nxt.get("estimated_hours", 0)
                result.append(merged_forward)
                i += 1  # next week already consumed above
            else:
                # Only week in the whole timeline and it's zero hours —
                # nothing to merge into; keep it as-is rather than lose data.
                result.append(week)
        else:
            result.append(week)

        i += 1

    return result


def normalize_timeline_presentation(
    timeline: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Cosmetic cleanup pass applied to an already-validated timeline
    (deterministic or Groq-produced). See module notes above STEP 4.5 for
    what this does and does not change. Raises TimelineValidationError
    (via the internal re-validation) if cleanup ever produces something
    inconsistent with the original grounding rules — callers should treat
    that the same as any other validation failure.
    """

    weeks = deepcopy(timeline.get("weeks", []))
    if not weeks:
        return timeline

    for week in weeks:
        week["focus"] = _dedupe_preserve_order(week.get("focus", []))

    weeks = _merge_zero_hour_weeks(weeks)

    for index, week in enumerate(weeks, start=1):
        week["week"] = index

    normalized = deepcopy(timeline)
    normalized["weeks"] = weeks
    normalized["total_duration_weeks"] = len(weeks)

    # Cleanup must never produce an invalid timeline — re-check against the
    # same grounding rules the raw output already passed.
    validate_timeline_structure(normalized, context)

    return normalized


# ============================================================================
# STEP 5 — ORCHESTRATION
# ============================================================================

def generate_timeline(
    plan: Dict[str, Any],
    hours_per_week: float,
    resources: Optional[Sequence[Dict[str, Any]]] = None,
    resources_path: Optional[str] = None,
    preferred_days: Optional[int] = None,
    use_model: bool = True,
    api_key: Optional[str] = None,
    model: str = DEFAULT_TIMELINE_MODEL,
    groq_client: Optional[Callable[..., str]] = None,
) -> Dict[str, Any]:
    """
    End-to-end timeline entry point.

    Steps:
        1. Load resources.json if resources were not supplied (metadata
           lookup only — this is NOT a second retrieval; the resource_ids
           to look up come entirely from planner.py's plan).
        2. Build the deterministic timeline input package from plan +
           resource metadata + hours_per_week.
        3. If use_model: call Groq (via planner.py's call_groq), validate
           its output, and return it. On any failure (missing key,
           network error, invalid/hallucinated JSON, reordering, hour
           overruns), fall back to the deterministic timeline instead of
           raising.
        4. If not use_model: return the deterministic timeline directly.
        5. Either way, run a cosmetic normalization pass (dedupe focus
           labels, fold away zero-hour weeks) before returning, re-
           validating the result so cleanup can never introduce a
           grounding violation.

    `groq_client` lets callers/tests inject a stand-in for call_groq
    (e.g. a stub returning a fixed JSON string) without hitting the network.
    """

    if resources is None:
        resources = load_resources(resources_path)

    context = build_timeline_input(plan, resources, hours_per_week, preferred_days)

    if not context["ordered_resources"]:
        return _empty_timeline(context)

    if not use_model:
        timeline = deterministic_fallback_timeline(context)
        timeline["_source"] = "deterministic"
        timeline = normalize_timeline_presentation(timeline, context)
        timeline["_source"] = "deterministic"
        return _finalize_totals(timeline)

    caller = groq_client or call_groq

    # A week-by-week schedule (potentially 20+ weeks x several resources x
    # focus/milestone text) is a much bigger JSON payload than planner.py's
    # phase list. Give it a larger completion-token budget than the
    # planner default so it doesn't get cut off mid-schedule — that
    # truncation was the actual cause of "missing required planner
    # resources" fallbacks, since dropped resources were consistently the
    # ones scheduled toward the end of the output.
    timeline_max_tokens = max(
        DEFAULT_MAX_COMPLETION_TOKENS,
        400 * max(len(context["ordered_resources"]), 1),
    )

    try:
        raw_text = caller(
            _build_timeline_messages(context),
            api_key=api_key,
            model=model,
            max_completion_tokens=timeline_max_tokens,
        )
        timeline = _parse_model_json(raw_text)

        try:
            validate_timeline_structure(timeline, context)
        except TimelineValidationError as first_error:
            # One repair attempt keeps the deterministic validator as the
            # final authority while giving Groq a chance to fix omissions.
            repair_raw = caller(
                _build_timeline_repair_messages(
                    context, timeline, str(first_error)
                ),
                api_key=api_key,
                model=model,
                max_completion_tokens=timeline_max_tokens,
            )
            timeline = _parse_model_json(repair_raw)
            validate_timeline_structure(timeline, context)

        # Cosmetic cleanup (dedupe focus labels, fold zero-hour weeks).
        # Re-validated internally; if this ever fails it raises
        # TimelineValidationError, which the except clause below catches
        # exactly like any other validation failure and falls back to the
        # deterministic timeline instead of shipping something broken.
        timeline = normalize_timeline_presentation(timeline, context)

        timeline["goal"] = context.get("goal")
        timeline["_source"] = "groq"

    except (TimelineError, PlannerError) as exc:
        timeline = deterministic_fallback_timeline(context)
        timeline = normalize_timeline_presentation(timeline, context)
        timeline["_source"] = "deterministic_fallback"
        timeline["_fallback_reason"] = str(exc)

    return _finalize_totals(timeline)


def _finalize_totals(timeline: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministically derive total_estimated_hours from the accepted
    weekly schedule, regardless of which path produced `timeline`. The
    model may omit this field or return null; the canonical timeline
    must not.
    """

    total_estimated_hours = sum(
        float(week["estimated_hours"]) for week in timeline.get("weeks", [])
    )
    if total_estimated_hours.is_integer():
        total_estimated_hours = int(total_estimated_hours)
    timeline["total_estimated_hours"] = total_estimated_hours
    return timeline


# ============================================================================
# SELF TEST (deterministic only — no network / no API key required)
# ============================================================================

def run_self_test() -> None:

    print("=" * 70)
    print("MINERVA ROADMAP RAG — TIMELINE SELF TEST")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Get a REAL planner.py plan (deterministic path, no network) to
    # build the timeline against.
    # ------------------------------------------------------------------

    from planner import plan_from_profile

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
    assert plan["phases"], "Test setup requires a non-empty plan."

    # ------------------------------------------------------------------
    # 1. Normal timeline generation (deterministic, generous hours/week)
    # ------------------------------------------------------------------

    context = build_timeline_input(plan, resources, hours_per_week=20)
    timeline = deterministic_fallback_timeline(context)
    validate_timeline_structure(timeline, context)

    assert timeline["weeks"]
    assert timeline["total_duration_weeks"] == len(timeline["weeks"])

    print("Normal timeline generation: PASS")

    # ------------------------------------------------------------------
    # 2. Multi-week resource distribution (tight hours/week forces a
    #    resource whose estimated_hours > hours_per_week to span weeks)
    # ------------------------------------------------------------------

    tight_context = build_timeline_input(plan, resources, hours_per_week=3)
    tight_timeline = deterministic_fallback_timeline(tight_context)
    validate_timeline_structure(tight_timeline, tight_context)

    resource_week_counts: Dict[str, int] = {}
    for week in tight_timeline["weeks"]:
        for rid in week["resources"]:
            resource_week_counts[rid] = resource_week_counts.get(rid, 0) + 1

    assert any(count > 1 for count in resource_week_counts.values()), (
        "Expected at least one resource to span multiple weeks at 3 hrs/week."
    )
    assert all(
        week["estimated_hours"] <= 3 + HOURS_TOLERANCE
        for week in tight_timeline["weeks"]
    )

    print("Multi-week resource distribution: PASS")
    print("Hours/week budget respected: PASS")

    # ------------------------------------------------------------------
    # 3. Planner order preservation must be enforced
    # ------------------------------------------------------------------

    if len(context["planner_resource_order"]) >= 2:
        reordered = deepcopy(timeline)
        # Swap the resources of the first two weeks that actually differ,
        # to simulate the model breaking planner.py's fixed order.
        if len(reordered["weeks"]) >= 2:
            reordered["weeks"][0]["resources"], reordered["weeks"][-1]["resources"] = (
                reordered["weeks"][-1]["resources"],
                reordered["weeks"][0]["resources"],
            )

            try:
                validate_timeline_structure(reordered, context)
                raise AssertionError("Reordering violation was not caught.")
            except TimelineValidationError:
                pass

            print("Planner order preservation enforcement: PASS")

    # ------------------------------------------------------------------
    # 4. Invalid resource rejection
    # ------------------------------------------------------------------

    bad_timeline = deepcopy(timeline)
    bad_timeline["weeks"][0]["resources"].append("totally_invented_resource_999")

    try:
        validate_timeline_structure(bad_timeline, context)
        raise AssertionError("Hallucinated resource_id was not caught.")
    except TimelineValidationError:
        pass

    print("Invalid resource rejection: PASS")

    # ------------------------------------------------------------------
    # 5. generate_timeline with use_model=False (no network needed)
    # ------------------------------------------------------------------

    result = generate_timeline(plan, hours_per_week=10, resources=resources, use_model=False)
    assert result["_source"] == "deterministic"
    validate_timeline_structure(result, build_timeline_input(plan, resources, 10))

    print("generate_timeline(use_model=False): PASS")

    # ------------------------------------------------------------------
    # 6. generate_timeline with a stubbed Groq client -> success path
    # ------------------------------------------------------------------

    def _stub_groq_success(messages, api_key=None, model=None, **kwargs):
        stub_context = build_timeline_input(plan, resources, hours_per_week=10)
        stub_timeline = deterministic_fallback_timeline(stub_context)
        return json.dumps(stub_timeline)

    stubbed = generate_timeline(
        plan,
        hours_per_week=10,
        resources=resources,
        use_model=True,
        groq_client=_stub_groq_success,
    )
    assert stubbed["_source"] == "groq"

    print("generate_timeline(Groq success via stub): PASS")

    # ------------------------------------------------------------------
    # 7. Groq failure -> deterministic fallback
    # ------------------------------------------------------------------

    def _stub_groq_failure(messages, api_key=None, model=None, **kwargs):
        raise PlannerError("simulated network failure")

    fallback = generate_timeline(
        plan,
        hours_per_week=10,
        resources=resources,
        use_model=True,
        groq_client=_stub_groq_failure,
    )
    assert fallback["_source"] == "deterministic_fallback"
    assert "simulated network failure" in fallback["_fallback_reason"]

    print("generate_timeline(Groq failure -> fallback): PASS")

    # ------------------------------------------------------------------
    # 8. Missing API key -> graceful fallback (no crash)
    # ------------------------------------------------------------------

    os.environ.pop("GROQ_API_KEY", None)

    no_key_result = generate_timeline(plan, hours_per_week=10, resources=resources, use_model=True)
    assert no_key_result["_source"] == "deterministic_fallback"

    print("generate_timeline(no API key -> graceful fallback): PASS")

    # ------------------------------------------------------------------
    # 9. Invalid Groq JSON -> fallback
    # ------------------------------------------------------------------

    def _stub_groq_bad_json(messages, api_key=None, model=None, **kwargs):
        return "this is not valid JSON at all {{{"

    bad_json_result = generate_timeline(
        plan,
        hours_per_week=10,
        resources=resources,
        use_model=True,
        groq_client=_stub_groq_bad_json,
    )
    assert bad_json_result["_source"] == "deterministic_fallback"

    print("generate_timeline(invalid Groq JSON -> fallback): PASS")

    # ------------------------------------------------------------------
    # 10. Timeline validation catches an hours-per-week overrun
    # ------------------------------------------------------------------

    overrun_timeline = deepcopy(timeline)
    overrun_timeline["weeks"][0]["estimated_hours"] = context["hours_per_week"] + 5

    try:
        validate_timeline_structure(overrun_timeline, context)
        raise AssertionError("Hours-per-week overrun was not caught.")
    except TimelineValidationError:
        pass

    print("Hours-per-week overrun rejection: PASS")

    # ------------------------------------------------------------------
    # 11. Presentation cleanup: duplicate focus labels get deduped
    # ------------------------------------------------------------------

    dup_focus_timeline = deepcopy(timeline)
    dup_focus_timeline["weeks"][0]["focus"] = ["Intermediate", "Intermediate"]
    cleaned = normalize_timeline_presentation(dup_focus_timeline, context)
    assert cleaned["weeks"][0]["focus"] == ["Intermediate"]

    print("Presentation cleanup (duplicate focus labels): PASS")

    # ------------------------------------------------------------------
    # 12. Presentation cleanup: trailing zero-hour week gets merged away
    # ------------------------------------------------------------------

    zero_week_timeline = deepcopy(timeline)
    last_resource_id = context["planner_resource_order"][-1]
    zero_week_timeline["weeks"].append({
        "week": len(zero_week_timeline["weeks"]) + 1,
        "focus": ["Job Readiness"],
        "resources": [last_resource_id],
        "estimated_hours": 0,
        "milestone": "Added Backend Developer profile",
    })
    zero_week_timeline["total_duration_weeks"] = len(zero_week_timeline["weeks"])
    # This still passes structural validation (0 hours is legal), which is
    # exactly why it needs the separate cosmetic pass, not a stricter
    # validator rule.
    validate_timeline_structure(zero_week_timeline, context)

    weeks_before = len(zero_week_timeline["weeks"])
    cleaned_zero = normalize_timeline_presentation(zero_week_timeline, context)

    assert len(cleaned_zero["weeks"]) == weeks_before - 1
    assert all(week["estimated_hours"] > 0 for week in cleaned_zero["weeks"])
    assert cleaned_zero["weeks"][-1]["milestone"].endswith(
        "Added Backend Developer profile"
    )
    validate_timeline_structure(cleaned_zero, context)

    print("Presentation cleanup (zero-hour week merge): PASS")

    print("=" * 70)
    print("ALL TIMELINE TESTS PASSED")
    print("=" * 70)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    run_self_test()
