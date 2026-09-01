"""
MINERVA — Personalized Roadmap RAG
retrieval.py

Purpose:
    Retrieve grounded, deterministic learning resources from the frozen
    resources.json dataset using a normalized common profile and the
    deterministic rules in level_rules.py.

Architecture boundary:
    adapter.py      -> common profile
    level_rules.py  -> learner state / suitable resource levels
    retrieval.py    -> WHICH REAL resources match those rules
    planner.py      -> future LLM-based planning/personalization
    timeline.py     -> future sequencing

IMPORTANT:
    - Journey outputs remain the source of truth.
    - This module does NOT recalculate skill levels or gaps.
    - This module does NOT select a career.
    - This module does NOT call an LLM or external API.
    - This module only returns resources that exist in resources.json.
    - No-evidence is never converted into a development gap.
    - Original resource records are never modified.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .level_rules import apply_level_rule, validate_level_rule_result


# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent

DEFAULT_RESOURCES_FILE = BASE_DIR / "resources.json"


PRIORITY_ORDER = {
    "high": 0,
    "medium": 1,
    "moderate": 1,
    "low": 2,
    "none": 3,
    None: 4,
}


# ============================================================================
# RESOURCE LOADING
# ============================================================================

def load_resources(
    path: Optional[str | Path] = None,
) -> List[Dict[str, Any]]:
    """
    Load the frozen resources.json dataset.

    No resource is created or modified.
    """

    resource_path = (
        Path(path)
        if path is not None
        else DEFAULT_RESOURCES_FILE
    )

    with resource_path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError(
            "resources.json root must be a dictionary."
        )

    resources = data.get("resources")

    if not isinstance(resources, list):
        raise ValueError(
            "resources.json must contain a 'resources' list."
        )

    seen_ids = set()

    for resource in resources:

        if not isinstance(resource, dict):
            raise ValueError(
                "Every resource must be a dictionary."
            )

        resource_id = resource.get(
            "resource_id"
        )

        if not resource_id:
            raise ValueError(
                "Every resource must have a resource_id."
            )

        if resource_id in seen_ids:
            raise ValueError(
                f"Duplicate resource_id found: {resource_id}"
            )

        seen_ids.add(resource_id)

    return deepcopy(resources)


# ============================================================================
# NORMALIZATION HELPERS
# ============================================================================

def _normalize_careers(
    value: Any,
) -> List[str]:
    """
    Normalize resource career field.

    resources.json currently stores career as a list,
    but a string is also safely supported.
    """

    if value is None:
        return []

    if isinstance(value, str):
        return [value]

    if isinstance(value, list):
        return [
            str(item)
            for item in value
        ]

    raise TypeError(
        "Resource career must be a string, "
        "list, or None."
    )


def _skill_level_for_resource(
    resource: Dict[str, Any],
    skill_id: str,
) -> Optional[int]:
    """
    Get the skill-specific level from:

        resource["skills"][skill_id]

    If the skill exists but its value is invalid,
    raise an error rather than guessing.
    """

    skills = resource.get("skills")

    if not isinstance(skills, dict):
        return None

    value = skills.get(skill_id)

    if value is None:
        return None

    if isinstance(value, bool):
        raise ValueError(
            f"Resource {resource.get('resource_id')} "
            f"has invalid skill level for '{skill_id}'."
        )

    if not isinstance(value, int):
        raise ValueError(
            f"Resource {resource.get('resource_id')} "
            f"has invalid skill level for '{skill_id}'."
        )

    return value


# ============================================================================
# CAREER MATCHING
# ============================================================================

def _resource_matches_career(
    resource: Dict[str, Any],
    career: Optional[str],
) -> bool:
    """
    Match resource career only when learner career is known.

    If career is None, no career is invented and the resource
    is not rejected solely because career information is unavailable.
    """

    if career is None:
        return True

    careers = _normalize_careers(
        resource.get("career")
    )

    return career in careers


# ============================================================================
# LEVEL MATCHING
# ============================================================================

def _resource_matches_level(
    resource: Dict[str, Any],
    skill_id: str,
    allowed_levels: Sequence[int],
) -> bool:
    """
    Check deterministic resource-level suitability.

    Primary signal:
        resource["level"]

    Secondary check:
        resource["skills"][skill_id]

    Both must be compatible when the skill-specific level exists.
    """

    resource_level = resource.get("level")

    if isinstance(resource_level, bool):
        return False

    if not isinstance(resource_level, int):
        return False

    if resource_level not in allowed_levels:
        return False

    skill_level = _skill_level_for_resource(
        resource,
        skill_id,
    )

    if skill_level is not None:

        if skill_level not in allowed_levels:
            return False

    return True


# ============================================================================
# DETERMINISTIC RANKING
# ============================================================================

def _resource_type_rank(
    resource_type: Any,
) -> int:
    """
    Deterministic type ordering.

    This does NOT create a timeline.
    Timeline planning belongs to timeline.py.
    """

    return {
        "course": 0,
        "project": 1,
        "certification": 2,
        "job": 3,
    }.get(
        resource_type,
        99,
    )


def _resource_sort_key(
    resource: Dict[str, Any],
    skill: Dict[str, Any],
) -> Tuple[Any, ...]:
    """
    Deterministic ranking key.

    Lower suitable levels are preferred first so that a learner
    does not immediately jump to a more advanced resource.
    """

    priority = str(
        skill.get(
            "priority",
            "none",
        )
    ).lower()

    allowed_levels = skill.get(
        "_allowed_levels",
        [],
    )

    resource_level = resource.get(
        "level",
        999,
    )

    if resource_level in allowed_levels:

        level_rank = allowed_levels.index(
            resource_level
        )

    else:

        level_rank = 999

    return (
        level_rank,

        PRIORITY_ORDER.get(
            priority,
            4,
        ),

        _resource_type_rank(
            resource.get(
                "resource_type"
            )
        ),

        str(
            resource.get(
                "title",
                "",
            )
        ).lower(),

        str(
            resource.get(
                "resource_id",
                "",
            )
        ),
    )


# ============================================================================
# SINGLE-SKILL RETRIEVAL
# ============================================================================

def retrieve_for_skill(
    skill: Dict[str, Any],
    resources: Sequence[Dict[str, Any]],
    career: Optional[str] = None,
    max_resources: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Retrieve grounded resources for one normalized skill.

    Flow:

        skill
          ↓
        level_rules.py
          ↓
        state
          ↓
        canonical skill_id
          ↓
        career filter
          ↓
        level filter
          ↓
        deterministic ranking
          ↓
        real resources
    """

    if not isinstance(skill, dict):
        raise TypeError(
            "skill must be a dictionary."
        )

    skill_id = skill.get(
        "skill_id"
    )

    if not skill_id:
        raise ValueError(
            "Skill is missing 'skill_id'."
        )

    # ---------------------------------------------------------------
    # Apply deterministic level rules
    # ---------------------------------------------------------------

    level_result = apply_level_rule(
        skill
    )

    validate_level_rule_result(
        level_result
    )

    state = level_result[
        "state"
    ]

    strategy = level_result[
        "resource_strategy"
    ]

    allowed_levels = list(
        level_result[
            "resource_levels"
        ]
    )

    result = {
        "skill_id": skill_id,

        "state": state,

        "resource_strategy": strategy,

        "resources": [],

        "resource_count": 0,
    }

    # ---------------------------------------------------------------
    # States that should NOT retrieve development resources
    # ---------------------------------------------------------------

    non_development_states = {
        "no_evidence",
        "unknown_level",
        "known_current_unknown_target",
        "no_development_gap",
        "invalid_progression_range",
    }

    if state in non_development_states:
        return result

    if not allowed_levels:
        return result

    # ---------------------------------------------------------------
    # Find matching resources
    # ---------------------------------------------------------------

    candidates = []

    for resource in resources:

        if not isinstance(
            resource,
            dict,
        ):
            continue

        # -----------------------------------------------------------
        # Career filter
        # -----------------------------------------------------------

        if not _resource_matches_career(
            resource,
            career,
        ):
            continue

        # -----------------------------------------------------------
        # Exact canonical skill matching
        # -----------------------------------------------------------

        resource_skills = resource.get(
            "skills"
        )

        if not isinstance(
            resource_skills,
            dict,
        ):
            continue

        if skill_id not in resource_skills:
            continue

        # -----------------------------------------------------------
        # Level suitability
        # -----------------------------------------------------------

        if not _resource_matches_level(
            resource,
            skill_id,
            allowed_levels,
        ):
            continue

        # -----------------------------------------------------------
        # Preserve original resource data
        # -----------------------------------------------------------

        candidates.append(
            deepcopy(resource)
        )

    # ---------------------------------------------------------------
    # Deterministic ranking
    # ---------------------------------------------------------------

    sort_skill = dict(skill)

    sort_skill[
        "_allowed_levels"
    ] = allowed_levels

    candidates.sort(
        key=lambda item:
            _resource_sort_key(
                item,
                sort_skill,
            )
    )

    # ---------------------------------------------------------------
    # Optional resource limit
    # ---------------------------------------------------------------

    if max_resources is not None:

        if isinstance(
            max_resources,
            bool,
        ):
            raise TypeError(
                "max_resources must be "
                "an integer or None."
            )

        if not isinstance(
            max_resources,
            int,
        ):
            raise TypeError(
                "max_resources must be "
                "an integer or None."
            )

        if max_resources < 0:
            raise ValueError(
                "max_resources cannot be negative."
            )

        candidates = candidates[
            :max_resources
        ]

    result[
        "resources"
    ] = candidates

    result[
        "resource_count"
    ] = len(
        candidates
    )

    return result


# ============================================================================
# PROFILE RETRIEVAL
# ============================================================================

def retrieve_profile(
    profile: Dict[str, Any],
    resources: Sequence[Dict[str, Any]],
    max_resources_per_skill: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Retrieve resources for all skills in a normalized common profile.

    The profile itself is never modified.
    """

    if not isinstance(
        profile,
        dict,
    ):
        raise TypeError(
            "profile must be a dictionary."
        )

    skills = profile.get(
        "skills"
    )

    if not isinstance(
        skills,
        list,
    ):
        raise ValueError(
            "Profile is missing a valid "
            "'skills' list."
        )

    career = profile.get(
        "career"
    )

    by_skill = []

    all_resource_ids = set()

    for skill in skills:

        skill_result = retrieve_for_skill(
            skill=skill,
            resources=resources,
            career=career,
            max_resources=max_resources_per_skill,
        )

        for resource in skill_result[
            "resources"
        ]:

            all_resource_ids.add(
                resource[
                    "resource_id"
                ]
            )

        by_skill.append(
            skill_result
        )

    return {
        "career": career,

        "skills": by_skill,

        "resource_count": len(
            all_resource_ids
        ),
    }


# ============================================================================
# SOURCE-GROUNDING VALIDATION
# ============================================================================

def _assert_resource_ids_exist(
    retrieved: Dict[str, Any],
    source_resources: Sequence[Dict[str, Any]],
) -> None:
    """
    Verify that every returned resource actually exists
    in resources.json.
    """

    source_ids = {
        resource[
            "resource_id"
        ]
        for resource in source_resources
    }

    # Single-skill result
    if "resources" in retrieved:

        resource_groups = [
            retrieved
        ]

    # Profile result
    else:

        resource_groups = retrieved[
            "skills"
        ]

    for group in resource_groups:

        for resource in group[
            "resources"
        ]:

            assert (
                resource[
                    "resource_id"
                ]
                in source_ids
            )


# ============================================================================
# SELF TEST
# ============================================================================

def run_self_test() -> None:
    """
    Standalone deterministic retrieval tests.

    Uses the REAL resources.json.
    """

    print("=" * 70)

    print(
        "MINERVA ROADMAP RAG — RETRIEVAL SELF TEST"
    )

    print("=" * 70)

    # ---------------------------------------------------------------
    # TEST 1 — Load resources
    # ---------------------------------------------------------------

    resources = load_resources()

    assert len(resources) > 0

    print(
        "Resource dataset load: PASS"
    )

    # ---------------------------------------------------------------
    # TEST 2 — Exact canonical skill matching
    # ---------------------------------------------------------------

    skill = {
        "skill_id":
            "machine_learning_reasoning",

        "current_level": 3,

        "target_level": 4,

        "gap": 1,

        "gap_label":
            "Low Gap",

        "priority":
            "High",

        "category":
            "core",

        "weight":
            1.0,

        "confidence":
            1.0,

        "evidence_status":
            "measured",
    }

    result = retrieve_for_skill(
        skill,
        resources,
        career="ai",
    )

    assert (
        result["state"]
        == "development_gap"
    )

    assert result[
        "resources"
    ]

    assert all(
        "machine_learning_reasoning"
        in resource["skills"]
        for resource
        in result["resources"]
    )

    print(
        "Exact canonical skill matching: PASS"
    )

    # ---------------------------------------------------------------
    # TEST 3 — Level suitability
    # ---------------------------------------------------------------

    assert all(
        resource["level"]
        in [3, 4]
        for resource
        in result["resources"]
    )

    print(
        "Level suitability filtering: PASS"
    )

    # ---------------------------------------------------------------
    # TEST 4 — Career filtering
    # ---------------------------------------------------------------

    assert all(
        "ai"
        in resource["career"]
        for resource
        in result["resources"]
    )

    print(
        "Career filtering: PASS"
    )

    # ---------------------------------------------------------------
    # TEST 5 — No evidence
    # ---------------------------------------------------------------

    no_evidence = dict(
        skill
    )

    no_evidence.update({

        "skill_id":
            "python",

        "current_level":
            None,

        "target_level":
            4,

        "gap":
            None,

        "gap_label":
            "No Evidence",

        "priority":
            "None",

        "confidence":
            0.0,

        "evidence_status":
            "no_evidence",
    })

    no_evidence_result = (
        retrieve_for_skill(
            no_evidence,
            resources,
            career="development",
        )
    )

    assert (
        no_evidence_result[
            "state"
        ]
        == "no_evidence"
    )

    assert (
        no_evidence_result[
            "resource_strategy"
        ]
        == "explore_validate"
    )

    assert (
        no_evidence_result[
            "resources"
        ]
        == []
    )

    print(
        "No-evidence protection: PASS"
    )

    # ---------------------------------------------------------------
    # TEST 6 — Strength / no gap
    # ---------------------------------------------------------------

    strength = dict(
        skill
    )

    strength.update({

        "current_level":
            4,

        "target_level":
            4,

        "gap":
            0,

        "gap_label":
            "No Gap",

        "priority":
            "None",
    })

    strength_result = (
        retrieve_for_skill(
            strength,
            resources,
            career="ai",
        )
    )

    assert (
        strength_result[
            "state"
        ]
        == "no_development_gap"
    )

    assert (
        strength_result[
            "resources"
        ]
        == []
    )

    print(
        "Strength/no-gap handling: PASS"
    )

    # ---------------------------------------------------------------
    # TEST 7 — No invented resources
    # ---------------------------------------------------------------

    _assert_resource_ids_exist(
        result,
        resources,
    )

    print(
        "No invented resource IDs: PASS"
    )

    # ---------------------------------------------------------------
    # TEST 8 — Deterministic ordering
    # ---------------------------------------------------------------

    result_again = (
        retrieve_for_skill(
            skill,
            resources,
            career="ai",
        )
    )

    ids_a = [
        resource[
            "resource_id"
        ]
        for resource
        in result["resources"]
    ]

    ids_b = [
        resource[
            "resource_id"
        ]
        for resource
        in result_again["resources"]
    ]

    assert ids_a == ids_b

    print(
        "Deterministic ordering: PASS"
    )

    # ---------------------------------------------------------------
    # TEST 9 — Common profile integration
    # ---------------------------------------------------------------

    profile = {

        "journey":
            "career-in-mind",

        "career":
            "ai",

        "target_role":
            None,

        "current_experience_level":
            None,

        "goal":
            None,

        "weekly_hours":
            None,

        "skills": [
            skill,
            no_evidence,
        ],

        "strengths":
            [],

        "weak_areas":
            [],

        "preferences":
            {},
    }

    profile_result = (
        retrieve_profile(
            profile,
            resources,
        )
    )

    assert (
        len(
            profile_result[
                "skills"
            ]
        )
        == 2
    )

    assert (
        profile_result[
            "skills"
        ][0][
            "resources"
        ]
    )

    assert (
        profile_result[
            "skills"
        ][1][
            "resources"
        ]
        == []
    )

    _assert_resource_ids_exist(
        profile_result,
        resources,
    )

    print(
        "Common profile integration: PASS"
    )

    # ---------------------------------------------------------------
    # FINAL
    # ---------------------------------------------------------------

    print("=" * 70)

    print(
        "ALL RETRIEVAL TESTS PASSED"
    )

    print("=" * 70)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    run_self_test()
