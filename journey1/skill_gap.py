"""
MINERVA — JOURNEY 1: PRELIMINARY SKILL GAP PIPELINE

Runs AFTER the existing Journey 1 career recommendation.

It does NOT modify:
- exploring_scoring.py
- exploring_ai.py
- exploring_recommendation.py
- Journey 2

Canonical sources:
- career_skill_matrix.json: target levels, categories, weights only
- skill_normalization.json: career-specific raw signal -> canonical skill mapping only

Journey 1 has only 2 questions per career, so all skill evidence is
explicitly preliminary and confidence is conservative.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


# ============================================================
# CONSTANTS
# ============================================================

CAREERS = (
    "ui_ux",
    "development",
    "data",
    "ai",
    "cyber",
)

LEVEL_LABELS = {
    1: "Needs Foundation",
    2: "Developing",
    3: "Functional",
    4: "Strong",
    5: "Advanced",
}

PRIORITY_ORDER = {
    "High": 0,
    "Medium": 1,
    "Low": 2,
    "None": 3,
}


# ============================================================
# ERROR
# ============================================================

class Journey1SkillGapError(ValueError):
    """Invalid Journey 1 skill-gap configuration or result."""


# ============================================================
# JSON LOADER
# ============================================================

def load_json(path: str | Path) -> Dict[str, Any]:
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        value = json.load(file)

    if not isinstance(value, dict):
        raise Journey1SkillGapError(
            f"{path.name} must contain a JSON object."
        )

    return value


# ============================================================
# HELPERS
# ============================================================

def _normalize_id(value: Any) -> str:
    return str(value).strip().lower()


def _first(
    mapping: Dict[str, Any],
    keys: Iterable[str],
    default=None,
):
    for key in keys:
        if key in mapping:
            return mapping[key]

    return default


# ============================================================
# CAREER SKILL MATRIX
# ============================================================

def _skill_records(
    matrix: Dict[str, Any],
    career: str,
) -> Dict[str, Dict[str, Any]]:
    """
    Read required canonical skills for one career.

    Target level, category and weight ALWAYS come from
    career_skill_matrix.json.
    """

    careers = matrix.get("careers")

    if not isinstance(careers, dict):
        raise Journey1SkillGapError(
            "career_skill_matrix.json must contain "
            "'careers'."
        )

    if career not in careers:
        raise Journey1SkillGapError(
            f"career_skill_matrix.json has no career "
            f"'{career}'."
        )

    career_data = careers[career]

    if not isinstance(career_data, dict):
        raise Journey1SkillGapError(
            f"Invalid career configuration for '{career}'."
        )

    raw = career_data.get("required_skills")

    # --------------------------------------------------------
    # Supported canonical matrix form
    # --------------------------------------------------------
    #
    # "required_skills": {
    #     "skill_id": {
    #         "target_level": 4,
    #         "category": "core",
    #         "weight": 1.0
    #     }
    # }
    #
    # --------------------------------------------------------

    if isinstance(raw, dict):

        records: Dict[str, Dict[str, Any]] = {}

        for skill_id, meta in raw.items():

            if not isinstance(meta, dict):
                raise Journey1SkillGapError(
                    f"Invalid skill metadata for "
                    f"'{career}:{skill_id}'."
                )

            if "target_level" not in meta:
                raise Journey1SkillGapError(
                    f"Missing target_level for "
                    f"'{career}:{skill_id}'."
                )

            canonical_id = _normalize_id(skill_id)

            records[canonical_id] = {
                "id": canonical_id,
                "name": (
                    meta.get("name")
                    or canonical_id.replace(
                        "_",
                        " ",
                    ).title()
                ),
                "target_level": int(
                    meta["target_level"]
                ),
                "category": meta.get(
                    "category",
                    "supporting",
                ),
                "weight": float(
                    meta.get(
                        "weight",
                        1.0,
                    )
                ),
            }

        return records

    # --------------------------------------------------------
    # Journey 2-style list support
    # --------------------------------------------------------

    if isinstance(raw, list):

        records = {}

        for item in raw:

            if (
                not isinstance(item, dict)
                or not item.get("id")
            ):
                raise Journey1SkillGapError(
                    f"Invalid required skill entry "
                    f"for career '{career}'."
                )

            if "target_level" not in item:
                raise Journey1SkillGapError(
                    f"Missing target_level for "
                    f"'{career}:{item.get('id')}'."
                )

            skill_id = _normalize_id(
                item["id"]
            )

            records[skill_id] = {
                "id": skill_id,
                "name": (
                    item.get("name")
                    or skill_id.replace(
                        "_",
                        " ",
                    ).title()
                ),
                "target_level": int(
                    item["target_level"]
                ),
                "category": item.get(
                    "category",
                    "supporting",
                ),
                "weight": float(
                    item.get(
                        "weight",
                        1.0,
                    )
                ),
            }

        return records

    raise Journey1SkillGapError(
        f"career_skill_matrix.json career "
        f"'{career}' must contain required_skills."
    )


# ============================================================
# NORMALIZATION
# ============================================================

def _extract_career_mappings(
    config: Dict[str, Any],
) -> Dict[str, Dict[str, str]]:
    """
    Read the FINALIZED skill_normalization.json structure.

    Expected structure:

        career_mappings
            ui_ux
                mappings[]
            development
                mappings[]
            data
                mappings[]
            ai
                mappings[]
            cyber
                mappings[]

    Returns:

        {
            "ui_ux": {
                "user_research": "user_research",
                "usability": "usability",
                ...
            },
            "development": {
                "logical_reasoning":
                    "logical_problem_solving",
                ...
            }
        }

    IMPORTANT:
    - diagnostic_only mappings are ignored
    - canonical_skill == null is ignored
    - mapping type does not change the canonical target
    - career-specific mappings remain career-specific
    """

    career_mappings = config.get(
        "career_mappings"
    )

    if not isinstance(
        career_mappings,
        dict,
    ):
        raise Journey1SkillGapError(
            "skill_normalization.json must contain "
            "'career_mappings'."
        )

    result: Dict[
        str,
        Dict[str, str],
    ] = {}

    for career in CAREERS:

        career_config = career_mappings.get(
            career
        )

        if career_config is None:
            result[career] = {}
            continue

        if not isinstance(
            career_config,
            dict,
        ):
            raise Journey1SkillGapError(
                f"Invalid normalization configuration "
                f"for career '{career}'."
            )

        mappings = career_config.get(
            "mappings"
        )

        if not isinstance(
            mappings,
            list,
        ):
            raise Journey1SkillGapError(
                f"skill_normalization.json career "
                f"'{career}' must contain a "
                f"'mappings' list."
            )

        career_result: Dict[str, str] = {}

        for item in mappings:

            if not isinstance(
                item,
                dict,
            ):
                continue

            source_skill = item.get(
                "source_skill"
            )

            canonical_skill = item.get(
                "canonical_skill"
            )

            mapping_type = _normalize_id(
                item.get(
                    "mapping_type",
                    "",
                )
            )

            # ------------------------------------------------
            # Diagnostic-only mappings NEVER contribute
            # ------------------------------------------------

            if mapping_type == "diagnostic_only":
                continue

            # ------------------------------------------------
            # Null canonical skill NEVER contributes
            # ------------------------------------------------

            if (
                source_skill is None
                or canonical_skill is None
            ):
                continue

            source_id = _normalize_id(
                source_skill
            )

            canonical_id = _normalize_id(
                canonical_skill
            )

            if not source_id or not canonical_id:
                continue

            career_result[
                source_id
            ] = canonical_id

        result[career] = career_result

    total_mappings = sum(
        len(mapping)
        for mapping in result.values()
    )

    if total_mappings == 0:
        raise Journey1SkillGapError(
            "skill_normalization.json contains no "
            "usable career-specific mappings."
        )

    return result


# ============================================================
# TARGET CAREERS
# ============================================================

def _target_careers(
    recommendation: Dict[str, Any],
) -> List[str]:
    """
    Determine which career(s) should receive Skill Gap analysis.

    Handles:
    - single_primary
    - highest_score_tie
    - complete_tie
    """

    rec = recommendation.get(
        "recommendation",
        recommendation,
    )

    if not isinstance(
        rec,
        dict,
    ):
        raise Journey1SkillGapError(
            "Invalid recommendation object."
        )

    rec_type = str(
        rec.get(
            "type",
            "",
        )
    ).strip().lower()

    # --------------------------------------------------------
    # Single primary career
    # --------------------------------------------------------

    if rec_type == "single_primary":

        primary = rec.get(
            "primary_career"
        ) or {}

        if isinstance(
            primary,
            dict,
        ):
            career = _normalize_id(
                primary.get(
                    "career_id"
                )
            )

            if career in CAREERS:
                return [career]

    # --------------------------------------------------------
    # Highest-score tie
    # --------------------------------------------------------

    if rec_type == "highest_score_tie":

        tie = rec.get(
            "career_tie"
        ) or {}

        tied = tie.get(
            "tied_career_ids",
            [],
        )

        if isinstance(
            tied,
            list,
        ):

            careers = [
                _normalize_id(value)
                for value in tied
            ]

            careers = [
                career
                for career in careers
                if career in CAREERS
            ]

            if careers:
                return careers

    # --------------------------------------------------------
    # Complete tie
    # --------------------------------------------------------

    if rec_type == "complete_tie":
        return list(CAREERS)

    # --------------------------------------------------------
    # Safe fallback
    # --------------------------------------------------------

    primary = rec.get(
        "primary_career"
    ) or {}

    if isinstance(
        primary,
        dict,
    ):
        career = _normalize_id(
            primary.get(
                "career_id"
            )
        )

        if career in CAREERS:
            return [career]

    raise Journey1SkillGapError(
        "Cannot determine target career(s) from "
        "career recommendation."
    )


# ============================================================
# PRELIMINARY LEVEL
# ============================================================

def _level_from_evidence(
    ratio: float,
) -> int:
    """
    Convert evidence ratio to preliminary 1-5 level.

    Journey 1 has very limited evidence, therefore the
    resulting level is capped at 3.

    ratio >= 0.80 -> raw 5 -> capped 3
    ratio >= 0.60 -> raw 4 -> capped 3
    ratio >= 0.40 -> raw 3
    ratio >= 0.20 -> raw 2
    otherwise     -> raw 1
    """

    if ratio >= 0.80:
        raw_level = 5

    elif ratio >= 0.60:
        raw_level = 4

    elif ratio >= 0.40:
        raw_level = 3

    elif ratio >= 0.20:
        raw_level = 2

    else:
        raw_level = 1

    return min(
        raw_level,
        3,
    )


# ============================================================
# CONFIDENCE
# ============================================================

def _confidence(
    question_count: int,
    evidence_ratio: float,
) -> float:
    """
    Conservative Journey 1 confidence.

    1 question -> <= 0.35
    2 questions -> <= 0.50
    Hard cap -> 0.60
    """

    base = {
        1: 0.35,
        2: 0.50,
    }.get(
        question_count,
        0.55,
    )

    consistency = (
        0.5
        + (
            0.5
            * evidence_ratio
        )
    )

    return round(
        min(
            base * consistency,
            0.60,
        ),
        2,
    )


# ============================================================
# GAP LABEL
# ============================================================

def _gap_label(
    gap: int,
) -> str:

    if gap == 0:
        return "No Gap"

    if gap == 1:
        return "Low Gap"

    if gap == 2:
        return "Moderate Gap"

    return "High Gap"


# ============================================================
# PRIORITY
# ============================================================

def _priority(
    gap: int,
) -> str:

    if gap >= 3:
        return "High"

    if gap == 2:
        return "Medium"

    if gap == 1:
        return "Low"

    return "None"


# ============================================================
# CAREER-SPECIFIC EVIDENCE COLLECTION
# ============================================================

def _collect_evidence_for_career(
    exploring_result: Dict[str, Any],
    career: str,
    career_normalization: Dict[str, str],
) -> Tuple[
    Dict[str, Dict[str, Any]],
    List[str],
]:
    """
    Convert behavior signals into canonical skills using
    ONLY the normalization mappings belonging to the target career.

    This is critical because skill_normalization.json contains
    career-specific mappings.

    Example:

        development:
            logical_reasoning
                -> logical_problem_solving

        data:
            pattern_recognition
                -> analytical_reasoning

    A signal is therefore NOT globally normalized across all careers.
    """

    question_results = exploring_result.get(
        "question_results",
        [],
    )

    if not isinstance(
        question_results,
        list,
    ):
        raise Journey1SkillGapError(
            "exploring_result.json question_results "
            "must be a list."
        )

    evidence: Dict[
        str,
        Dict[str, Any],
    ] = {}

    unmapped = set()

    for question in question_results:

        if not isinstance(
            question,
            dict,
        ):
            continue

        question_id = str(
            question.get(
                "question_id"
            )
            or question.get(
                "id"
            )
            or ""
        ).strip()

        is_correct = bool(
            question.get(
                "is_correct"
            )
        )

        raw_signals = question.get(
            "behavior_signals",
            [],
        )

        if not isinstance(
            raw_signals,
            list,
        ):
            continue

        seen_canonical_this_question = set()

        for raw_signal in raw_signals:

            signal = _normalize_id(
                raw_signal
            )

            if not signal:
                continue

            canonical = career_normalization.get(
                signal
            )

            # ------------------------------------------------
            # Signal is not mapped for this career.
            #
            # This is NOT automatically an error.
            # It may simply be:
            # - diagnostic only
            # - relevant to another career
            # - not part of this career's normalization
            # ------------------------------------------------

            if not canonical:
                unmapped.add(signal)
                continue

            # ------------------------------------------------
            # Prevent duplicate counting inside one question
            # ------------------------------------------------

            if (
                canonical
                in seen_canonical_this_question
            ):
                continue

            seen_canonical_this_question.add(
                canonical
            )

            item = evidence.setdefault(
                canonical,
                {
                    "positive": 0,
                    "negative": 0,
                    "question_ids": set(),
                },
            )

            if is_correct:
                item["positive"] += 1
            else:
                item["negative"] += 1

            if question_id:
                item[
                    "question_ids"
                ].add(question_id)

    return (
        evidence,
        sorted(
            value
            for value in unmapped
            if value
        ),
    )


# ============================================================
# BUILD PRELIMINARY SKILL PROFILE
# ============================================================

def build_preliminary_skill_profile(
    exploring_result: Dict[str, Any],
    target_careers: List[str],
    matrix: Dict[str, Any],
    normalization: Dict[str, Dict[str, str]],
) -> Dict[str, Any]:
    """
    Build preliminary current skill profile and gap analysis.

    NO-EVIDENCE RULE:

        current_level = None
        gap = None
        priority = None/None label
        excluded from weak_areas
        excluded from skill_gap_analysis

    Evidence is collected separately for each target career.
    """

    # --------------------------------------------------------
    # Validate target careers
    # --------------------------------------------------------

    target_careers = [
        career
        for career in target_careers
        if career in CAREERS
    ]

    if not target_careers:
        raise Journey1SkillGapError(
            "No valid target careers supplied."
        )

    # --------------------------------------------------------
    # Required canonical skills
    #
    # If multiple target careers share a skill, keep the
    # highest target level.
    # --------------------------------------------------------

    required: Dict[
        str,
        Dict[str, Any],
    ] = {}

    skill_careers: Dict[
        str,
        List[str],
    ] = {}

    for career in target_careers:

        career_skills = _skill_records(
            matrix,
            career,
        )

        for skill_id, meta in career_skills.items():

            skill_careers.setdefault(
                skill_id,
                [],
            ).append(
                career
            )

            if (
                skill_id not in required
                or meta["target_level"]
                > required[
                    skill_id
                ]["target_level"]
            ):
                required[
                    skill_id
                ] = dict(meta)

    # --------------------------------------------------------
    # Collect evidence CAREER BY CAREER
    # --------------------------------------------------------

    career_evidence: Dict[
        str,
        Dict[str, Dict[str, Any]],
    ] = {}

    career_unmapped: Dict[
        str,
        List[str],
    ] = {}

    for career in target_careers:

        career_normalization = normalization.get(
            career,
            {},
        )

        evidence, unmapped = (
            _collect_evidence_for_career(
                exploring_result=exploring_result,
                career=career,
                career_normalization=career_normalization,
            )
        )

        career_evidence[
            career
        ] = evidence

        career_unmapped[
            career
        ] = unmapped

    # --------------------------------------------------------
    # Build canonical skill evidence
    #
    # Important:
    # A skill may be required by multiple careers.
    # Evidence is accepted if the relevant career mapping
    # provides evidence for that canonical skill.
    # --------------------------------------------------------

    evidence: Dict[
        str,
        Dict[str, Any],
    ] = {}

    for career in target_careers:

        for skill_id, ev in career_evidence[
            career
        ].items():

            item = evidence.setdefault(
                skill_id,
                {
                    "positive": 0,
                    "negative": 0,
                    "question_ids": set(),
                    "careers": set(),
                },
            )

            item[
                "positive"
            ] += ev["positive"]

            item[
                "negative"
            ] += ev["negative"]

            item[
                "question_ids"
            ].update(
                ev["question_ids"]
            )

            item[
                "careers"
            ].add(
                career
            )

    # --------------------------------------------------------
    # Build final skill items
    # --------------------------------------------------------

    skills = []
    strengths = []
    weak_areas = []

    for skill_id, meta in required.items():

        ev = evidence.get(
            skill_id
        )

        # ====================================================
        # NO EVIDENCE
        # ====================================================

        if (
            not ev
            or not ev["question_ids"]
        ):

            skills.append(
                {
                    "skill_id": skill_id,
                    "skill_name": meta["name"],
                    "category": meta["category"],
                    "weight": meta["weight"],
                    "current_level": None,
                    "current_level_label": "No Evidence",
                    "target_level": meta["target_level"],
                    "evidence_ratio": None,
                    "confidence": 0.0,
                    "evidence_questions": [],
                    "evidence_careers": [],
                    "evidence_status": "No Evidence",
                    "gap": None,
                    "gap_label": "No Evidence",
                    "priority": "None",
                }
            )

            continue

        # ====================================================
        # PRELIMINARY EVIDENCE
        # ====================================================

        total = (
            ev["positive"]
            + ev["negative"]
        )

        ratio = (
            ev["positive"]
            / total
            if total
            else 0.0
        )

        current_level = _level_from_evidence(
            ratio
        )

        confidence = _confidence(
            len(
                ev["question_ids"]
            ),
            ratio,
        )

        gap = max(
            meta["target_level"]
            - current_level,
            0,
        )

        item = {
            "skill_id": skill_id,
            "skill_name": meta["name"],
            "category": meta["category"],
            "weight": meta["weight"],
            "current_level": current_level,
            "current_level_label": LEVEL_LABELS[
                current_level
            ],
            "target_level": meta["target_level"],
            "evidence_ratio": round(
                ratio,
                2,
            ),
            "confidence": confidence,
            "evidence_questions": sorted(
                ev["question_ids"]
            ),
            "evidence_careers": sorted(
                ev["careers"]
            ),
            "positive_evidence": ev[
                "positive"
            ],
            "negative_evidence": ev[
                "negative"
            ],
            "evidence_status": (
                "Preliminary Evidence"
            ),
            "gap": gap,
            "gap_label": _gap_label(
                gap
            ),
            "priority": _priority(
                gap
            ),
        }

        skills.append(item)

        if gap == 0:
            strengths.append(item)

        elif gap > 0:
            weak_areas.append(item)

    # --------------------------------------------------------
    # Sort strengths
    # --------------------------------------------------------

    strengths.sort(
        key=lambda item: (
            -item["current_level"],
            item["skill_name"],
        )
    )

    # --------------------------------------------------------
    # Sort weak areas
    # --------------------------------------------------------

    weak_areas.sort(
        key=lambda item: (
            PRIORITY_ORDER[
                item["priority"]
            ],
            -item["gap"],
            (
                0
                if item["category"]
                == "core"
                else 1
            ),
            item["skill_name"],
        )
    )

    # --------------------------------------------------------
    # Sort all skills
    # --------------------------------------------------------

    skills.sort(
        key=lambda item: (
            (
                0
                if item["gap"] is not None
                else 1
            ),
            item["skill_name"],
        )
    )

    # --------------------------------------------------------
    # Unmapped signals
    # --------------------------------------------------------

    all_unmapped = set()

    for signals in career_unmapped.values():
        all_unmapped.update(
            signals
        )

    return {
        "skills": skills,
        "strengths": strengths,
        "weak_areas": weak_areas,
        "unmapped_behavior_signals": sorted(
            all_unmapped
        ),
        "career_unmapped_behavior_signals": (
            career_unmapped
        ),
    }


# ============================================================
# RECOMMENDED NEXT STEP
# ============================================================

def recommended_next_step(
    profile: Dict[str, Any],
) -> str:

    weak = profile[
        "weak_areas"
    ]

    if weak:

        high = [
            item
            for item in weak
            if item["priority"]
            == "High"
        ]

        if high:

            names = ", ".join(
                item["skill_name"]
                for item in high[:3]
            )

            return (
                "Begin guided practice on the "
                "highest-priority preliminary gaps: "
                f"{names}. Validate these skills later "
                "with deeper assessment or practical work."
            )

        names = ", ".join(
            item["skill_name"]
            for item in weak[:3]
        )

        return (
            "Strengthen these preliminary skill areas: "
            f"{names}. Use practical exercises to "
            "build stronger evidence."
        )

    if profile["strengths"]:

        return (
            "Preliminary evidence shows alignment with "
            "the target career. Move to practical projects "
            "to validate and strengthen these skills."
        )

    return (
        "Continue with practical exploration to collect "
        "stronger evidence; the current assessment alone "
        "does not provide enough skill evidence."
    )


# ============================================================
# FINAL RESULT
# ============================================================

def build_final_result(
    exploring_result_path: str | Path = (
        "exploring_result.json"
    ),
    recommendation_path: str | Path = (
        "exploring_recommendation.json"
    ),
    matrix_path: str | Path = (
        "career_skill_matrix.json"
    ),
    normalization_path: str | Path = (
        "skill_normalization.json"
    ),
    output_path: str | Path = (
        "journey1_final_result.json"
    ),
) -> Dict[str, Any]:

    # --------------------------------------------------------
    # Load canonical files
    # --------------------------------------------------------

    exploring = load_json(
        exploring_result_path
    )

    recommendation = load_json(
        recommendation_path
    )

    matrix = load_json(
        matrix_path
    )

    normalization_config = load_json(
        normalization_path
    )

    # --------------------------------------------------------
    # Read finalized career-specific mappings
    # --------------------------------------------------------

    normalization = (
        _extract_career_mappings(
            normalization_config
        )
    )

    # --------------------------------------------------------
    # Determine target career(s)
    # --------------------------------------------------------

    target_careers = _target_careers(
        recommendation
    )

    # --------------------------------------------------------
    # Build profile
    # --------------------------------------------------------

    profile = build_preliminary_skill_profile(
        exploring_result=exploring,
        target_careers=target_careers,
        matrix=matrix,
        normalization=normalization,
    )

    # --------------------------------------------------------
    # Mapping counts
    # --------------------------------------------------------

    career_mapping_counts = {
        career: len(
            normalization.get(
                career,
                {},
            )
        )
        for career in target_careers
    }

    mapped_signal_count = sum(
        career_mapping_counts.values()
    )

    # --------------------------------------------------------
    # Extract unmapped data
    # --------------------------------------------------------

    unmapped_behavior_signals = profile.pop(
        "unmapped_behavior_signals"
    )

    career_unmapped_behavior_signals = (
        profile.pop(
            "career_unmapped_behavior_signals"
        )
    )

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    final = {
        "journey": 1,

        "mode": "exploring",

        "status": (
            "preliminary_skill_evidence"
        ),

        # ----------------------------------------------------
        # Recommendation remains untouched.
        # ----------------------------------------------------

        "career_recommendation": recommendation,

        # ----------------------------------------------------
        # Career(s) receiving skill-gap analysis.
        # ----------------------------------------------------

        "target_careers": target_careers,

        # ----------------------------------------------------
        # Normalization information.
        # ----------------------------------------------------

        "skill_normalization": {
            "source": Path(
                normalization_path
            ).name,

            "mapping_structure": (
                "career_mappings[career].mappings"
            ),

            "mapped_signal_count": (
                mapped_signal_count
            ),

            "career_mapping_counts": (
                career_mapping_counts
            ),

            "unmapped_behavior_signals": (
                unmapped_behavior_signals
            ),

            "career_unmapped_behavior_signals": (
                career_unmapped_behavior_signals
            ),
        },

        # ----------------------------------------------------
        # Preliminary current skill profile
        # ----------------------------------------------------

        "preliminary_current_skill_profile": (
            profile["skills"]
        ),

        # ----------------------------------------------------
        # Only evidence-backed gaps
        #
        # No-Evidence skills are excluded.
        # ----------------------------------------------------

        "skill_gap_analysis": [
            item
            for item in profile[
                "weak_areas"
            ]
        ],

        # ----------------------------------------------------
        # Strengths
        # ----------------------------------------------------

        "strengths": [
            item["skill_name"]
            for item in profile[
                "strengths"
            ]
        ],

        "strength_details": profile[
            "strengths"
        ],

        # ----------------------------------------------------
        # Weak areas
        # ----------------------------------------------------

        "weak_areas": [
            item["skill_name"]
            for item in profile[
                "weak_areas"
            ]
        ],

        "weak_area_details": profile[
            "weak_areas"
        ],

        # ----------------------------------------------------
        # Recommended next step
        # ----------------------------------------------------

        "recommended_next_step": (
            recommended_next_step(
                profile
            )
        ),

        # ----------------------------------------------------
        # Evidence policy
        # ----------------------------------------------------

        "evidence_policy": {

            "evidence_type": (
                "preliminary"
            ),

            "max_questions_per_career": 2,

            "confidence_cap": 0.60,

            "preliminary_level_cap": 3,

            "no_evidence_is_not_a_skill_gap": True,

            "diagnostic_only_signals_excluded": True,

            "career_specific_normalization": True,

            "interpretation_rule": (
                "Never present Journey 1 evidence as "
                "definitive certification or expertise."
            ),
        },

        # ----------------------------------------------------
        # Canonical target source
        # ----------------------------------------------------

        "target_level_source": Path(
            matrix_path
        ).name,

        # ----------------------------------------------------
        # Gap formula
        # ----------------------------------------------------

        "gap_formula": (
            "max(target_level - current_level, 0)"
        ),

        "gap_labels": {
            "0": "No Gap",
            "1": "Low Gap",
            "2": "Moderate Gap",
            "3-4": "High Gap",
        },

        "priority_rules": {
            "gap >= 3": "High",
            "gap == 2": "Medium",
            "gap == 1": "Low",
            "gap == 0": "None",
        },
    }

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    output = Path(
        output_path
    )

    with output.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            final,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return final


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    try:

        result = build_final_result()

        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            )
        )

        print()
        print(
            "=" * 60
        )
        print(
            "JOURNEY 1 SKILL GAP PIPELINE: PASS"
        )
        print(
            "=" * 60
        )

    except Exception as exc:

        print()
        print(
            "=" * 60
        )
        print(
            "JOURNEY 1 SKILL GAP PIPELINE: FAILED"
        )
        print(
            "=" * 60
        )

        print(
            f"{type(exc).__name__}: {exc}"
        )

        raise