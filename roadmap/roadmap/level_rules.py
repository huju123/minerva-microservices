"""
MINERVA — Personalized Roadmap RAG
level_rules.py

Purpose:
    Apply deterministic level rules to a normalized skill profile.

IMPORTANT:
    - Does NOT calculate skill gaps.
    - Does NOT calculate current levels.
    - Does NOT calculate target levels.
    - Does NOT select careers.
    - Does NOT retrieve resources.
    - Does NOT use an LLM.
    - Does NOT invent missing information.

Input:
    Common skill records produced by adapter.py.

Output:
    Deterministic learning/level strategy that retrieval.py
    can later use to filter resources.json.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# ============================================================================
# CONFIGURATION
# ============================================================================

# MINERVA currently uses levels up to 4 in the career skill matrix.
MIN_LEVEL = 1
MAX_LEVEL = 4


# User skill level -> roadmap starting phase
LEVEL_PHASES = {
    1: "foundation",
    2: "beginner",
    3: "intermediate",
    4: "advanced",
}


# Resource level -> acceptable difficulty labels.
#
# Resources.json contains both "level" and "difficulty".
# The resource's explicit level will remain the primary signal.
LEVEL_DIFFICULTIES = {
    1: ["beginner"],
    2: ["beginner"],
    3: ["intermediate"],
    4: ["advanced"],
}


# ============================================================================
# BASIC HELPERS
# ============================================================================

def _validate_level(
    value: Any,
    field_name: str,
    allow_none: bool = True,
) -> None:
    """Validate a skill level."""

    if value is None:

        if allow_none:
            return

        raise ValueError(
            f"{field_name} cannot be None."
        )

    if isinstance(value, bool):
        raise ValueError(
            f"{field_name} must be an integer."
        )

    if not isinstance(value, int):
        raise ValueError(
            f"{field_name} must be an integer, "
            f"got {type(value).__name__}."
        )

    if value < MIN_LEVEL:
        raise ValueError(
            f"{field_name} cannot be below {MIN_LEVEL}."
        )


def _phase_for_level(
    level: int,
) -> str:
    """
    Convert a current skill level into a deterministic phase.
    """

    if level <= 1:
        return "foundation"

    if level == 2:
        return "beginner"

    if level == 3:
        return "intermediate"

    return "advanced"


def _difficulty_for_level(
    level: int,
) -> List[str]:
    """
    Return expected resource difficulty for a resource level.
    """

    if level in LEVEL_DIFFICULTIES:
        return list(
            LEVEL_DIFFICULTIES[level]
        )

    if level <= 1:
        return ["beginner"]

    if level == 2:
        return ["beginner"]

    if level == 3:
        return ["intermediate"]

    return ["advanced"]


# ============================================================================
# SINGLE SKILL RULE
# ============================================================================

def apply_level_rule(
    skill: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Apply deterministic level rules to ONE normalized skill.

    Expected input fields from adapter.py:

        skill_id
        current_level
        target_level
        gap
        gap_label
        priority
        category
        weight
        confidence
        evidence_status

    Returns a new dictionary.

    Original values are never recalculated or modified.
    """

    if not isinstance(skill, dict):
        raise TypeError(
            "Skill must be a dictionary."
        )

    skill_id = skill.get("skill_id")

    if not skill_id:
        raise ValueError(
            "Skill is missing 'skill_id'."
        )

    current_level = skill.get(
        "current_level"
    )

    target_level = skill.get(
        "target_level"
    )

    gap = skill.get("gap")

    evidence_status = (
        skill.get("evidence_status")
    )

    _validate_level(
        current_level,
        "current_level",
        allow_none=True,
    )

    _validate_level(
        target_level,
        "target_level",
        allow_none=True,
    )

    # ========================================================================
    # CASE 1 — NO EVIDENCE
    # ========================================================================

    if evidence_status == "no_evidence":

        return {
            "skill_id": skill_id,

            "state": "no_evidence",

            "starting_phase": "validation",

            "resource_strategy":
                "explore_validate",

            "resource_levels": [],

            "resource_difficulties": [],

            "development_required": False,

            "progression_required": False,

            "reason":
                "Current skill level is unknown; "
                "do not treat missing evidence as a skill gap.",
        }

    # ========================================================================
    # CASE 2 — CURRENT LEVEL UNKNOWN BUT NOT EXPLICITLY NO-EVIDENCE
    # ========================================================================

    if current_level is None:

        return {
            "skill_id": skill_id,

            "state": "unknown_level",

            "starting_phase": "validation",

            "resource_strategy":
                "explore_validate",

            "resource_levels": [],

            "resource_difficulties": [],

            "development_required": False,

            "progression_required": False,

            "reason":
                "Current level is unavailable; "
                "do not infer a level.",
        }

    # ========================================================================
    # CASE 3 — TARGET LEVEL UNKNOWN
    # ========================================================================

    if target_level is None:

        return {
            "skill_id": skill_id,

            "state": "known_current_unknown_target",

            "starting_phase":
                _phase_for_level(
                    current_level
                ),

            "resource_strategy":
                "maintain_or_validate",

            "resource_levels": [],

            "resource_difficulties": [],

            "development_required": False,

            "progression_required": False,

            "reason":
                "Target level is unavailable; "
                "do not invent a target.",
        }

    # ========================================================================
    # CASE 4 — NO DEVELOPMENT GAP
    # ========================================================================

    if gap == 0 or current_level >= target_level:

        return {
            "skill_id": skill_id,

            "state": "no_development_gap",

            "starting_phase":
                _phase_for_level(
                    current_level
                ),

            "resource_strategy":
                "maintain_or_leverage",

            "resource_levels": [],

            "resource_difficulties": [],

            "development_required": False,

            "progression_required": False,

            "reason":
                "Current level meets or exceeds "
                "the target level.",
        }

    # ========================================================================
    # CASE 5 — VERIFIED DEVELOPMENT GAP
    # ========================================================================

    # We intentionally use the journey-provided gap.
    #
    # We DO NOT calculate:
    #
    #     target_level - current_level
    #
    # because Journey outputs are the source of truth.
    #
    # The only thing calculated here is the resource suitability range.

    progression_start = max(
        MIN_LEVEL,
        current_level,
    )

    progression_end = min(
        MAX_LEVEL,
        target_level,
    )

    if progression_start > progression_end:

        return {
            "skill_id": skill_id,

            "state": "invalid_progression_range",

            "starting_phase":
                _phase_for_level(
                    current_level
                ),

            "resource_strategy":
                "validation_required",

            "resource_levels": [],

            "resource_difficulties": [],

            "development_required": False,

            "progression_required": False,

            "reason":
                "No valid resource-level progression "
                "range is available.",
        }

    resource_levels = list(
        range(
            progression_start,
            progression_end + 1,
        )
    )

    difficulties = []

    for level in resource_levels:

        for difficulty in _difficulty_for_level(
            level
        ):

            if difficulty not in difficulties:
                difficulties.append(
                    difficulty
                )

    # ========================================================================
    # GAP SIZE STRATEGY
    # ========================================================================

    if gap == 1:

        strategy = (
            "direct_progression"
        )

    else:

        strategy = (
            "progressive_progression"
        )

    return {
        "skill_id": skill_id,

        "state": "development_gap",

        "starting_phase":
            _phase_for_level(
                current_level
            ),

        "resource_strategy": strategy,

        "resource_levels":
            resource_levels,

        "resource_difficulties":
            difficulties,

        "development_required": True,

        "progression_required":
            len(resource_levels) > 1,

        "reason":
            "Use resources appropriate to the "
            "learner's current level and progress "
            "toward the supplied target level.",
    }


# ============================================================================
# MULTIPLE SKILLS
# ============================================================================

def apply_level_rules(
    skills: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Apply deterministic level rules to multiple skills.
    """

    if not isinstance(skills, list):
        raise TypeError(
            "'skills' must be a list."
        )

    return [
        apply_level_rule(skill)
        for skill in skills
    ]


# ============================================================================
# COMMON PROFILE SUPPORT
# ============================================================================

def apply_profile_level_rules(
    profile: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Apply level rules to a normalized common profile.

    The original profile is not modified.
    """

    if not isinstance(profile, dict):
        raise TypeError(
            "Profile must be a dictionary."
        )

    if "skills" not in profile:
        raise ValueError(
            "Profile is missing 'skills'."
        )

    result = dict(profile)

    result["level_rules"] = (
        apply_level_rules(
            profile["skills"]
        )
    )

    return result


# ============================================================================
# VALIDATION
# ============================================================================

def validate_level_rule_result(
    result: Dict[str, Any],
) -> None:
    """
    Validate one level-rule result.

    Structural validation only.
    """

    required_fields = {
        "skill_id",
        "state",
        "starting_phase",
        "resource_strategy",
        "resource_levels",
        "resource_difficulties",
        "development_required",
        "progression_required",
        "reason",
    }

    missing = (
        required_fields - result.keys()
    )

    if missing:
        raise ValueError(
            "Level-rule result missing fields: "
            f"{sorted(missing)}"
        )

    if not isinstance(
        result["resource_levels"],
        list,
    ):
        raise TypeError(
            "'resource_levels' must be a list."
        )

    for level in result["resource_levels"]:

        if not isinstance(level, int):
            raise TypeError(
                "Every resource level must be an integer."
            )

        if not (
            MIN_LEVEL
            <= level
            <= MAX_LEVEL
        ):
            raise ValueError(
                f"Invalid resource level: {level}"
            )


# ============================================================================
# SELF TEST
# ============================================================================

def run_self_test() -> None:
    """
    Standalone deterministic tests.
    """

    print("=" * 70)
    print(
        "MINERVA ROADMAP RAG — LEVEL RULES SELF TEST"
    )
    print("=" * 70)

    # ========================================================================
    # TEST 1 — BEGINNER / LEVEL 1
    # ========================================================================

    beginner_skill = {
        "skill_id":
            "logical_problem_solving",

        "current_level": 1,

        "target_level": 4,

        "gap": 3,

        "gap_label":
            "High Gap",

        "priority": "High",

        "category": "core",

        "weight": 1.0,

        "confidence": 0.5,

        "evidence_status":
            "measured",
    }

    beginner_result = apply_level_rule(
        beginner_skill
    )

    validate_level_rule_result(
        beginner_result
    )

    assert (
        beginner_result["state"]
        == "development_gap"
    )

    assert (
        beginner_result["starting_phase"]
        == "foundation"
    )

    assert (
        beginner_result["resource_strategy"]
        == "progressive_progression"
    )

    assert (
        beginner_result["resource_levels"]
        == [1, 2, 3, 4]
    )

    assert (
        beginner_result[
            "development_required"
        ]
        is True
    )

    print(
        "Beginner/Foundation rule: PASS"
    )

    # ========================================================================
    # TEST 2 — INTERMEDIATE / SMALL GAP
    # ========================================================================

    intermediate_skill = {
        "skill_id":
            "machine_learning_reasoning",

        "current_level": 3,

        "target_level": 4,

        "gap": 1,

        "gap_label":
            "Low Gap",

        "priority": "Low",

        "category": "core",

        "weight": 1.0,

        "confidence": 0.5,

        "evidence_status":
            "measured",
    }

    intermediate_result = apply_level_rule(
        intermediate_skill
    )

    validate_level_rule_result(
        intermediate_result
    )

    assert (
        intermediate_result["state"]
        == "development_gap"
    )

    assert (
        intermediate_result["starting_phase"]
        == "intermediate"
    )

    assert (
        intermediate_result["resource_strategy"]
        == "direct_progression"
    )

    assert (
        intermediate_result["resource_levels"]
        == [3, 4]
    )

    print(
        "Intermediate/Small gap rule: PASS"
    )

    # ========================================================================
    # TEST 3 — LEVEL 2 TO LEVEL 4
    # ========================================================================

    progressive_skill = {
        "skill_id":
            "algorithmic_thinking",

        "current_level": 2,

        "target_level": 4,

        "gap": 2,

        "gap_label":
            "Moderate Gap",

        "priority": "Medium",

        "category": "core",

        "weight": 1.0,

        "confidence": 0.5,

        "evidence_status":
            "measured",
    }

    progressive_result = apply_level_rule(
        progressive_skill
    )

    validate_level_rule_result(
        progressive_result
    )

    assert (
        progressive_result["starting_phase"]
        == "beginner"
    )

    assert (
        progressive_result["resource_strategy"]
        == "progressive_progression"
    )

    assert (
        progressive_result["resource_levels"]
        == [2, 3, 4]
    )

    assert (
        progressive_result[
            "progression_required"
        ]
        is True
    )

    print(
        "Progressive gap rule: PASS"
    )

    # ========================================================================
    # TEST 4 — NO EVIDENCE
    # ========================================================================

    no_evidence_skill = {
        "skill_id":
            "python",

        "current_level": None,

        "target_level": 4,

        "gap": None,

        "gap_label":
            "No Evidence",

        "priority": "None",

        "category": "tool",

        "weight": 0.8,

        "confidence": 0.0,

        "evidence_status":
            "no_evidence",
    }

    no_evidence_result = apply_level_rule(
        no_evidence_skill
    )

    validate_level_rule_result(
        no_evidence_result
    )

    assert (
        no_evidence_result["state"]
        == "no_evidence"
    )

    assert (
        no_evidence_result["starting_phase"]
        == "validation"
    )

    assert (
        no_evidence_result[
            "resource_strategy"
        ]
        == "explore_validate"
    )

    assert (
        no_evidence_result[
            "resource_levels"
        ]
        == []
    )

    assert (
        no_evidence_result[
            "development_required"
        ]
        is False
    )

    print(
        "No-evidence rule: PASS"
    )

    # ========================================================================
    # TEST 5 — NO DEVELOPMENT GAP
    # ========================================================================

    strength_skill = {
        "skill_id":
            "model_evaluation",

        "current_level": 4,

        "target_level": 4,

        "gap": 0,

        "gap_label":
            "No Gap",

        "priority": "None",

        "category": "core",

        "weight": 1.0,

        "confidence": 1.0,

        "evidence_status":
            "measured",
    }

    strength_result = apply_level_rule(
        strength_skill
    )

    validate_level_rule_result(
        strength_result
    )

    assert (
        strength_result["state"]
        == "no_development_gap"
    )

    assert (
        strength_result["starting_phase"]
        == "advanced"
    )

    assert (
        strength_result[
            "development_required"
        ]
        is False
    )

    assert (
        strength_result[
            "resource_levels"
        ]
        == []
    )

    print(
        "Strength/No-gap rule: PASS"
    )

    # ========================================================================
    # TEST 6 — ABOVE TARGET
    # ========================================================================

    above_target_skill = {
        "skill_id":
            "analytical_reasoning",

        "current_level": 5,

        "target_level": 4,

        "gap": 0,

        "gap_label":
            "No Gap",

        "priority": "None",

        "category": "core",

        "weight": 1.0,

        "confidence": 1.0,

        "evidence_status":
            "measured",
    }

    above_target_result = apply_level_rule(
        above_target_skill
    )

    validate_level_rule_result(
        above_target_result
    )

    assert (
        above_target_result["state"]
        == "no_development_gap"
    )

    assert (
        above_target_result["starting_phase"]
        == "advanced"
    )

    assert (
        above_target_result[
            "development_required"
        ]
        is False
    )

    print(
        "Above-target rule: PASS"
    )

    # ========================================================================
    # TEST 7 — PROFILE
    # ========================================================================

    profile = {
        "journey":
            "career-in-mind",

        "career":
            "data",

        "target_role":
            None,

        "current_experience_level":
            None,

        "goal":
            None,

        "weekly_hours":
            None,

        "skills": [
            intermediate_skill,
            no_evidence_skill,
        ],

        "strengths": [],

        "weak_areas": [],

        "preferences": {},
    }

    profile_result = (
        apply_profile_level_rules(
            profile
        )
    )

    assert (
        len(
            profile_result[
                "level_rules"
            ]
        )
        == 2
    )

    # Original skills remain untouched.
    assert (
        profile_result["skills"]
        is profile["skills"]
    )

    print(
        "Common profile integration: PASS"
    )

    # ========================================================================
    # FINAL
    # ========================================================================

    print("=" * 70)
    print(
        "ALL LEVEL RULES TESTS PASSED"
    )
    print("=" * 70)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    run_self_test()