"""
MINERVA — Personalized Roadmap Engine
roadmap_engine.py

Purpose
-------
Pure orchestrator. Every real decision (career adaptation, skill-gap
rules, resource retrieval, plan generation, scheduling, structural
schema, semantic validation) already lives in its own module. This file
calls them in the right order and does nothing else.

Pipeline (per profile)
-----------------------
Journey output
    -> adapter.py            (Journey-specific -> common profile)
    -> level_rules.py         (skills -> gap/level actions)
    -> retrieval.py            (actions -> verified real resources)
    -> planner.py               (resources -> phased plan; Groq + its
                                  own deterministic fallback)
    -> timeline.py                (plan -> weekly schedule; Groq + its
                                     own deterministic fallback)
    -> schema.py                    (assemble + structural validation)
    -> validator.py                  (semantic/business-rule validation)
    -> FINAL ROADMAP

Journey contract (this is the part the engine enforces)
---------------------------------------------------------
Journey 1 (career exploration):
    Adapter returns one profile PER career found in the J1 output.
    The engine NEVER narrows this to one career, NEVER scores or ranks
    careers, and NEVER lets the model pick "the best" one. Every
    profile gets the full pipeline run independently.
    -> Returns a List[Dict]: one validated roadmap per career.

Journey 2 (career already selected by the user):
    Adapter returns exactly one profile (career embedded in J2 output).
    -> Returns a single Dict: one validated roadmap.

Journey 3 (skills-focused refinement):
    Adapter returns exactly one profile with career=None. J3's assessed
    skills are the sole driver of the roadmap — the engine never
    forces J2's previously-selected career onto it, never invents a
    career, and never invents skills outside what adapter.py verified.
    -> Returns a single Dict: one validated roadmap (career stays
       whatever adapter.py produced, i.e. None — pure metadata, never
       a filter).

What this file must NEVER do (enforced by construction, not by
convention — none of these operations even appear below):
    - career scoring / career selection / career ranking
    - skill-gap, current-level, or target-level recalculation
    - evidence invention
    - resource invention or fake resource_ids
    - a second "agent" layer, or a duplicate of planner.py's/
      timeline.py's own Groq-fallback logic
    - silently returning a roadmap that failed validation
"""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from .adapter import adapt, validate_common_profile
from .level_rules import apply_profile_level_rules
from .retrieval import load_resources, retrieve_profile
from .planner import plan_from_profile
from .timeline import generate_timeline
from .schema import build_and_validate_roadmap, to_json
from .validator import validate_roadmap, ValidationReport


DEFAULT_RESOURCES_PATH = Path(__file__).with_name("resources.json")
DEFAULT_OUTPUT_DIR = Path(__file__).with_name("output")

VALID_JOURNEYS = {1, 2, 3}


# ============================================================================
# ERRORS
# ============================================================================

class RoadmapEngineError(Exception):
    """Base error for roadmap_engine.py."""


class RoadmapEngineValidationError(RoadmapEngineError):
    """
    Raised when a roadmap fails semantic validation in BOTH the
    requested pipeline mode and the full deterministic recovery
    pipeline. This is never silently swallowed — per the architecture
    contract, an invalid roadmap is never handed back to a caller.
    """

    def __init__(self, career_context: Optional[str], first_report: ValidationReport,
                 recovery_report: ValidationReport):
        self.career_context = career_context
        self.first_report = first_report
        self.recovery_report = recovery_report
        where = f" (career={career_context!r})" if career_context else ""
        super().__init__(
            f"Roadmap failed semantic validation{where} in both the requested "
            f"pipeline and the deterministic recovery pipeline.\n"
            f"Initial run: {first_report.summary()}\n"
            f"Recovery run: {recovery_report.summary()}"
        )


def _log(message: str) -> None:
    """Print live roadmap-engine progress immediately."""
    print(message, flush=True)


def _source_label(value: Any) -> str:
    """Return a compact human-readable source label."""
    return str(value or "unknown")


# ============================================================================
# STAGE 1 — ADAPTATION
# ============================================================================

def _adapt_journey1_all_careers(journey_output: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Journey 1 always yields every career profile present in the output.
    No career is ever selected or filtered here — that's the entire
    point of Journey 1 (career exploration), and the master contract
    is explicit: "AI automatically select nahi hoga".
    """

    profiles = adapt(journey=1, journey_output=journey_output, career=None)

    if not isinstance(profiles, list):
        raise RoadmapEngineError(
            "adapter.adapt(journey=1, ...) must return a list of profiles."
        )

    if not profiles:
        raise RoadmapEngineError(
            "Journey 1 adapter produced no career profiles from this input."
        )

    return profiles


def _adapt_single_profile(journey: int, journey_output: Dict[str, Any]) -> Dict[str, Any]:
    """Journey 2 and Journey 3 each yield exactly one profile."""

    profile = adapt(journey=journey, journey_output=journey_output, career=None)

    if not isinstance(profile, dict):
        raise RoadmapEngineError(
            f"adapter.adapt(journey={journey}, ...) must return a single profile dict."
        )

    return profile


# ============================================================================
# STAGE 1b — OPTIONAL RUNTIME SETTINGS (never invented user facts — these
# are explicit caller-supplied configuration, e.g. "how many hours per
# week can this learner study", which no Journey output is guaranteed
# to carry)
# ============================================================================

def _apply_runtime_settings(
    profile: Dict[str, Any],
    weekly_hours: Optional[float],
    goal: Optional[str],
    target_role: Optional[str],
) -> Dict[str, Any]:

    result = deepcopy(profile)

    if weekly_hours is not None:
        if weekly_hours <= 0:
            raise ValueError("weekly_hours must be greater than zero.")
        result["weekly_hours"] = float(weekly_hours)

    if goal is not None:
        result["goal"] = goal

    if target_role is not None:
        result["target_role"] = target_role

    validate_common_profile(result)
    return result


# ============================================================================
# STAGES 2-7 — LEVEL RULES -> RETRIEVAL -> PLANNER -> TIMELINE -> SCHEMA ->
# VALIDATOR, for exactly ONE profile
# ============================================================================

def _run_pipeline_once(
    profile: Dict[str, Any],
    resources: Sequence[Dict[str, Any]],
    *,
    use_model: bool,
    api_key: Optional[str],
    model: Optional[str],
    preferred_days: Optional[int],
    groq_client: Optional[Callable[..., str]],
) -> Dict[str, Any]:
    """
    Run level_rules -> retrieval -> planner -> timeline -> schema for a
    single already-adapted, already-configured profile, then validate
    the result and return it.

    Groq success/failure and the deterministic fallback for BOTH the
    plan and the timeline are handled entirely inside planner.py and
    timeline.py themselves (their own `_source` field records which
    path was taken) — this function does not duplicate that logic.

    If the resulting roadmap fails validator.py's semantic checks, this
    re-runs the ENTIRE plan + timeline generation deterministically
    from the same source-of-truth profile and resource pool (never
    "patches" a bad model output) and validates again. If that still
    fails, raises RoadmapEngineValidationError — a roadmap that never
    passed validation is never returned.
    """

    if "weekly_hours" not in profile or profile.get("weekly_hours") is None:
        raise RoadmapEngineError(
            "Profile is missing 'weekly_hours'. Supply it explicitly via "
            "the weekly_hours parameter, since not every Journey output "
            "carries it."
        )

    # ---- level_rules.py -----------------------------------------------
    profile_with_rules = apply_profile_level_rules(profile)

    # ---- retrieval.py ---------------------------------------------------
    # Run explicitly here for pipeline transparency (this is the
    # "Verified Resources" stage in the architecture diagram). planner.py
    # re-runs retrieval internally against the same profile + resource
    # pool before building its plan — that's planner.py re-confirming its
    # own inputs, not this engine duplicating any business rule.
    retrieve_profile(profile_with_rules, resources)

    def _plan_and_schedule(use_model_now: bool):
        plan = plan_from_profile(
            profile_with_rules,
            resources=resources,
            use_model=use_model_now,
            api_key=api_key,
            **({"model": model} if model else {}),
            **({"groq_client": groq_client} if groq_client else {}),
        )
        timeline = generate_timeline(
            plan,
            hours_per_week=profile_with_rules["weekly_hours"],
            resources=resources,
            preferred_days=preferred_days,
            use_model=use_model_now,
            api_key=api_key,
            **({"model": model} if model else {}),
            **({"groq_client": groq_client} if groq_client else {}),
        )
        return plan, timeline

    plan, timeline = _plan_and_schedule(use_model)
    roadmap = build_and_validate_roadmap(plan, timeline, profile=profile_with_rules)
    report = validate_roadmap(roadmap, resources=resources)

    if report.is_valid:
        roadmap["meta"]["engine_mode"] = "groq_with_module_fallbacks" if use_model else "deterministic"
        roadmap["meta"]["validation"] = report.to_dict()

        # Only touches roadmaps that are genuinely empty (no gaps found,
        # nothing to plan). Non-empty roadmaps (learning_objectives or
        # phases present) skip this entirely and return exactly as before.
        if not roadmap.get("learning_objectives") and not roadmap.get("phases"):
            unassessed = [
                s.get("skill_id")
                for s in profile_with_rules.get("level_rules", [])
                if s.get("state") in ("no_evidence", "unknown_level")
            ]
            roadmap["meta"]["status"] = (
                "already_qualified" if not unassessed else "no_gaps_some_unassessed"
            )
            roadmap["meta"]["unassessed_skills"] = unassessed

        return roadmap

    # ---- deterministic recovery ------------------------------------------
    # Do not patch an invalid model output — regenerate the plan and
    # timeline completely deterministically from the same profile/
    # resources, then validate again.
    fallback_plan, fallback_timeline = _plan_and_schedule(False)
    fallback_roadmap = build_and_validate_roadmap(
        fallback_plan, fallback_timeline, profile=profile_with_rules
    )
    fallback_report = validate_roadmap(fallback_roadmap, resources=resources)

    if fallback_report.is_valid:
        fallback_roadmap["meta"]["engine_mode"] = "deterministic_recovery"
        fallback_roadmap["meta"]["validation"] = fallback_report.to_dict()
        fallback_roadmap["meta"]["initial_validation_failure"] = report.to_dict()

        # Same empty-roadmap handling as the primary path above.
        if not fallback_roadmap.get("learning_objectives") and not fallback_roadmap.get("phases"):
            unassessed = [
                s.get("skill_id")
                for s in profile_with_rules.get("level_rules", [])
                if s.get("state") in ("no_evidence", "unknown_level")
            ]
            fallback_roadmap["meta"]["status"] = (
                "already_qualified" if not unassessed else "no_gaps_some_unassessed"
            )
            fallback_roadmap["meta"]["unassessed_skills"] = unassessed

        return fallback_roadmap

    raise RoadmapEngineValidationError(
        career_context=profile_with_rules.get("career"),
        first_report=report,
        recovery_report=fallback_report,
    )


# ============================================================================
# PUBLIC ENTRY POINT
# ============================================================================

def generate_roadmap(
    journey: int,
    journey_output: Dict[str, Any],
    *,
    weekly_hours: Optional[float] = None,
    goal: Optional[str] = None,
    target_role: Optional[str] = None,
    preferred_days: Optional[int] = None,
    resources: Optional[Sequence[Dict[str, Any]]] = None,
    resources_path: Optional[str] = None,
    use_model: bool = True,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    groq_client: Optional[Callable[..., str]] = None,
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Main production entry point. Runs the full pipeline for the given
    Journey output and returns the validated roadmap(s).

    Parameters
    ----------
    journey:
        1, 2, or 3. No `career` parameter exists anywhere on this
        function by design — this engine never selects, filters, or
        overrides a career for any journey (see module docstring).
    weekly_hours / goal / target_role:
        Explicit runtime configuration, applied only if supplied.
        Never invented; Journey values are preserved otherwise.
    use_model:
        True  = planner.py/timeline.py's normal Groq-with-fallback path.
        False = fully deterministic planner + timeline, no network call.

    Returns
    -------
    Journey 1: List[Dict]  — one validated roadmap per career found in
               the input (always a list, even if only one career was
               present, so callers never need to type-branch on count).
    Journey 2 or 3: Dict    — one validated roadmap.
    """

    if journey not in VALID_JOURNEYS:
        raise ValueError(f"journey must be one of {sorted(VALID_JOURNEYS)}.")

    if not isinstance(journey_output, dict):
        raise TypeError(f"Journey {journey} output must be a dictionary.")

    if resources is None:
        resources = load_resources(
            str(resources_path) if resources_path else str(DEFAULT_RESOURCES_PATH)
        )

    pipeline_kwargs = dict(
        use_model=use_model,
        api_key=api_key,
        model=model,
        preferred_days=preferred_days,
        groq_client=groq_client,
    )

    if journey == 1:
        profiles = _adapt_journey1_all_careers(journey_output)

        roadmaps: List[Dict[str, Any]] = []
        total_profiles = len(profiles)

        if use_model:
            _log(f"[INFO] Journey {journey}: processing {total_profiles} career roadmap(s) with Groq...")
        else:
            _log(f"[INFO] Journey {journey}: processing {total_profiles} career roadmap(s) deterministically...")

        for index, raw_profile in enumerate(profiles, start=1):
            career = raw_profile.get("career") or "unknown"
            _log(f"\n[{index}/{total_profiles}] Career: {career}")
            _log(f"  → Level rules + resource retrieval...")
            prepared = _apply_runtime_settings(raw_profile, weekly_hours, goal, target_role)
            _log(f"  ✓ Profile prepared")

            if use_model:
                _log(f"  → Planner: Groq/model path starting...")
            else:
                _log(f"  → Planner: deterministic path starting...")
            roadmap = _run_pipeline_once(prepared, resources, **pipeline_kwargs)

            meta = roadmap.get("meta", {})
            plan_source = _source_label(meta.get("plan_source"))
            timeline_source = _source_label(meta.get("timeline_source"))
            validation = meta.get("validation", {})
            is_valid = bool(validation.get("is_valid"))

            _log(f"  ✓ Planner source: {plan_source}")
            _log(f"  ✓ Timeline source: {timeline_source}")
            _log(f"  ✓ Validation: {'VALID' if is_valid else 'INVALID'}")
            _log(f"  ✓ Completed: {career}")

            roadmaps.append(roadmap)

        _log(f"\n[COMPLETE] Journey {journey}: all {total_profiles} career roadmap(s) processed.")
        return roadmaps

    # Journey 2 or 3 — exactly one profile, exactly one roadmap.
    profile = _adapt_single_profile(journey, journey_output)
    career = profile.get("career") or "unknown"
    _log(f"[INFO] Journey {journey}: processing career={career}")
    _log("  → Level rules + resource retrieval...")
    prepared = _apply_runtime_settings(profile, weekly_hours, goal, target_role)
    _log("  ✓ Profile prepared")
    _log("  → Running planner + timeline...")
    roadmap = _run_pipeline_once(prepared, resources, **pipeline_kwargs)
    meta = roadmap.get("meta", {})
    _log(f"  ✓ Planner source: {_source_label(meta.get('plan_source'))}")
    _log(f"  ✓ Timeline source: {_source_label(meta.get('timeline_source'))}")
    validation = meta.get("validation", {})
    _log(f"  ✓ Validation: {'VALID' if validation.get('is_valid') else 'INVALID'}")
    _log(f"  ✓ Completed: {career}")
    return roadmap


# ============================================================================
# PERSISTENCE / CLI HELPERS
# ============================================================================

def save_roadmap(roadmap: Dict[str, Any], output_path: Union[str, Path]) -> Path:
    """Write one canonical roadmap JSON file."""

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(to_json(roadmap, indent=2), encoding="utf-8")
    return output


def save_roadmaps(
    result: Union[Dict[str, Any], List[Dict[str, Any]]],
    output_dir: Union[str, Path] = DEFAULT_OUTPUT_DIR,
    base_name: str = "roadmap",
) -> List[Path]:
    """
    Persist generate_roadmap()'s return value.

    A list (Journey 1) is written as one file per career, named
    `<base_name>_<career>.json`. A single dict (Journey 2/3) is written
    as `<base_name>.json`. Returns every path written.
    """

    output_dir = Path(output_dir)

    if isinstance(result, list):
        paths = []
        for roadmap in result:
            career = roadmap.get("career") or "unknown"
            path = save_roadmap(roadmap, output_dir / f"{base_name}_{career}.json")
            paths.append(path)
        return paths

    return [save_roadmap(result, output_dir / f"{base_name}.json")]


def load_json_file(path: Union[str, Path]) -> Dict[str, Any]:
    """Load one Journey JSON file."""

    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"Input JSON not found: {file_path}")

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {file_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"JSON file '{file_path}' must contain an object.")

    return data


def _print_roadmap_summary(roadmap: Dict[str, Any]) -> None:
    meta = roadmap.get("meta", {})
    timeline = roadmap.get("timeline", {})

    print("-" * 70)
    print(f"Career:              {roadmap.get('career')}")
    print(f"Goal:                {roadmap.get('goal')}")
    print(f"Learning objectives: {len(roadmap.get('learning_objectives', []))}")
    print(f"Phases:              {len(roadmap.get('phases', []))}")
    print(f"Duration:            {timeline.get('total_duration_weeks')} weeks")
    print(f"Hours/week:          {timeline.get('hours_per_week')}")
    print(f"Total hours:         {timeline.get('total_estimated_hours')}")
    print(f"Plan source:         {meta.get('plan_source')}")
    print(f"Timeline source:     {meta.get('timeline_source')}")
    print(f"Engine mode:         {meta.get('engine_mode')}")
    validation = meta.get("validation", {})
    print(f"Validation:          {'VALID' if validation.get('is_valid') else 'INVALID'} "
          f"({len(validation.get('errors', []))} error(s), "
          f"{len(validation.get('warnings', []))} warning(s))")


def main() -> None:
    parser = argparse.ArgumentParser(description="MINERVA Personalized Roadmap Engine")

    parser.add_argument("--journey", type=int, choices=[1, 2, 3], required=True)
    parser.add_argument("--input", required=True, help="Path to the Journey output JSON.")
    parser.add_argument("--hours", type=float, default=None, help="Weekly learning hours.")
    parser.add_argument("--goal", default=None)
    parser.add_argument("--target-role", default=None)
    parser.add_argument("--preferred-days", type=int, default=None)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-model", action="store_true",
                         help="Run completely deterministic planner + timeline.")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--model", default=None)

    args = parser.parse_args()

    journey_output = load_json_file(args.input)

    result = generate_roadmap(
        journey=args.journey,
        journey_output=journey_output,
        weekly_hours=args.hours,
        goal=args.goal,
        target_role=args.target_role,
        preferred_days=args.preferred_days,
        use_model=not args.no_model,
        api_key=args.api_key,
        model=args.model,
    )

    print("=" * 70)
    print("MINERVA — ROADMAP ENGINE")
    print("=" * 70)

    if isinstance(result, list):
        print(f"Journey {args.journey}: {len(result)} career roadmap(s) generated.")
        for roadmap in result:
            _print_roadmap_summary(roadmap)
    else:
        print(f"Journey {args.journey}: 1 roadmap generated.")
        _print_roadmap_summary(result)

    paths = save_roadmaps(result, output_dir=args.output_dir)
    print("-" * 70)
    for path in paths:
        print(f"Saved: {path.resolve()}")


if __name__ == "__main__":
    main()