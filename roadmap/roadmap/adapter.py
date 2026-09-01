"""
MINERVA — Personalized Roadmap RAG
adapter.py

Purpose:
    Normalize Journey 1, Journey 2, and Journey 3 outputs into
    one common Skill Gap Profile for the Roadmap RAG.

IMPORTANT ARCHITECTURE RULES:
    - Journey outputs are the source of truth.
    - This adapter ONLY normalizes structure.
    - It does NOT calculate skill gaps.
    - It does NOT calculate current levels.
    - It does NOT calculate target levels.
    - It does NOT select careers.
    - It does NOT retrieve resources.
    - It does NOT generate roadmap content.
    - It does NOT invent missing user information.
    - No-evidence remains no-evidence.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional


# ============================================================================
# CONFIGURATION
# ============================================================================

SUPPORTED_CAREERS = {
    "ui_ux",
    "development",
    "data",
    "ai",
    "cyber",
}


CONFIDENCE_MAP = {
    "high": 1.0,
    "moderate": 0.75,
    "medium": 0.75,
    "low": 0.5,
    "none": 0.0,
}


# ============================================================================
# GENERIC HELPERS
# ============================================================================

def _require_dict(data: Any, source: str) -> Dict[str, Any]:
    """Ensure journey output is a dictionary."""

    if not isinstance(data, dict):
        raise TypeError(
            f"{source} input must be a dictionary, "
            f"got {type(data).__name__}"
        )

    return data


def _validate_career(career: Optional[str]) -> None:
    """Validate career only when career is actually supplied."""

    if career is None:
        return

    if career not in SUPPORTED_CAREERS:
        raise ValueError(
            f"Unsupported career '{career}'. "
            f"Expected one of: {sorted(SUPPORTED_CAREERS)}"
        )


def _copy_optional_list(value: Any) -> List[Any]:
    """Safely copy an optional list."""

    if value is None:
        return []

    if not isinstance(value, list):
        raise TypeError(
            f"Expected list, got {type(value).__name__}"
        )

    return deepcopy(value)


def _normalize_confidence(value: Any) -> Optional[float]:
    """
    Normalize confidence.

    Supported input examples:

        Journey 1:
            0.5
            0.75
            1.0

        Journey 2 / Journey 3:
            high
            moderate
            low
            none

    Output:
        numeric value between 0 and 1
        or None when confidence is unavailable
    """

    if value is None:
        return None

    if isinstance(value, bool):
        raise ValueError("Confidence cannot be boolean.")

    if isinstance(value, (int, float)):
        value = float(value)

        if not 0.0 <= value <= 1.0:
            raise ValueError(
                f"Confidence must be between 0 and 1, got {value}"
            )

        return value

    if isinstance(value, str):
        normalized = value.strip().lower()

        if normalized in CONFIDENCE_MAP:
            return CONFIDENCE_MAP[normalized]

    raise ValueError(
        f"Unsupported confidence value: {value!r}"
    )


def _normalize_evidence_status(value: Any) -> Optional[str]:
    """
    Normalize evidence-status terminology.

    Common output values:

        measured
        partial_evidence
        no_evidence
    """

    if value is None:
        return None

    normalized = str(value).strip().lower()

    mapping = {
        "preliminary evidence": "partial_evidence",
        "preliminary_evidence": "partial_evidence",
        "partial evidence": "partial_evidence",
        "partial_evidence": "partial_evidence",

        "no evidence": "no_evidence",
        "no_evidence": "no_evidence",

        "measured": "measured",
    }

    return mapping.get(normalized, normalized)


def _normalize_skill_record(
    skill: Dict[str, Any],
    source: str,
) -> Dict[str, Any]:
    """
    Normalize a single skill record.

    IMPORTANT:
        Values are copied from the journey.
        No gap/level calculation happens here.
    """

    if not isinstance(skill, dict):
        raise TypeError(
            f"{source} skill record must be a dictionary."
        )

    skill_id = skill.get("skill_id")

    if not skill_id:
        raise ValueError(
            f"{source} skill record is missing 'skill_id'."
        )

    # ------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------

    if "confidence" in skill:
        confidence_value = skill.get("confidence")
    else:
        confidence_value = skill.get("evidence_confidence")

    # ------------------------------------------------------------
    # Common normalized record
    # ------------------------------------------------------------

    normalized = {
        "skill_id": skill_id,

        "current_level": skill.get("current_level"),

        "target_level": skill.get("target_level"),

        "gap": skill.get("gap"),

        "gap_label": skill.get("gap_label"),

        "priority": skill.get("priority"),

        "category": skill.get("category"),

        "weight": skill.get("weight"),

        "confidence": _normalize_confidence(
            confidence_value
        ),

        "evidence_status": _normalize_evidence_status(
            skill.get("evidence_status")
        ),
    }

    return normalized


# ============================================================================
# COMMON PROFILE
# ============================================================================

def _base_profile(
    journey: str,
    career: Optional[str],
) -> Dict[str, Any]:
    """
    Create the common RAG profile.

    Missing information is intentionally represented as None/empty.
    The adapter never invents user information.
    """

    return {
        "journey": journey,

        "career": career,

        "target_role": None,

        "current_experience_level": None,

        "goal": None,

        "weekly_hours": None,

        "skills": [],

        "strengths": [],

        "weak_areas": [],

        "preferences": {},
    }


# ============================================================================
# JOURNEY 1
# ============================================================================

def adapt_journey1(
    journey1_output: Dict[str, Any],
    career: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Adapt Journey 1 final result.

    Journey 1 may contain multiple career profiles.

    If career is supplied:
        return only that career.

    If career is not supplied:
        return all careers represented in the J1 skill profile.
    """

    data = _require_dict(
        journey1_output,
        "Journey 1",
    )

    _validate_career(career)

    source_skills = data.get(
        "preliminary_current_skill_profile"
    )

    if source_skills is None:
        raise ValueError(
            "Journey 1 output is missing "
            "'preliminary_current_skill_profile'."
        )

    if not isinstance(source_skills, list):
        raise TypeError(
            "Journey 1 'preliminary_current_skill_profile' "
            "must be a list."
        )

    # ------------------------------------------------------------
    # Find careers directly from J1 output
    # ------------------------------------------------------------

    available_careers: List[str] = []

    for skill in source_skills:

        if not isinstance(skill, dict):
            continue

        skill_career = skill.get("career")

        if (
            skill_career
            and skill_career not in available_careers
        ):
            available_careers.append(skill_career)

    # ------------------------------------------------------------
    # Career filtering
    # ------------------------------------------------------------

    if career is not None:
        selected_careers = [career]
    else:
        selected_careers = available_careers

    # ------------------------------------------------------------
    # Existing J1 AI insight structure
    # ------------------------------------------------------------

    recommendation = data.get(
        "career_recommendation",
        {}
    )

    if not isinstance(recommendation, dict):
        recommendation = {}

    ai_insights = recommendation.get(
        "supporting_ai_insights",
        {}
    )

    if not isinstance(ai_insights, dict):
        ai_insights = {}

    strengths = _copy_optional_list(
        ai_insights.get("strengths")
    )

    weak_areas = _copy_optional_list(
        ai_insights.get("improvement_areas")
    )

    # ------------------------------------------------------------
    # Build one common profile per career
    # ------------------------------------------------------------

    profiles: List[Dict[str, Any]] = []

    for selected_career in selected_careers:

        career_skills = [
            skill
            for skill in source_skills
            if isinstance(skill, dict)
            and skill.get("career") == selected_career
        ]

        if not career_skills:
            continue

        profile = _base_profile(
            journey="exploring",
            career=selected_career,
        )

        profile["skills"] = [
            _normalize_skill_record(
                skill,
                source="Journey 1",
            )
            for skill in career_skills
        ]

        profile["strengths"] = deepcopy(
            strengths
        )

        profile["weak_areas"] = deepcopy(
            weak_areas
        )

        profiles.append(profile)

    return profiles


# ============================================================================
# JOURNEY 2
# ============================================================================

def adapt_journey2(
    journey2_output: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Adapt Journey 2 output.

    Journey 2 represents one selected career.
    """

    data = _require_dict(
        journey2_output,
        "Journey 2",
    )

    career = data.get("career")

    if not career:
        raise ValueError(
            "Journey 2 output is missing 'career'."
        )

    _validate_career(career)

    source_skills = data.get(
        "current_skill_profile"
    )

    if source_skills is None:
        raise ValueError(
            "Journey 2 output is missing "
            "'current_skill_profile'."
        )

    if not isinstance(source_skills, list):
        raise TypeError(
            "Journey 2 'current_skill_profile' "
            "must be a list."
        )

    profile = _base_profile(
        journey="career-in-mind",
        career=career,
    )

    profile["skills"] = [
        _normalize_skill_record(
            skill,
            source="Journey 2",
        )
        for skill in source_skills
    ]

    profile["strengths"] = _copy_optional_list(
        data.get("strengths")
    )

    profile["weak_areas"] = _copy_optional_list(
        data.get("weak_areas")
    )

    return profile


# ============================================================================
# JOURNEY 3
# ============================================================================

def adapt_journey3(
    journey3_output: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Adapt Journey 3 Skill Gap Analysis output.

    Actual Journey 3 structure:

        {
            "evaluation_results": [...],
            "skill_profile": [...]
        }

    Journey 3's actual skill information is located directly
    inside 'skill_profile'.

    Career/target-role information is NOT assumed because it is
    not present in the supplied J3 skill-profile format.

    Therefore missing fields remain None.
    """

    data = _require_dict(
        journey3_output,
        "Journey 3",
    )

    source_skills = data.get(
        "skill_profile"
    )

    if source_skills is None:
        raise ValueError(
            "Journey 3 output is missing 'skill_profile'."
        )

    if not isinstance(source_skills, list):
        raise TypeError(
            "Journey 3 'skill_profile' must be a list."
        )

    profile = _base_profile(
        journey="targeting",
        career=None,
    )

    profile["skills"] = [
        _normalize_skill_record(
            skill,
            source="Journey 3",
        )
        for skill in source_skills
    ]

    # J3 supplied output does not define a separate strengths
    # or weak_areas field in the provided format.
    profile["strengths"] = []

    profile["weak_areas"] = []

    return profile


# ============================================================================
# UNIFIED ENTRY POINT
# ============================================================================

def adapt(
    journey: int,
    journey_output: Dict[str, Any],
    career: Optional[str] = None,
) -> Any:
    """
    Unified adapter entry point.

    Journey 1:
        returns List[Dict]

    Journey 2:
        returns Dict

    Journey 3:
        returns Dict
    """

    if journey == 1:

        return adapt_journey1(
            journey1_output=journey_output,
            career=career,
        )

    if journey == 2:

        if career is not None:
            raise ValueError(
                "Do not provide 'career' for Journey 2. "
                "Journey 2 already contains its selected career."
            )

        return adapt_journey2(
            journey2_output=journey_output,
        )

    if journey == 3:

        if career is not None:
            raise ValueError(
                "Do not provide 'career' for Journey 3. "
                "Career is not present in the supplied J3 "
                "skill-profile format."
            )

        return adapt_journey3(
            journey3_output=journey_output,
        )

    raise ValueError(
        f"Unsupported journey '{journey}'. "
        "Currently supported: Journey 1, Journey 2, Journey 3."
    )


# ============================================================================
# COMMON PROFILE VALIDATION
# ============================================================================

def validate_common_profile(
    profile: Dict[str, Any],
) -> None:
    """
    Validate normalized profile structure.

    Structural validation only.

    This function does NOT recalculate:
        - current_level
        - target_level
        - gap
        - priority
        - confidence
    """

    if not isinstance(profile, dict):
        raise TypeError(
            "Common profile must be a dictionary."
        )

    required_fields = {
        "journey",
        "career",
        "target_role",
        "current_experience_level",
        "goal",
        "weekly_hours",
        "skills",
        "strengths",
        "weak_areas",
        "preferences",
    }

    missing = (
        required_fields - profile.keys()
    )

    if missing:
        raise ValueError(
            "Common profile missing fields: "
            f"{sorted(missing)}"
        )

    if profile["career"] is not None:
        _validate_career(
            profile["career"]
        )

    if not isinstance(
        profile["skills"],
        list,
    ):
        raise TypeError(
            "'skills' must be a list."
        )

    if not isinstance(
        profile["strengths"],
        list,
    ):
        raise TypeError(
            "'strengths' must be a list."
        )

    if not isinstance(
        profile["weak_areas"],
        list,
    ):
        raise TypeError(
            "'weak_areas' must be a list."
        )

    if not isinstance(
        profile["preferences"],
        dict,
    ):
        raise TypeError(
            "'preferences' must be a dictionary."
        )

    required_skill_fields = {
        "skill_id",
        "current_level",
        "target_level",
        "gap",
        "gap_label",
        "priority",
        "category",
        "weight",
        "confidence",
        "evidence_status",
    }

    for skill in profile["skills"]:

        if not isinstance(skill, dict):
            raise TypeError(
                "Every skill must be a dictionary."
            )

        missing_skill_fields = (
            required_skill_fields - skill.keys()
        )

        if missing_skill_fields:
            raise ValueError(
                "Skill record missing fields: "
                f"{sorted(missing_skill_fields)}"
            )

        if not skill["skill_id"]:
            raise ValueError(
                "Skill record contains empty skill_id."
            )


# ============================================================================
# TEST HELPERS
# ============================================================================

def _assert_no_recalculation(
    skill: Dict[str, Any],
    expected_current: Any,
    expected_target: Any,
    expected_gap: Any,
) -> None:
    """
    Confirm adapter preserved journey values exactly.
    """

    assert (
        skill["current_level"]
        == expected_current
    )

    assert (
        skill["target_level"]
        == expected_target
    )

    assert (
        skill["gap"]
        == expected_gap
    )


# ============================================================================
# SELF TEST
# ============================================================================

def run_self_test() -> None:
    """
    Complete standalone adapter test.

    Tests:
        - Journey 1
        - Journey 2
        - Journey 3
        - confidence normalization
        - evidence normalization
        - no-evidence preservation
        - common schema validation
        - no recalculation
    """

    # ========================================================================
    # JOURNEY 1 TEST
    # ========================================================================

    j1_sample = {

        "journey": 1,

        "mode": "exploring",

        "preliminary_current_skill_profile": [

            {
                "career": "ai",

                "skill_id":
                    "machine_learning_reasoning",

                "skill_name":
                    "Machine Learning Reasoning",

                "category": "core",

                "weight": 1.0,

                "current_level": 3,

                "current_level_label":
                    "Functional",

                "target_level": 4,

                "evidence_ratio": 1.0,

                "confidence": 0.5,

                "evidence_questions":
                    ["AI_01", "AI_02"],

                "evidence_careers":
                    ["ai"],

                "positive_evidence": 2,

                "negative_evidence": 0,

                "evidence_status":
                    "Preliminary Evidence",

                "gap": 1,

                "gap_label":
                    "Low Gap",

                "priority": "Low",
            },

            {
                "career": "data",

                "skill_id":
                    "analytical_reasoning",

                "skill_name":
                    "Analytical Reasoning",

                "category": "core",

                "weight": 1.0,

                "current_level": 3,

                "current_level_label":
                    "Functional",

                "target_level": 4,

                "evidence_ratio": 1.0,

                "confidence": 0.5,

                "evidence_questions":
                    ["DATA_01", "DATA_02"],

                "evidence_careers":
                    ["data"],

                "positive_evidence": 2,

                "negative_evidence": 0,

                "evidence_status":
                    "Preliminary Evidence",

                "gap": 1,

                "gap_label":
                    "Low Gap",

                "priority": "Low",
            },
        ],

        "career_recommendation": {

            "supporting_ai_insights": {

                "strengths": [
                    "Analytical Reasoning"
                ],

                "improvement_areas": [],
            }
        },
    }

    j1_profiles = adapt(
        journey=1,
        journey_output=j1_sample,
    )

    assert len(j1_profiles) == 2

    assert (
        j1_profiles[0]["career"]
        == "ai"
    )

    assert (
        j1_profiles[1]["career"]
        == "data"
    )

    for profile in j1_profiles:
        validate_common_profile(profile)

    ai_skill = j1_profiles[0]["skills"][0]

    _assert_no_recalculation(
        ai_skill,
        expected_current=3,
        expected_target=4,
        expected_gap=1,
    )

    assert (
        ai_skill["confidence"]
        == 0.5
    )

    assert (
        ai_skill["evidence_status"]
        == "partial_evidence"
    )

    # ========================================================================
    # JOURNEY 2 TEST
    # ========================================================================

    j2_sample = {

        "career": "data",

        "career_name":
            "Data & Analytics",

        "score": 5,

        "max_score": 5,

        "readiness_percent": 100.0,

        "performance_level":
            "Highly Ready",

        "validation":
            "Strong Match",

        "strengths": [

            "Analytical Reasoning",

            "Critical Thinking",
        ],

        "weak_areas": [],

        "skill_gap": [],

        "current_skill_profile": [

            {
                "skill_id":
                    "analytical_reasoning",

                "skill_name":
                    "Analytical Reasoning",

                "category": "core",

                "weight": 1.0,

                "current_level": 5,

                "current_level_label":
                    "Expert",

                "target_level": 4,

                "evidence_ratio": 1.0,

                "positive_signals": 3,

                "negative_signals": 0,

                "total_signals": 3,

                "evidence_questions": [
                    "DATA_01",
                    "DATA_04",
                    "DATA_05",
                ],

                "gap": 0,

                "gap_label": "No Gap",

                "priority": "None",

                "evidence_status":
                    "measured",

                "evidence_confidence":
                    "high",
            },

            {
                "skill_id":
                    "sql",

                "skill_name":
                    "Sql",

                "category": "tool",

                "weight": 0.8,

                "current_level": None,

                "current_level_label":
                    "No Evidence",

                "target_level": 3,

                "evidence_ratio": None,

                "positive_signals": 0,

                "negative_signals": 0,

                "total_signals": 0,

                "evidence_questions": [],

                "gap": None,

                "gap_label":
                    "No Evidence",

                "priority": "None",

                "evidence_status":
                    "no_evidence",

                "evidence_confidence":
                    "none",
            },
        ],
    }

    j2_profile = adapt(
        journey=2,
        journey_output=j2_sample,
    )

    validate_common_profile(
        j2_profile
    )

    assert (
        j2_profile["career"]
        == "data"
    )

    assert (
        len(j2_profile["skills"])
        == 2
    )

    measured_j2_skill = (
        j2_profile["skills"][0]
    )

    no_evidence_j2_skill = (
        j2_profile["skills"][1]
    )

    _assert_no_recalculation(
        measured_j2_skill,
        expected_current=5,
        expected_target=4,
        expected_gap=0,
    )

    assert (
        measured_j2_skill["confidence"]
        == 1.0
    )

    assert (
        no_evidence_j2_skill["current_level"]
        is None
    )

    assert (
        no_evidence_j2_skill["target_level"]
        == 3
    )

    assert (
        no_evidence_j2_skill["gap"]
        is None
    )

    assert (
        no_evidence_j2_skill["confidence"]
        == 0.0
    )

    assert (
        no_evidence_j2_skill[
            "evidence_status"
        ]
        == "no_evidence"
    )

    # ========================================================================
    # JOURNEY 3 TEST
    # ========================================================================

    j3_sample = {

        "evaluation_results": [

            {
                "skill_id":
                    "logical_problem_solving",

                "is_correct": False,

                "reasoning":
                    "The response is vague.",
            },

            {
                "skill_id":
                    "system_design",

                "is_correct": True,

                "reasoning":
                    "Correctly identifies read replication.",
            },
        ],

        "skill_profile": [

            {
                "skill_id":
                    "logical_problem_solving",

                "skill_name":
                    "Logical Problem Solving",

                "category": "core",

                "weight": 1.0,

                "current_level": 1,

                "current_level_label":
                    "Beginner",

                "target_level": 4,

                "evidence_ratio": 0.0,

                "gap": 3,

                "gap_label":
                    "High Gap",

                "priority": "High",

                "evidence_status":
                    "measured",

                "evidence_confidence":
                    "low",
            },

            {
                "skill_id":
                    "debugging",

                "skill_name":
                    "Debugging",

                "category": "core",

                "weight": 0.9,

                "current_level": 1,

                "current_level_label":
                    "Beginner",

                "target_level": 3,

                "evidence_ratio": 0.0,

                "gap": 2,

                "gap_label":
                    "Moderate Gap",

                "priority": "Medium",

                "evidence_status":
                    "measured",

                "evidence_confidence":
                    "low",
            },

            {
                "skill_id":
                    "javascript",

                "skill_name":
                    "Javascript",

                "category": "tool",

                "weight": 0.7,

                "current_level": None,

                "current_level_label":
                    "No Evidence",

                "target_level": 3,

                "gap": None,

                "gap_label":
                    "No Evidence",

                "priority": "None",

                "evidence_status":
                    "no_evidence",
            },

            {
                "skill_id":
                    "system_design",

                "skill_name":
                    "System Design",

                "category": "supporting",

                "weight": 0.8,

                "current_level": 3,

                "current_level_label":
                    "Intermediate",

                "target_level": 3,

                "evidence_ratio": 1.0,

                "gap": 0,

                "gap_label":
                    "No Gap",

                "priority": "None",

                "evidence_status":
                    "measured",

                "evidence_confidence":
                    "low",
            },
        ],
    }

    j3_profile = adapt(
        journey=3,
        journey_output=j3_sample,
    )

    validate_common_profile(
        j3_profile
    )

    assert (
        j3_profile["journey"]
        == "targeting"
    )

    assert (
        j3_profile["career"]
        is None
    )

    assert (
        len(j3_profile["skills"])
        == 4
    )

    # ------------------------------------------------------------
    # J3 measured high-gap skill
    # ------------------------------------------------------------

    logical_skill = (
        j3_profile["skills"][0]
    )

    _assert_no_recalculation(
        logical_skill,
        expected_current=1,
        expected_target=4,
        expected_gap=3,
    )

    assert (
        logical_skill["priority"]
        == "High"
    )

    assert (
        logical_skill["confidence"]
        == 0.5
    )

    assert (
        logical_skill["evidence_status"]
        == "measured"
    )

    # ------------------------------------------------------------
    # J3 no-evidence skill
    # ------------------------------------------------------------

    javascript_skill = (
        j3_profile["skills"][2]
    )

    assert (
        javascript_skill["current_level"]
        is None
    )

    assert (
        javascript_skill["target_level"]
        == 3
    )

    assert (
        javascript_skill["gap"]
        is None
    )

    assert (
        javascript_skill["evidence_status"]
        == "no_evidence"
    )

    assert (
        javascript_skill["confidence"]
        is None
    )

    # ========================================================================
    # FINAL TEST OUTPUT
    # ========================================================================

    print("=" * 70)
    print("MINERVA ROADMAP RAG — FINAL ADAPTER SELF TEST")
    print("=" * 70)

    print("Journey 1 adaptation: PASS")
    print("Journey 2 adaptation: PASS")
    print("Journey 3 adaptation: PASS")

    print("Confidence normalization: PASS")
    print("Evidence-status normalization: PASS")

    print("No-evidence preservation: PASS")

    print("Gap/level preservation: PASS")

    print("Common profile validation: PASS")

    print("Journey 3 career not invented: PASS")

    print("=" * 70)
    print("ALL ADAPTER TESTS PASSED")
    print("=" * 70)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    run_self_test()