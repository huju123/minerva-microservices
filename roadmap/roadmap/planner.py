"""
MINERVA — Personalized Roadmap RAG
planner.py

Purpose:
    Turn a normalized Skill Gap Profile (adapter.py) + Level Rules
    (level_rules.py) + Retrieved Fixed Resources (retrieval.py) into an
    ordered, dependency-aware Learning Plan (WHAT to learn + in WHAT
    order), using a hybrid of deterministic rules and a Grok model call.

Architecture boundary:
    adapter.py      -> common profile
    level_rules.py   -> learner state / suitable resource levels
    retrieval.py     -> WHICH real resources match those rules
    planner.py       -> WHAT + ORDER learning plan   (this file)
    timeline.py      -> WHEN + HOW LONG (future)

IMPORTANT ARCHITECTURE RULES:
    - planner.py does NOT calculate skill gaps or levels.
    - planner.py does NOT retrieve resources. It only sequences resources
      already returned by retrieval.py.
    - planner.py does NOT invent resources, titles, or URLs. Every
      resource_id in the final plan is re-validated against the real
      candidate pool — the model is never trusted blindly.
    - planner.py does NOT build a timeline. No weeks, dates, or
      durations appear anywhere in its output. That is timeline.py's job.
    - planner.py combines deterministic priority/dependency rules with a
      Groq model call for phase organization, objective grouping, and
      course/practice/project sequencing.
    - If the Groq call fails or returns an invalid/hallucinated plan,
      planner.py falls back to a fully deterministic plan rather than
      crashing the pipeline.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from dotenv import load_dotenv

load_dotenv()
from .level_rules import LEVEL_PHASES, apply_profile_level_rules
from .retrieval import load_resources, retrieve_profile


# ============================================================================
# CONFIGURATION
# ============================================================================

# xAI's Groq API is OpenAI-compatible (chat completions).
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
DEFAULT_TIMEOUT_SECONDS = 60

PRIORITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "moderate": 2,
    "low": 3,
    "none": 4,
    None: 5,
}

RESOURCE_TYPE_ORDER = {
    "course": 0,
    "project": 1,
    "certification": 2,
    "job": 3,
}

# Phase name -> rank, reused from level_rules so "starting_level" /
# "target_level" summaries stay consistent with the rest of the pipeline.
PHASE_RANK = {name: rank for rank, name in LEVEL_PHASES.items()}


# ============================================================================
# ERRORS
# ============================================================================

class PlannerError(Exception):
    """Base error for planner.py."""


class PlannerValidationError(PlannerError):
    """
    Raised when a model-produced (or hand-built) plan fails structural
    or grounding validation — e.g. it references a resource_id that was
    never retrieved, or breaks a prerequisite ordering.
    """


# ============================================================================
# STEP 1 — BUILD PLANNER INPUT (deterministic)
# ============================================================================

def _skill_display_name(skill_id: str) -> str:
    """Human-readable label for a skill_id. Never used as a resource title."""

    return skill_id.replace("_", " ").replace("-", " ").title()


def _resource_summary(resource: Dict[str, Any]) -> Dict[str, Any]:
    """Slim, model-facing view of a real retrieved resource."""

    return {
        "resource_id": resource["resource_id"],
        "resource_type": resource.get("resource_type"),
        "title": resource.get("title"),
        "level": resource.get("level"),
        "difficulty": resource.get("difficulty"),
        "estimated_hours": resource.get("estimated_hours"),
        "prerequisites": list(resource.get("prerequisites") or []),
    }


def build_planner_input(
    profile: Dict[str, Any],
    retrieval_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Merge the adapter profile (priority, category, weight per skill),
    level_rules state (starting_phase, resource_strategy), and the real
    retrieved resources per skill into ONE deterministic context package
    that is safe to hand to the model.

    Only skills that are in a development_gap state AND have at least
    one retrieved candidate resource become "objectives". No-evidence
    skills, no-gap skills, and skills with zero matching resources are
    deliberately excluded — planner.py does not invent work for them.
    """

    if not isinstance(profile, dict):
        raise TypeError("profile must be a dictionary.")

    if not isinstance(retrieval_result, dict):
        raise TypeError("retrieval_result must be a dictionary.")

    skills_by_id = {
        skill["skill_id"]: skill
        for skill in profile.get("skills", [])
        if isinstance(skill, dict) and skill.get("skill_id")
    }

    level_rules_by_id = {
        rule["skill_id"]: rule
        for rule in profile.get("level_rules", [])
        if isinstance(rule, dict) and rule.get("skill_id")
    }

    objectives: List[Dict[str, Any]] = []
    resource_lookup: Dict[str, Dict[str, Any]] = {}

    for skill_result in retrieval_result.get("skills", []):

        skill_id = skill_result.get("skill_id")
        resources = skill_result.get("resources") or []

        if skill_result.get("state") != "development_gap":
            continue

        if not resources:
            continue

        source_skill = skills_by_id.get(skill_id, {})
        level_rule = level_rules_by_id.get(skill_id, {})

        candidate_resources = []

        for resource in resources:
            summary = _resource_summary(resource)
            candidate_resources.append(summary)
            # Last write wins; identical resource_ids are identical resources.
            resource_lookup[resource["resource_id"]] = resource

        objectives.append({
            "skill_id": skill_id,
            "skill_display_name": _skill_display_name(skill_id),
            "priority": str(source_skill.get("priority") or "none").lower(),
            "category": source_skill.get("category"),
            "starting_phase": level_rule.get("starting_phase"),
            "resource_strategy": skill_result.get("resource_strategy"),
            "candidate_resources": candidate_resources,
        })

    # Deterministic default ordering hint for the model: priority first,
    # then skill_id for stability. The model may still reorder to satisfy
    # prerequisites — validation, not this order, is what's enforced.
    objectives.sort(
        key=lambda obj: (
            PRIORITY_ORDER.get(obj["priority"], 5),
            obj["skill_id"],
        )
    )

    all_candidate_resource_ids = sorted(resource_lookup.keys())

    # Dependency edges restricted to the candidate pool. A prerequisite
    # that isn't in the pool is assumed already satisfied (e.g. the
    # learner's level already passed it) and is not the planner's concern.
    dependency_edges = {
        resource_id: [
            prereq
            for prereq in (resource.get("prerequisites") or [])
            if prereq in resource_lookup
        ]
        for resource_id, resource in resource_lookup.items()
    }

    return {
        "career": profile.get("career"),
        "goal": profile.get("goal"),
        "target_role": profile.get("target_role"),
        "objectives": objectives,
        "resource_lookup": resource_lookup,
        "all_candidate_resource_ids": all_candidate_resource_ids,
        "dependency_edges": dependency_edges,
    }


def _model_facing_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """Strip internal-only fields (full resource_lookup) before sending to Groq."""

    return {
        "career": context["career"],
        "goal": context["goal"],
        "target_role": context["target_role"],
        "objectives": context["objectives"],
    }


# ============================================================================
# STEP 2 — GROQ MODEL CALL
# ============================================================================

PLANNER_SYSTEM_PROMPT = """\
You are the planning stage of a deterministic learning-roadmap engine \
called MINERVA. You receive a learner's skill gaps, their current level \
per skill, and a fixed pool of REAL candidate resources already \
retrieved for them by an upstream retrieval system.

Your job is to produce an ordered, phase-based LEARNING PLAN: WHAT to \
learn and in WHAT ORDER. You do NOT produce a timeline.

STRICT RULES:
1. Use ONLY the resource_id values given in each objective's \
   "candidate_resources". Never invent a resource, title, URL, or \
   resource_id that was not provided.
2. Do not output any weeks, dates, durations, or timeline of any kind.
3. Respect each objective's "starting_phase" — do not prefer resources \
   whose level is below what the learner already has, when a more \
   suitable candidate exists.
4. Order phases using BOTH priority (critical > high > medium > low) \
   AND resource prerequisites. If resource A lists resource B in its \
   "prerequisites" and B is also selected somewhere in the plan, B must \
   appear in an earlier (or, at worst, the same, earlier-in-list) phase \
   than A.
5. Within a phase, prefer course -> project -> certification ordering \
   for a given skill.
6. Every resource_id must appear at most once in the entire plan.
7. Do not create a phase for an objective with no resources selected.
8. Place job-type resources, if any, only in a final "job readiness" \
   phase — never earlier.
9. Output STRICT JSON matching this schema and NOTHING else — no \
   markdown fences, no commentary, no extra keys:

{
  "goal": string or null,
  "starting_level": string or null,
  "target_level": string or null,
  "learning_objectives": [
    {"skill": string, "priority": string}
  ],
  "phases": [
    {
      "phase": integer,
      "title": string,
      "objectives": [string, ...],
      "resources": [resource_id, ...]
    }
  ],
  "certifications": [resource_id, ...],
  "job_preparation": [resource_id, ...],
  "recommended_jobs": [resource_id, ...]
}
"""


def _build_messages(context: Dict[str, Any]) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(_model_facing_context(context), indent=2),
        },
    ]


# gpt-oss-120b on Groq defaults to "medium" reasoning_effort, which burns
# output-token budget on hidden reasoning tokens before the model even
# starts writing the JSON answer. That's what was originally causing
# truncated timelines. BUT: this account's Groq tier caps requests at
# GROQ_TPM_SAFETY_CEILING tokens per minute (TPM) — a *combined*
# prompt + completion budget for a single request, confirmed by a live
# 413 "rate_limit_exceeded" (Limit 8000). So max_completion_tokens can't
# just be set high; it has to be sized down for large prompts so
# (prompt_tokens + max_completion_tokens) never exceeds the ceiling.
# Override GROQ_MAX_COMPLETION_TOKENS / GROQ_TPM_SAFETY_CEILING via env
# vars if your account is on a higher tier.
GROQ_TPM_SAFETY_CEILING = int(os.environ.get("GROQ_TPM_SAFETY_CEILING", "7500"))
DEFAULT_MAX_COMPLETION_TOKENS = int(os.environ.get("GROQ_MAX_COMPLETION_TOKENS", "3000"))
DEFAULT_REASONING_EFFORT = "low"

# A single request staying under GROQ_TPM_SAFETY_CEILING isn't enough on
# its own: the TPM quota is shared across ALL calls within the same
# rolling 60s window, so back-to-back calls (planner.py's call, then
# timeline.py's call moments later) can each be individually safe but
# still add up past the account's limit — exactly what a live 429
# ("Used 4814, Requested 4189", limit 8000) showed. Groq's error tells
# you exactly how long to wait before the window has room again, so
# retry once using that wait time before giving up and falling back to
# the deterministic path.
GROQ_RATE_LIMIT_MAX_RETRIES = int(os.environ.get("GROQ_RATE_LIMIT_MAX_RETRIES", "2"))
_RETRY_AFTER_PATTERN = re.compile(r"try again in ([\d.]+)s", re.IGNORECASE)


def _parse_retry_after_seconds(error_detail: str, default: float = 10.0) -> float:
    """Pull Groq's own suggested wait time out of a 429 error body, e.g.
    '...Please try again in 7.522499999s...'. Falls back to `default` if
    the message format ever changes and the pattern doesn't match."""
    match = _RETRY_AFTER_PATTERN.search(error_detail)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return default



def _estimate_prompt_tokens(messages: List[Dict[str, str]]) -> int:
    """Rough (~4 chars/token) prompt-size estimate. Not an exact tokenizer —
    just enough to keep a single request's prompt + completion budget under
    the account's TPM limit instead of risking a 413 rate_limit_exceeded."""
    total_chars = sum(len(m.get("content", "")) for m in messages)
    return max(1, total_chars // 4)


def call_groq(
    messages: List[Dict[str, str]],
    api_key: Optional[str] = None,
    model: str = DEFAULT_GROQ_MODEL,
    temperature: float = 0.2,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    max_completion_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS,
    reasoning_effort: Optional[str] = DEFAULT_REASONING_EFFORT,
) -> str:
    """
    Call the Groq (xAI) chat completions API and return the raw text
    of the model's reply.

    Requires an API key, either passed directly or via the GROQ_API_KEY
    environment variable. Raises PlannerError on any failure so callers
    can fall back to the deterministic planner instead of crashing.

    max_completion_tokens is set explicitly (rather than left to Groq's
    default) because the older `max_tokens` param is deprecated on Groq's
    OpenAI-compatible endpoint and, more importantly, an unset/too-small
    cap is a common silent cause of truncated JSON on long structured
    outputs. If the model still runs out of room, this raises a
    PlannerError that clearly says so (finish_reason == "length") instead
    of surfacing as a confusing "missing resource_id" validation failure
    two layers up.
    """

    resolved_key = api_key or os.environ.get("GROQ_API_KEY")

    if not resolved_key:
        raise PlannerError(
            "No Groq API key available. Set the GROQ_API_KEY environment "
    "variable or pass api_key explicitly."
        )

    # Clamp the requested completion budget so prompt + completion tokens
    # stay under the account's TPM ceiling, however large the caller asked
    # for. This is what actually prevents the 413 rate_limit_exceeded —
    # DEFAULT_MAX_COMPLETION_TOKENS alone isn't enough once the prompt
    # itself (e.g. a big resources list) eats into the same budget.
    estimated_prompt_tokens = _estimate_prompt_tokens(messages)
    safe_completion_budget = max(
        500, GROQ_TPM_SAFETY_CEILING - estimated_prompt_tokens
    )
    effective_max_completion_tokens = min(max_completion_tokens, safe_completion_budget)

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "max_completion_tokens": effective_max_completion_tokens,
    }
    if reasoning_effort is not None:
        payload["reasoning_effort"] = reasoning_effort

    request_kwargs = dict(
        url=GROQ_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {resolved_key}",
            "User-Agent": "minerva-roadmap-planner/1.0",
        },
        method="POST",
    )

    last_error: Optional[Exception] = None

    for attempt in range(GROQ_RATE_LIMIT_MAX_RETRIES + 1):
        request = urllib.request.Request(**request_kwargs)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
            break

        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last_error = PlannerError(f"Groq API error {exc.code}: {detail}")

            is_rate_limit = exc.code == 429 or "rate_limit_exceeded" in detail
            if is_rate_limit and attempt < GROQ_RATE_LIMIT_MAX_RETRIES:
                wait_seconds = _parse_retry_after_seconds(detail) + 0.5
                time.sleep(wait_seconds)
                continue

            raise last_error from exc

        except urllib.error.URLError as exc:
            raise PlannerError(f"Groq API request failed: {exc.reason}") from exc

    try:
        choice = body["choices"][0]
        content = choice["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise PlannerError(f"Unexpected Groq API response shape: {body}") from exc

    # If the model ran out of budget mid-JSON, finish_reason will be
    # "length" rather than "stop". Surface this immediately and clearly
    # instead of letting it fail downstream as a vague "missing resources"
    # validation error.
    if choice.get("finish_reason") == "length":
        raise PlannerError(
            "Groq response was truncated (finish_reason='length') before "
            "it finished writing the JSON — max_completion_tokens "
            f"({effective_max_completion_tokens}, clamped from requested "
            f"{max_completion_tokens} to stay under the "
            f"{GROQ_TPM_SAFETY_CEILING}-token TPM ceiling) was too low for "
            "this output. Either the prompt is too large for this account's "
            "rate limit, or GROQ_TPM_SAFETY_CEILING needs raising if your "
            "account is on a higher tier."
        )

    return content


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
        raise PlannerValidationError(
            f"Model did not return valid JSON: {exc}"
        ) from exc

    if not isinstance(parsed, dict):
        raise PlannerValidationError("Model JSON root must be an object.")

    return parsed


# ============================================================================
# STEP 3 — VALIDATE PLAN STRUCTURE (deterministic, no trust in the model)
# ============================================================================

REQUIRED_PLAN_KEYS = {"phases"}
REQUIRED_PHASE_KEYS = {"phase", "title", "objectives", "resources"}
FORBIDDEN_PLAN_SUBSTRINGS = (
    "week", "weeks", "day", "days", "date", "duration", "month", "months",
)


def _assert_no_timeline_leakage(plan: Dict[str, Any]) -> None:
    """planner.py must never emit timeline data — that belongs to timeline.py."""

    def _walk(node: Any) -> None:

        if isinstance(node, dict):
            for key, value in node.items():
                lowered = str(key).lower()
                if any(bad in lowered for bad in FORBIDDEN_PLAN_SUBSTRINGS):
                    raise PlannerValidationError(
                        f"Plan contains a timeline-like field '{key}'. "
                        "planner.py must not produce a timeline."
                    )
                _walk(value)

        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(plan)


def validate_plan_structure(
    plan: Dict[str, Any],
    context: Dict[str, Any],
) -> None:
    """
    Structural + grounding validation of a candidate plan.

    Raises PlannerValidationError on the first problem found. Checks:
      - required top-level / phase keys are present and well-typed
      - every referenced resource_id exists in the retrieved candidate pool
      - no resource_id is used more than once across the whole plan
      - prerequisite resources appear in an earlier-or-equal phase
      - no timeline-like fields were smuggled in
    """

    if not isinstance(plan, dict):
        raise PlannerValidationError("Plan must be a JSON object.")

    missing = REQUIRED_PLAN_KEYS - plan.keys()
    if missing:
        raise PlannerValidationError(f"Plan is missing required keys: {sorted(missing)}")

    phases = plan["phases"]
    if not isinstance(phases, list):
        raise PlannerValidationError("'phases' must be a list.")

    valid_ids = set(context["all_candidate_resource_ids"])
    resource_phase_index: Dict[str, Tuple[int, int]] = {}
    seen_resource_ids: set = set()

    for phase_index, phase in enumerate(phases):

        if not isinstance(phase, dict):
            raise PlannerValidationError(f"Phase {phase_index} is not an object.")

        missing_phase_keys = REQUIRED_PHASE_KEYS - phase.keys()
        if missing_phase_keys:
            raise PlannerValidationError(
                f"Phase {phase_index} is missing keys: {sorted(missing_phase_keys)}"
            )

        if not isinstance(phase["resources"], list):
            raise PlannerValidationError(f"Phase {phase_index} 'resources' must be a list.")

        for position, resource_id in enumerate(phase["resources"]):

            if resource_id not in valid_ids:
                raise PlannerValidationError(
                    f"Plan references resource_id '{resource_id}' which was never "
                    "retrieved. This is a hallucinated / invented resource."
                )

            if resource_id in seen_resource_ids:
                raise PlannerValidationError(
                    f"resource_id '{resource_id}' appears more than once in the plan."
                )

            seen_resource_ids.add(resource_id)
            resource_phase_index[resource_id] = (phase_index, position)

    # Extra resource_id lists outside "phases" must also be grounded.
        # Extra resource_id lists outside "phases" must also be grounded,
    # and must not contain internal duplicates (e.g. the model repeating
    # the same job/certification id twice in one list).
    for extra_key in ("certifications", "job_preparation", "recommended_jobs"):
        seen_in_extra_key: set = set()
        for resource_id in plan.get(extra_key) or []:
            if resource_id not in valid_ids:
                raise PlannerValidationError(
                    f"Plan references resource_id '{resource_id}' in '{extra_key}' "
                    "which was never retrieved."
                )
            if resource_id in seen_in_extra_key:
                raise PlannerValidationError(
                    f"resource_id '{resource_id}' appears more than once in "
                    f"'{extra_key}'."
                )
            seen_in_extra_key.add(resource_id)

    # Prerequisite ordering.
    for resource_id, (phase_index, position) in resource_phase_index.items():
        for prereq_id in context["dependency_edges"].get(resource_id, []):

            if prereq_id not in resource_phase_index:
                # Prerequisite wasn't selected into the plan at all — that's
                # allowed (e.g. deemed already satisfied); nothing to check.
                continue

            prereq_phase_index, prereq_position = resource_phase_index[prereq_id]

            out_of_order = (
                prereq_phase_index > phase_index
                or (
                    prereq_phase_index == phase_index
                    and prereq_position >= position
                )
            )

            if out_of_order:
                raise PlannerValidationError(
                    f"Prerequisite ordering violated: '{prereq_id}' must appear "
                    f"before '{resource_id}', but does not."
                )

    _assert_no_timeline_leakage(plan)


# ============================================================================
# STEP 4 — DETERMINISTIC FALLBACK PLANNER (no model, no network)
# ============================================================================

def _topological_order(
    resource_lookup: Dict[str, Dict[str, Any]],
    dependency_edges: Dict[str, List[str]],
    tie_break_key: Callable[[str], Tuple[Any, ...]],
) -> List[str]:
    """
    Kahn's algorithm topological sort over the candidate pool, choosing
    among "ready" resources using tie_break_key at each step so the
    result stays deterministic and priority/type aware.
    """

    remaining_deps = {rid: set(deps) for rid, deps in dependency_edges.items()}
    dependents: Dict[str, List[str]] = {rid: [] for rid in resource_lookup}

    for rid, deps in dependency_edges.items():
        for dep in deps:
            dependents.setdefault(dep, []).append(rid)

    ready = sorted(
        (rid for rid, deps in remaining_deps.items() if not deps),
        key=tie_break_key,
    )

    ordered: List[str] = []
    ready_set = set(ready)

    while ready:
        ready.sort(key=tie_break_key)
        current = ready.pop(0)
        ready_set.discard(current)
        ordered.append(current)

        for dependent in dependents.get(current, []):
            remaining_deps[dependent].discard(current)
            if not remaining_deps[dependent] and dependent not in ready_set:
                ready.append(dependent)
                ready_set.add(dependent)

    if len(ordered) != len(resource_lookup):
        # A cycle exists (shouldn't happen with curated data). Append the
        # remainder in a stable, priority-aware order rather than failing.
        leftover = sorted(set(resource_lookup) - set(ordered), key=tie_break_key)
        ordered.extend(leftover)

    return ordered


def deterministic_fallback_plan(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a fully deterministic plan with no model involved.

    Used when use_model=False, when no API key is configured, or as an
    automatic fallback if the Groq call fails or returns an invalid plan.
    """

    resource_lookup = context["resource_lookup"]
    objectives = context["objectives"]

    priority_by_skill = {obj["skill_id"]: obj["priority"] for obj in objectives}
    skill_of_resource: Dict[str, str] = {}

    for obj in objectives:
        for resource_summary in obj["candidate_resources"]:
            rid = resource_summary["resource_id"]
            # First (highest-priority, since objectives are pre-sorted)
            # objective to claim a shared resource keeps it.
            skill_of_resource.setdefault(rid, obj["skill_id"])

    def tie_break(resource_id: str) -> Tuple[Any, ...]:
        resource = resource_lookup[resource_id]
        skill_id = skill_of_resource.get(resource_id, "")
        return (
            PRIORITY_ORDER.get(priority_by_skill.get(skill_id), 5),
            RESOURCE_TYPE_ORDER.get(resource.get("resource_type"), 99),
            resource.get("level", 999),
            str(resource.get("title", "")).lower(),
            resource_id,
        )

    # Jobs are sequenced separately and always placed last.
    non_job_pool = {
        rid: res for rid, res in resource_lookup.items()
        if res.get("resource_type") != "job"
    }
    non_job_edges = {
        rid: [d for d in deps if d in non_job_pool]
        for rid, deps in context["dependency_edges"].items()
        if rid in non_job_pool
    }

    ordered_ids = _topological_order(non_job_pool, non_job_edges, tie_break)

    # Chunk the topological order into phases: a new phase starts whenever
    # the owning skill changes, so dependency-forced reordering (e.g. a
    # medium-priority prerequisite skill pulled earlier) becomes its own
    # clearly-labelled phase rather than being hidden inside another skill's.
    phases: List[Dict[str, Any]] = []
    current_skill: Optional[str] = None

    for resource_id in ordered_ids:
        skill_id = skill_of_resource.get(resource_id, "unspecified")

        if skill_id != current_skill:
            phases.append({
                "phase": len(phases) + 1,
                "title": f"{_skill_display_name(skill_id)} Development",
                "objectives": [
                    f"Close the {priority_by_skill.get(skill_id, 'relevant')} "
                    f"priority gap in {_skill_display_name(skill_id)}"
                ],
                "resources": [],
            })
            current_skill = skill_id

        phases[-1]["resources"].append(resource_id)

    # Final job-readiness phase, if any job resources were retrieved.
    job_ids = sorted(
        (rid for rid, res in resource_lookup.items() if res.get("resource_type") == "job"),
        key=lambda rid: str(resource_lookup[rid].get("title", "")).lower(),
    )

    if job_ids:
        phases.append({
            "phase": len(phases) + 1,
            "title": "Job Readiness",
            "objectives": ["Move from skills to job applications"],
            "resources": job_ids,
        })

    certifications = [
        rid for rid, res in resource_lookup.items()
        if res.get("resource_type") == "certification"
    ]

    starting_ranks = [
        PHASE_RANK.get(obj["starting_phase"])
        for obj in objectives
        if obj["starting_phase"] in PHASE_RANK
    ]
    starting_level = LEVEL_PHASES.get(min(starting_ranks)) if starting_ranks else None

    target_ranks = [
        resource_lookup[rid].get("level")
        for rid in resource_lookup
        if isinstance(resource_lookup[rid].get("level"), int)
    ]
    target_level = LEVEL_PHASES.get(max(target_ranks)) if target_ranks else None

    plan = {
        "goal": context.get("goal"),
        "starting_level": starting_level,
        "target_level": target_level,
        "learning_objectives": [
            {"skill": obj["skill_id"], "priority": obj["priority"]}
            for obj in objectives
        ],
        "phases": phases,
        "certifications": certifications,
        "job_preparation": job_ids,
        "recommended_jobs": job_ids,
    }

    return plan


def _empty_plan(context: Dict[str, Any]) -> Dict[str, Any]:
    """No development-gap objectives with candidate resources were found."""

    return {
        "goal": context.get("goal"),
        "starting_level": None,
        "target_level": None,
        "learning_objectives": [],
        "phases": [],
        "certifications": [],
        "job_preparation": [],
        "recommended_jobs": [],
        "_source": "empty",
        "_reason": "No development-gap skills with matching resources were found.",
    }


# ============================================================================
# STEP 5 — ORCHESTRATION
# ============================================================================

def plan_from_profile(
    profile: Dict[str, Any],
    resources: Optional[Sequence[Dict[str, Any]]] = None,
    resources_path: Optional[str] = None,
    use_model: bool = True,
    api_key: Optional[str] = None,
    model: str = DEFAULT_GROQ_MODEL,
    groq_client: Optional[Callable[..., str]] = None,
) -> Dict[str, Any]:
    """
    End-to-end planner entry point.

    Steps:
        1. Apply level_rules to the profile if not already applied.
        2. Load resources.json if resources were not supplied.
        3. Run retrieval.retrieve_profile to get REAL candidate resources.
        4. Build the deterministic planner input package.
        5. If use_model: call Groq, validate its output, and return it.
           On any failure (missing key, network error, invalid/hallucinated
           JSON), fall back to the deterministic planner instead of raising.
        6. If not use_model: return the deterministic plan directly.

    `groq_client` lets callers/tests inject a stand-in for call_groq
    (e.g. a stub returning a fixed JSON string) without hitting the network.
    """

    profile_with_rules = (
        profile if "level_rules" in profile else apply_profile_level_rules(profile)
    )

    if resources is None:
        resources = load_resources(resources_path)

    retrieval_result = retrieve_profile(profile_with_rules, resources)
    context = build_planner_input(profile_with_rules, retrieval_result)

    if not context["objectives"]:
        return _empty_plan(context)

    if not use_model:
        plan = deterministic_fallback_plan(context)
        plan["_source"] = "deterministic"
        return plan

    caller = groq_client or call_groq

    try:
        raw_text = caller(
            _build_messages(context),
            api_key=api_key,
            model=model,
        )
        plan = _parse_model_json(raw_text)
        validate_plan_structure(plan, context)
        plan["_source"] = "groq"
        return plan

    except PlannerError as exc:
        plan = deterministic_fallback_plan(context)
        plan["_source"] = "deterministic_fallback"
        plan["_fallback_reason"] = str(exc)
        return plan


# ============================================================================
# SELF TEST (deterministic only — no network / no API key required)
# ============================================================================

def run_self_test() -> None:

    print("=" * 70)
    print("MINERVA ROADMAP RAG — PLANNER SELF TEST")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Build a realistic profile using REAL resources.json
    # ------------------------------------------------------------------

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

    profile_with_rules = apply_profile_level_rules(profile)
    retrieval_result = retrieve_profile(profile_with_rules, resources)

    context = build_planner_input(profile_with_rules, retrieval_result)

    assert len(context["objectives"]) == 2
    assert context["objectives"][0]["skill_id"] == "python"  # critical sorts first
    assert context["all_candidate_resource_ids"]

    print("build_planner_input: PASS")

    # ------------------------------------------------------------------
    # Deterministic fallback plan must validate against its own context
    # ------------------------------------------------------------------

    plan = deterministic_fallback_plan(context)
    validate_plan_structure(plan, context)

    assert plan["phases"]
    assert plan["learning_objectives"][0]["skill"] == "python"

    all_planned_ids = {
        rid for phase in plan["phases"] for rid in phase["resources"]
    }
    assert all_planned_ids <= set(context["all_candidate_resource_ids"])

    print("deterministic_fallback_plan structure: PASS")
    print("deterministic_fallback_plan validation: PASS")

    # ------------------------------------------------------------------
    # Hallucinated resource_id must be rejected
    # ------------------------------------------------------------------

    bad_plan = deepcopy(plan)
    bad_plan["phases"][0]["resources"].append("totally_invented_resource_999")

    try:
        validate_plan_structure(bad_plan, context)
        raise AssertionError("Hallucinated resource_id was not caught.")
    except PlannerValidationError:
        pass

    print("Hallucinated resource_id rejection: PASS")

    # ------------------------------------------------------------------
    # Duplicate resource_id must be rejected
    # ------------------------------------------------------------------

    dup_plan = deepcopy(plan)
    if len(dup_plan["phases"]) >= 1 and dup_plan["phases"][0]["resources"]:
        dup_plan["phases"][-1]["resources"].append(
            dup_plan["phases"][0]["resources"][0]
        )

        try:
            validate_plan_structure(dup_plan, context)
            raise AssertionError("Duplicate resource_id was not caught.")
        except PlannerValidationError:
            pass

        print("Duplicate resource_id rejection: PASS")

    # ------------------------------------------------------------------
    # Timeline leakage must be rejected
    # ------------------------------------------------------------------

    timeline_plan = deepcopy(plan)
    timeline_plan["phases"][0]["duration_weeks"] = 2

    try:
        validate_plan_structure(timeline_plan, context)
        raise AssertionError("Timeline leakage was not caught.")
    except PlannerValidationError:
        pass

    print("Timeline leakage rejection: PASS")

    # ------------------------------------------------------------------
    # Prerequisite ordering violation must be rejected
    # ------------------------------------------------------------------

    for rid, deps in context["dependency_edges"].items():
        if deps:
            broken_plan = {
                "phases": [
                    {
                        "phase": 1,
                        "title": "Broken order",
                        "objectives": ["test"],
                        # dependent resource placed BEFORE its prerequisite
                        "resources": [rid, deps[0]],
                    }
                ],
                "certifications": [],
                "job_preparation": [],
                "recommended_jobs": [],
            }

            try:
                validate_plan_structure(broken_plan, context)
                raise AssertionError(
                    "Prerequisite ordering violation was not caught."
                )
            except PlannerValidationError:
                pass

            print("Prerequisite ordering violation rejection: PASS")
            break

    # ------------------------------------------------------------------
    # plan_from_profile with use_model=False (no network needed)
    # ------------------------------------------------------------------

    result = plan_from_profile(profile, resources=resources, use_model=False)
    assert result["_source"] == "deterministic"
    validate_plan_structure(result, context)

    print("plan_from_profile(use_model=False): PASS")

    # ------------------------------------------------------------------
    # plan_from_profile with a stubbed GroQ client (no network needed)
    # ------------------------------------------------------------------

    def _stub_groq_client(messages, api_key=None, model=None, **kwargs):
        # Echo back a trivially valid, empty-but-well-formed plan.
        return json.dumps({
            "goal": None,
            "starting_level": None,
            "target_level": None,
            "learning_objectives": [],
            "phases": [],
            "certifications": [],
            "job_preparation": [],
            "recommended_jobs": [],
        })

    stubbed = plan_from_profile(
        profile,
        resources=resources,
        use_model=True,
        groq_client=_stub_groq_client,
    )
    assert stubbed["_source"] == "groq"

    print("plan_from_profile(stubbed groq_client): PASS")

    # ------------------------------------------------------------------
    # plan_from_profile falls back cleanly when the model errors out
    # ------------------------------------------------------------------

    def _failing_groq_client(messages, api_key=None, model=None, **kwargs):
        raise PlannerError("simulated network failure")

    fallback = plan_from_profile(
        profile,
        resources=resources,
        use_model=True,
        groq_client=_failing_groq_client,
    )
    assert fallback["_source"] == "deterministic_fallback"
    assert "simulated network failure" in fallback["_fallback_reason"]

    print("plan_from_profile(failing groq_client -> fallback): PASS")

    # ------------------------------------------------------------------
    # No missing XAI_API_KEY should ever crash the pipeline
    # ------------------------------------------------------------------

    os.environ.pop("GROQ_API_KEY", None)

    no_key_result = plan_from_profile(profile, resources=resources, use_model=True)
    assert no_key_result["_source"] == "deterministic_fallback"

    print("plan_from_profile(no API key -> graceful fallback): PASS")

    print("=" * 70)
    print("ALL PLANNER TESTS PASSED")
    print("=" * 70)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    run_self_test()
