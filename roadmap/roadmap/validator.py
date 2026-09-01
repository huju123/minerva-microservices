"""
MINERVA — Personalized Roadmap RAG
validator.py

Purpose:
    Deep, semantic / business-rule validation of a fully assembled,
    structurally-valid roadmap (schema.py's build_and_validate_roadmap()
    output) against the LIVE resources.json pool.

Architecture boundary:
    adapter.py       -> common profile
    level_rules.py    -> learner state / suitable resource levels
    retrieval.py      -> WHICH real resources match those rules
    planner.py        -> WHAT + ORDER learning plan
    timeline.py        -> WHEN + HOW LONG
    schema.py           -> Complete roadmap's strict structured format
    validator.py         -> deep/semantic validation of the assembled roadmap (this file)
    roadmap_engine.py    -> wires the whole pipeline together (future)

IMPORTANT ARCHITECTURE RULES:
    - validator.py does NOT repeat schema.py's structural checks (missing
      keys, wrong types, internal count consistency). It calls
      validate_roadmap_schema() once, up front, as a cheap precondition —
      its actual job starts after that already passes.
    - validator.py does NOT repeat planner.py's / timeline.py's own
      grounding checks against the context THEY were built from
      (validate_plan_structure, validate_timeline_structure). Those
      already ran during planning/scheduling, against the retrieval
      snapshot that was live at that moment. validator.py instead
      cross-checks the FINAL ASSEMBLED roadmap against whatever
      resources.json is live RIGHT NOW — this is deliberately a second,
      independent check: it catches drift if resources.json changed
      between planning and validation, or if a roadmap arrived here from
      storage / an API call / a hand-edited file rather than straight out
      of the pipeline, where nothing upstream ever validated it at all.
    - validator.py does NOT mutate the roadmap. It only inspects it and
      reports problems; presentation cleanup belongs to the producing
      stage (see timeline.py's normalize_timeline_presentation), not here.
    - validator.py does NOT invent business rules that contradict an
      earlier stage's deliberate decision (e.g. it never overrides
      planner.py's resource selection). It only checks that the selection
      already made is internally sensible and grounded in real data.
    - validator.py distinguishes ERRORS (roadmap is not fit to hand to a
      learner — reject it) from WARNINGS (worth surfacing, e.g. to logs
      or a review queue, but not a hard failure). Both are attached to a
      single ValidationReport rather than raising on the first problem,
      so a caller (e.g. roadmap_engine.py) can see the whole picture at
      once instead of fixing one issue per run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .schema import validate_roadmap_schema
from .retrieval import load_resources


# ============================================================================
# CONFIGURATION
# ============================================================================

HOURS_TOLERANCE = 1e-6

# Resource types that must never be embedded inside a learning phase — a
# phase is "what to study", not "what job to apply to". The one sanctioned
# exception is planner.py's own convention (see deterministic_fallback_plan)
# of appending a final phase literally titled "Job Readiness" that holds
# the same job resource_ids also listed in job_preparation/recommended_jobs
# — that phase exists specifically to surface job-hunting as a roadmap
# step, so job-type resources are allowed there and nowhere else.
PHASE_DISALLOWED_RESOURCE_TYPES = {"job"}
JOB_READINESS_PHASE_TITLE = "job readiness"

# roadmap["certifications"] must only ever point at real certifications.
CERTIFICATION_RESOURCE_TYPE = "certification"

# roadmap["job_preparation"] / roadmap["recommended_jobs"] must only ever
# point at real job archetypes/listings.
JOB_RESOURCE_TYPE = "job"

# Priorities that make a learning objective "must be addressed by at
# least one phase" rather than optional/nice-to-have.
CRITICAL_PRIORITIES = {"critical", "high"}

# A roadmap longer than this is not "wrong", just worth a human glance —
# flagged as a WARNING, never an ERROR.
MAX_REASONABLE_DURATION_WEEKS = 104  # ~2 years

# Soft heuristic threshold for flagging a later phase that is, on
# average, meaningfully *easier* than an earlier phase (learners
# shouldn't regress in resource level as they progress through phases).
LEVEL_REGRESSION_WARNING_THRESHOLD = 0.5


# ============================================================================
# ERRORS
# ============================================================================

class ValidatorError(Exception):
    """Base error for validator.py."""


class RoadmapValidationError(ValidatorError):
    """
    Raised by validate_roadmap_or_raise() when the assembled ValidationReport
    contains at least one ERROR-severity issue. Carries the full report so
    callers can inspect every problem, not just the first one.
    """

    def __init__(self, report: "ValidationReport") -> None:
        self.report = report
        summary = "; ".join(
            f"[{issue.code}] {issue.message}" for issue in report.errors
        )
        super().__init__(
            f"Roadmap failed semantic validation "
            f"({len(report.errors)} error(s), {len(report.warnings)} warning(s)): {summary}"
        )


# ============================================================================
# REPORT MODEL
# ============================================================================

@dataclass
class ValidationIssue:
    code: str
    severity: str  # "error" | "warning"
    message: str
    location: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "location": self.location,
        }


@dataclass
class ValidationReport:
    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True iff there are zero ERROR-severity issues (warnings are OK)."""
        return not self.errors

    def add_error(self, code: str, message: str, location: str = "") -> None:
        self.errors.append(ValidationIssue(code, "error", message, location))

    def add_warning(self, code: str, message: str, location: str = "") -> None:
        self.warnings.append(ValidationIssue(code, "warning", message, location))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }

    def summary(self) -> str:
        lines = [
            f"ValidationReport: {'VALID' if self.is_valid else 'INVALID'} "
            f"({len(self.errors)} error(s), {len(self.warnings)} warning(s))"
        ]
        for issue in self.errors:
            lines.append(f"  ERROR   [{issue.code}] {issue.location}: {issue.message}")
        for issue in self.warnings:
            lines.append(f"  WARNING [{issue.code}] {issue.location}: {issue.message}")
        return "\n".join(lines)


# ============================================================================
# SHARED HELPERS
# ============================================================================

def _resource_index(resources: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {
        resource["resource_id"]: resource
        for resource in resources
        if isinstance(resource, dict) and resource.get("resource_id")
    }


def _iter_resource_refs(roadmap: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Every (resource_id, location_label) pair referenced anywhere in the
    assembled roadmap: phases, certifications, job_preparation,
    recommended_jobs, and the timeline's per-week resource lists.
    """

    refs: List[Tuple[str, str]] = []

    for phase in roadmap.get("phases", []) or []:
        phase_label = f"phases[phase={phase.get('phase')}]"
        for resource_id in phase.get("resources", []) or []:
            refs.append((resource_id, phase_label))

    for resource_id in roadmap.get("certifications", []) or []:
        refs.append((resource_id, "certifications"))

    for resource_id in roadmap.get("job_preparation", []) or []:
        refs.append((resource_id, "job_preparation"))

    for resource_id in roadmap.get("recommended_jobs", []) or []:
        refs.append((resource_id, "recommended_jobs"))

    for week in roadmap.get("timeline", {}).get("weeks", []) or []:
        week_label = f"timeline.weeks[week={week.get('week')}]"
        for resource_id in week.get("resources", []) or []:
            refs.append((resource_id, week_label))

    return refs


def _first_appearance_phase_index(roadmap: Dict[str, Any]) -> Dict[str, int]:
    """resource_id -> 0-based index of the first phase it appears in."""

    first_index: Dict[str, int] = {}
    for index, phase in enumerate(roadmap.get("phases", []) or []):
        for resource_id in phase.get("resources", []) or []:
            if resource_id not in first_index:
                first_index[resource_id] = index
    return first_index


# ============================================================================
# CHECK 1 — every referenced resource_id must exist in the live pool
# ============================================================================

def _check_resources_exist(
    roadmap: Dict[str, Any],
    resource_by_id: Dict[str, Dict[str, Any]],
    report: ValidationReport,
) -> None:

    seen: set = set()

    for resource_id, location in _iter_resource_refs(roadmap):
        key = (resource_id, location)
        if key in seen:
            continue
        seen.add(key)

        if resource_id not in resource_by_id:
            report.add_error(
                "unknown_resource_id",
                f"resource_id '{resource_id}' does not exist in the live resource "
                "pool (resources.json). Either it was hallucinated, or "
                "resources.json changed since this roadmap was built.",
                location=location,
            )


# ============================================================================
# CHECK 2 — every referenced resource must match the roadmap's career
# ============================================================================

def _check_career_alignment(
    roadmap: Dict[str, Any],
    resource_by_id: Dict[str, Dict[str, Any]],
    report: ValidationReport,
) -> None:

    career = roadmap.get("career")

    if career is None:
        report.add_warning(
            "roadmap_missing_career",
            "roadmap['career'] is None, so career-appropriateness of "
            "resources could not be checked.",
            location="career",
        )
        return

    seen: set = set()

    for resource_id, location in _iter_resource_refs(roadmap):
        key = (resource_id, location)
        if key in seen:
            continue
        seen.add(key)

        resource = resource_by_id.get(resource_id)
        if resource is None:
            continue  # already reported by _check_resources_exist

        resource_careers = resource.get("career") or []
        if career not in resource_careers:
            report.add_error(
                "career_mismatch",
                f"resource_id '{resource_id}' belongs to career(s) "
                f"{resource_careers}, not the roadmap's career '{career}'.",
                location=location,
            )


# ============================================================================
# CHECK 3 — resources must be placed in a sensible section
# ============================================================================

def _check_resource_type_placement(
    roadmap: Dict[str, Any],
    resource_by_id: Dict[str, Dict[str, Any]],
    report: ValidationReport,
) -> None:

    for phase in roadmap.get("phases", []) or []:
        phase_label = f"phases[phase={phase.get('phase')}]"
        is_job_readiness_phase = (
            str(phase.get("title", "")).strip().lower() == JOB_READINESS_PHASE_TITLE
        )
        for resource_id in phase.get("resources", []) or []:
            resource = resource_by_id.get(resource_id)
            if resource is None:
                continue
            resource_type = resource.get("resource_type")
            if resource_type in PHASE_DISALLOWED_RESOURCE_TYPES and not is_job_readiness_phase:
                report.add_error(
                    "resource_type_wrong_section",
                    f"resource_id '{resource_id}' is a '{resource_type}' resource "
                    "but was placed inside a learning phase that isn't the "
                    "designated 'Job Readiness' phase; job resources belong "
                    "in job_preparation / recommended_jobs (or a phase "
                    "literally titled 'Job Readiness'), not a regular "
                    "learning phase.",
                    location=phase_label,
                )

    for resource_id in roadmap.get("certifications", []) or []:
        resource = resource_by_id.get(resource_id)
        if resource is None:
            continue
        resource_type = resource.get("resource_type")
        if resource_type != CERTIFICATION_RESOURCE_TYPE:
            report.add_error(
                "resource_type_wrong_section",
                f"resource_id '{resource_id}' is a '{resource_type}' resource "
                f"but was listed under certifications (expected "
                f"'{CERTIFICATION_RESOURCE_TYPE}').",
                location="certifications",
            )

    for section in ("job_preparation", "recommended_jobs"):
        for resource_id in roadmap.get(section, []) or []:
            resource = resource_by_id.get(resource_id)
            if resource is None:
                continue
            resource_type = resource.get("resource_type")
            if resource_type != JOB_RESOURCE_TYPE:
                report.add_error(
                    "resource_type_wrong_section",
                    f"resource_id '{resource_id}' is a '{resource_type}' resource "
                    f"but was listed under {section} (expected "
                    f"'{JOB_RESOURCE_TYPE}').",
                    location=section,
                )


# ============================================================================
# CHECK 4 — no resource should be double-booked across phases
# ============================================================================

def _check_no_duplicate_resource_across_phases(
    roadmap: Dict[str, Any],
    report: ValidationReport,
) -> None:

    phase_indices_by_resource: Dict[str, List[int]] = {}

    for index, phase in enumerate(roadmap.get("phases", []) or []):
        for resource_id in phase.get("resources", []) or []:
            phase_indices_by_resource.setdefault(resource_id, []).append(index)

    for resource_id, indices in phase_indices_by_resource.items():
        if len(indices) > 1:
            report.add_error(
                "duplicate_resource_across_phases",
                f"resource_id '{resource_id}' appears in {len(indices)} different "
                f"phases (phase indices {indices}); each resource should be "
                "scheduled in exactly one phase.",
                location="phases",
            )


# ============================================================================
# CHECK 5 — prerequisites must be satisfied by phase order
# ============================================================================

def _check_prerequisites_satisfied(
    roadmap: Dict[str, Any],
    resource_by_id: Dict[str, Dict[str, Any]],
    report: ValidationReport,
) -> None:

    first_phase_index = _first_appearance_phase_index(roadmap)

    for resource_id, resource_phase_index in first_phase_index.items():
        resource = resource_by_id.get(resource_id)
        if resource is None:
            continue  # already reported by _check_resources_exist

        for prereq_id in resource.get("prerequisites") or []:
            prereq_phase_index = first_phase_index.get(prereq_id)

            if prereq_phase_index is None:
                # Prerequisite isn't part of this roadmap at all — assumed
                # already satisfied (e.g. learner's level already passed
                # it). Not this validator's concern, same convention
                # planner.py uses when building dependency_edges.
                continue

            if prereq_phase_index > resource_phase_index:
                report.add_error(
                    "prerequisite_order_violation",
                    f"resource_id '{resource_id}' first appears in phase index "
                    f"{resource_phase_index}, but its prerequisite '{prereq_id}' "
                    f"first appears later, in phase index {prereq_phase_index}.",
                    location=f"phases[phase={resource_id}]",
                )


# ============================================================================
# CHECK 6 — timeline hours must be realistic
# ============================================================================

def _check_timeline_hours_realistic(
    roadmap: Dict[str, Any],
    report: ValidationReport,
) -> None:

    timeline = roadmap.get("timeline", {}) or {}
    hours_per_week = timeline.get("hours_per_week")
    weeks = timeline.get("weeks", []) or []

    if not isinstance(hours_per_week, (int, float)) or hours_per_week <= 0:
        report.add_error(
            "invalid_hours_per_week",
            f"timeline.hours_per_week must be a positive number, got {hours_per_week!r}.",
            location="timeline.hours_per_week",
        )
        hours_per_week = None

    running_total = 0.0

    for week in weeks:
        week_label = f"timeline.weeks[week={week.get('week')}]"
        hours = week.get("estimated_hours")

        if not isinstance(hours, (int, float)):
            report.add_error(
                "invalid_week_hours",
                f"estimated_hours must be numeric, got {hours!r}.",
                location=week_label,
            )
            continue

        if hours <= HOURS_TOLERANCE:
            report.add_error(
                "zero_hour_week",
                "This week schedules 0 hours of work. A week that carries no "
                "real workload should be merged into a neighbouring week "
                "rather than shown to the learner on its own.",
                location=week_label,
            )

        if hours_per_week is not None and hours > hours_per_week + HOURS_TOLERANCE:
            report.add_error(
                "hours_overrun",
                f"This week allocates {hours} hours, exceeding the learner's "
                f"hours_per_week budget of {hours_per_week}.",
                location=week_label,
            )

        running_total += float(hours)

    reported_total = timeline.get("total_estimated_hours")
    if isinstance(reported_total, (int, float)) and abs(reported_total - running_total) > 1e-3:
        report.add_error(
            "total_hours_mismatch",
            f"timeline.total_estimated_hours ({reported_total}) does not match "
            f"the sum of each week's estimated_hours ({running_total}).",
            location="timeline.total_estimated_hours",
        )


# ============================================================================
# CHECK 7 — overall duration sanity
# ============================================================================

def _check_total_duration_reasonable(
    roadmap: Dict[str, Any],
    report: ValidationReport,
) -> None:

    timeline = roadmap.get("timeline", {}) or {}
    total_weeks = timeline.get("total_duration_weeks")
    phases = roadmap.get("phases", []) or []

    if phases and total_weeks == 0:
        report.add_error(
            "empty_timeline_with_nonempty_plan",
            "The plan has phases with resources to learn, but the timeline "
            "schedules 0 weeks of work.",
            location="timeline.total_duration_weeks",
        )

    if isinstance(total_weeks, int) and total_weeks > MAX_REASONABLE_DURATION_WEEKS:
        report.add_warning(
            "roadmap_duration_long",
            f"This roadmap spans {total_weeks} weeks (~{total_weeks // 52} "
            f"year(s)), longer than the {MAX_REASONABLE_DURATION_WEEKS}-week "
            "sanity threshold. Not necessarily wrong, but worth a human glance.",
            location="timeline.total_duration_weeks",
        )


# ============================================================================
# CHECK 8 — critical/high-priority objectives must actually be addressed
# ============================================================================

def _check_learning_objectives_addressed(
    roadmap: Dict[str, Any],
    report: ValidationReport,
) -> None:

    objectives = roadmap.get("learning_objectives", []) or []
    phases = roadmap.get("phases", []) or []

    has_critical_objective = any(
        str(objective.get("priority", "")).lower() in CRITICAL_PRIORITIES
        for objective in objectives
        if isinstance(objective, dict)
    )

    has_any_phase_resources = any(
        phase.get("resources") for phase in phases if isinstance(phase, dict)
    )

    if has_critical_objective and not has_any_phase_resources:
        report.add_error(
            "critical_objective_unaddressed",
            "At least one learning_objective is Critical/High priority, but "
            "the plan's phases contain no resources at all.",
            location="phases",
        )


# ============================================================================
# CHECK 9 — resource difficulty shouldn't regress across phases (soft)
# ============================================================================

def _check_level_progression(
    roadmap: Dict[str, Any],
    resource_by_id: Dict[str, Dict[str, Any]],
    report: ValidationReport,
) -> None:

    phase_avg_levels: List[Tuple[int, float]] = []

    for index, phase in enumerate(roadmap.get("phases", []) or []):
        levels = [
            resource_by_id[resource_id]["level"]
            for resource_id in phase.get("resources", []) or []
            if resource_id in resource_by_id
            and isinstance(resource_by_id[resource_id].get("level"), (int, float))
        ]
        if levels:
            phase_avg_levels.append((index, sum(levels) / len(levels)))

    for (prev_index, prev_avg), (next_index, next_avg) in zip(
        phase_avg_levels, phase_avg_levels[1:]
    ):
        if prev_avg - next_avg > LEVEL_REGRESSION_WARNING_THRESHOLD:
            report.add_warning(
                "level_regression_across_phases",
                f"Average resource level drops from {prev_avg:.2f} in phase "
                f"index {prev_index} to {next_avg:.2f} in phase index "
                f"{next_index}. Phases are usually expected to hold steady "
                "or increase in difficulty as the learner progresses.",
                location=f"phases[{next_index}]",
            )


# ============================================================================
# ORCHESTRATION
# ============================================================================

def validate_roadmap(
    roadmap: Dict[str, Any],
    resources: Optional[Sequence[Dict[str, Any]]] = None,
    resources_path: Optional[str] = None,
    run_schema_check: bool = True,
) -> ValidationReport:
    """
    Run every semantic/business-rule check against the assembled roadmap
    and return a ValidationReport (never raises for business-rule
    problems — see validate_roadmap_or_raise() for a raising variant).

    If run_schema_check is True (default), schema.validate_roadmap_schema()
    is called first and allowed to raise SchemaValidationError directly —
    semantic validation assumes a structurally sound roadmap and cannot
    produce meaningful results otherwise.
    """

    if run_schema_check:
        validate_roadmap_schema(roadmap)

    if resources is None:
        resources = load_resources(resources_path)

    resource_by_id = _resource_index(resources)

    report = ValidationReport()

    _check_resources_exist(roadmap, resource_by_id, report)
    _check_career_alignment(roadmap, resource_by_id, report)
    _check_resource_type_placement(roadmap, resource_by_id, report)
    _check_no_duplicate_resource_across_phases(roadmap, report)
    _check_prerequisites_satisfied(roadmap, resource_by_id, report)
    _check_timeline_hours_realistic(roadmap, report)
    _check_total_duration_reasonable(roadmap, report)
    _check_learning_objectives_addressed(roadmap, report)
    _check_level_progression(roadmap, resource_by_id, report)

    return report


def validate_roadmap_or_raise(
    roadmap: Dict[str, Any],
    resources: Optional[Sequence[Dict[str, Any]]] = None,
    resources_path: Optional[str] = None,
    run_schema_check: bool = True,
) -> ValidationReport:
    """
    Convenience wrapper for callers (e.g. roadmap_engine.py) that just want
    a pass/fail gate: returns the ValidationReport if it has zero errors,
    otherwise raises RoadmapValidationError carrying the full report.
    """

    report = validate_roadmap(
        roadmap,
        resources=resources,
        resources_path=resources_path,
        run_schema_check=run_schema_check,
    )
    if not report.is_valid:
        raise RoadmapValidationError(report)
    return report


# ============================================================================
# SELF TEST (deterministic only — no network / no API key required)
# ============================================================================

def run_self_test() -> None:

    print("=" * 70)
    print("MINERVA ROADMAP RAG — VALIDATOR SELF TEST")
    print("=" * 70)

    from copy import deepcopy

    from planner import plan_from_profile
    from timeline import generate_timeline
    from schema import build_and_validate_roadmap

    resources = load_resources()
    resource_by_id = _resource_index(resources)

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
    roadmap = build_and_validate_roadmap(plan, timeline, profile=profile)

    assert roadmap["phases"], "Test setup requires a non-empty plan."

    # ------------------------------------------------------------------
    # 1. A real, unmodified roadmap out of the pipeline must validate
    #    with zero errors.
    # ------------------------------------------------------------------

    report = validate_roadmap(roadmap, resources=resources)
    assert report.is_valid, f"Unexpected errors on a clean roadmap:\n{report.summary()}"

    print("Clean roadmap has zero errors: PASS")

    # ------------------------------------------------------------------
    # 2. Unknown / hallucinated resource_id must be caught.
    # ------------------------------------------------------------------

    bad = deepcopy(roadmap)
    bad["phases"][0]["resources"].append("totally_invented_resource_999")

    report = validate_roadmap(bad, resources=resources)
    assert not report.is_valid
    assert any(issue.code == "unknown_resource_id" for issue in report.errors)

    print("Unknown resource_id rejection: PASS")

    # ------------------------------------------------------------------
    # 3. Career-mismatched resource must be caught.
    # ------------------------------------------------------------------

    cyber_only = next(
        r for r in resources
        if r.get("career") == ["cyber"]
    )

    bad = deepcopy(roadmap)
    bad["phases"][0]["resources"].append(cyber_only["resource_id"])

    report = validate_roadmap(bad, resources=resources)
    assert not report.is_valid
    assert any(issue.code == "career_mismatch" for issue in report.errors)

    print("Career mismatch rejection: PASS")

    # ------------------------------------------------------------------
    # 4. A job-type resource embedded in a learning phase must be caught.
    # ------------------------------------------------------------------

    dev_job = next(
        r for r in resources
        if "development" in (r.get("career") or []) and r["resource_type"] == "job"
    )

    bad = deepcopy(roadmap)
    bad["phases"][0]["resources"].append(dev_job["resource_id"])

    report = validate_roadmap(bad, resources=resources)
    assert not report.is_valid
    assert any(issue.code == "resource_type_wrong_section" for issue in report.errors)

    print("Job-in-phase placement rejection: PASS")

    # ------------------------------------------------------------------
    # 5. A course-type resource mislabelled as a certification must be
    #    caught.
    # ------------------------------------------------------------------

    dev_course = next(
        r for r in resources
        if "development" in (r.get("career") or []) and r["resource_type"] == "course"
    )

    bad = deepcopy(roadmap)
    bad["certifications"].append(dev_course["resource_id"])

    report = validate_roadmap(bad, resources=resources)
    assert not report.is_valid
    assert any(issue.code == "resource_type_wrong_section" for issue in report.errors)

    print("Mislabelled certification rejection: PASS")

    # ------------------------------------------------------------------
    # 6. A resource duplicated across two phases must be caught.
    # ------------------------------------------------------------------

    bad = deepcopy(roadmap)
    if len(bad["phases"]) >= 2 and bad["phases"][0]["resources"]:
        dup_id = bad["phases"][0]["resources"][0]
        bad["phases"][1]["resources"].append(dup_id)

        report = validate_roadmap(bad, resources=resources)
        assert not report.is_valid
        assert any(issue.code == "duplicate_resource_across_phases" for issue in report.errors)

        print("Duplicate resource across phases rejection: PASS")
    else:
        # Force a second phase to guarantee this path is always exercised.
        bad["phases"].append(deepcopy(bad["phases"][0]))
        report = validate_roadmap(bad, resources=resources)
        assert not report.is_valid
        assert any(issue.code == "duplicate_resource_across_phases" for issue in report.errors)

        print("Duplicate resource across phases rejection: PASS")

    # ------------------------------------------------------------------
    # 7. A prerequisite scheduled AFTER the resource that needs it must
    #    be caught.
    # ------------------------------------------------------------------

    prereq_resource = next(
        r for r in resources
        if "development" in (r.get("career") or []) and r.get("prerequisites")
    )
    prereq_id = prereq_resource["prerequisites"][0]

    bad = deepcopy(roadmap)
    # Put the dependent resource in phase 0, and its prerequisite in a
    # later phase — the exact violation this check exists to catch.
    bad["phases"][0]["resources"].append(prereq_resource["resource_id"])
    if len(bad["phases"]) < 2:
        bad["phases"].append({
            "phase": 99, "title": "Injected", "objectives": [], "resources": []
        })
    bad["phases"][-1]["resources"].append(prereq_id)

    report = validate_roadmap(bad, resources=resources)
    assert not report.is_valid
    assert any(issue.code == "prerequisite_order_violation" for issue in report.errors)

    print("Prerequisite order violation rejection: PASS")

    # ------------------------------------------------------------------
    # 8. A zero-hour week must be caught (business rule, not just
    #    structurally allowed the way schema.py treats it).
    # ------------------------------------------------------------------

    bad = deepcopy(roadmap)
    bad["timeline"]["weeks"].append({
        "week": len(bad["timeline"]["weeks"]) + 1,
        "focus": ["Job Readiness"],
        "resources": [],
        "estimated_hours": 0,
        "milestone": "Nothing scheduled",
    })
    bad["timeline"]["total_duration_weeks"] = len(bad["timeline"]["weeks"])

    report = validate_roadmap(bad, resources=resources)
    assert not report.is_valid
    assert any(issue.code == "zero_hour_week" for issue in report.errors)

    print("Zero-hour week rejection: PASS")

    # ------------------------------------------------------------------
    # 9. An hours-per-week overrun must be caught.
    # ------------------------------------------------------------------

    bad = deepcopy(roadmap)
    bad["timeline"]["weeks"][0]["estimated_hours"] = bad["timeline"]["hours_per_week"] + 5

    report = validate_roadmap(bad, resources=resources)
    assert not report.is_valid
    assert any(issue.code == "hours_overrun" for issue in report.errors)

    print("Hours-per-week overrun rejection: PASS")

    # ------------------------------------------------------------------
    # 10. total_estimated_hours not matching the weeks must be caught.
    # ------------------------------------------------------------------

    bad = deepcopy(roadmap)
    bad["timeline"]["total_estimated_hours"] = (
        bad["timeline"]["total_estimated_hours"] + 999
    )

    report = validate_roadmap(bad, resources=resources)
    assert not report.is_valid
    assert any(issue.code == "total_hours_mismatch" for issue in report.errors)

    print("Total-hours mismatch rejection: PASS")

    # ------------------------------------------------------------------
    # 11. A non-empty plan with an empty timeline must be caught.
    # ------------------------------------------------------------------

    bad = deepcopy(roadmap)
    bad["timeline"]["weeks"] = []
    bad["timeline"]["total_duration_weeks"] = 0
    bad["timeline"]["total_estimated_hours"] = 0

    report = validate_roadmap(bad, resources=resources)
    assert not report.is_valid
    assert any(issue.code == "empty_timeline_with_nonempty_plan" for issue in report.errors)

    print("Empty timeline with non-empty plan rejection: PASS")

    # ------------------------------------------------------------------
    # 12. A Critical-priority objective with no phase resources at all
    #     must be caught.
    # ------------------------------------------------------------------

    bad = deepcopy(roadmap)
    bad["learning_objectives"] = [{"skill": "Python", "priority": "Critical"}]
    for phase in bad["phases"]:
        phase["resources"] = []

    report = validate_roadmap(bad, resources=resources)
    assert not report.is_valid
    assert any(issue.code == "critical_objective_unaddressed" for issue in report.errors)

    print("Unaddressed critical objective rejection: PASS")

    # ------------------------------------------------------------------
    # 13. A very long roadmap should warn, not error.
    # ------------------------------------------------------------------

    warn_case = deepcopy(roadmap)
    warn_case["timeline"]["total_duration_weeks"] = MAX_REASONABLE_DURATION_WEEKS + 10

    # Skip the schema precondition here: bumping total_duration_weeks alone
    # (without generating 114 matching week entries) would fail schema.py's
    # own internal-consistency check first, which isn't what this specific
    # business-rule test is targeting.
    report = validate_roadmap(warn_case, resources=resources, run_schema_check=False)
    assert report.is_valid, "A long duration should only warn, never error."
    assert any(issue.code == "roadmap_duration_long" for issue in report.warnings)

    print("Long-duration warning (non-fatal): PASS")

    # ------------------------------------------------------------------
    # 14. validate_roadmap_or_raise() must raise RoadmapValidationError
    #     when the report has errors, and return quietly when it doesn't.
    # ------------------------------------------------------------------

    validate_roadmap_or_raise(roadmap, resources=resources)  # should not raise

    broken = deepcopy(roadmap)
    broken["phases"][0]["resources"].append("totally_invented_resource_999")

    try:
        validate_roadmap_or_raise(broken, resources=resources)
        raise AssertionError("RoadmapValidationError was not raised.")
    except RoadmapValidationError as exc:
        assert not exc.report.is_valid

    print("validate_roadmap_or_raise() pass/fail gate: PASS")

    print("=" * 70)
    print("ALL VALIDATOR TESTS PASSED")
    print("=" * 70)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    run_self_test()
