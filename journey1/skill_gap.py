"""
MINERVA — JOURNEY 1: PRELIMINARY SKILL GAP PIPELINE

Runs AFTER the existing Journey 1 career recommendation.

It does NOT modify:
- exploring_scoring.py
- exploring_ai.py
- exploring_recommendation.py
- Journey 2

Canonical sources:
- career_skill_matrix.json:
    target levels, categories, weights only

- skill_normalization.json:
    career-specific raw signal -> canonical skill mapping only

Journey 1 has very limited evidence.
Therefore:
- all skill evidence is preliminary
- confidence is conservative
- preliminary level is capped at 3
- No Evidence is NOT treated as a skill gap
- career-specific mappings are respected
- diagnostic-only mappings never contribute
- shared skills across multiple careers are handled conservatively
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

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

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
    """
    Normalize IDs/signals consistently.
    """

    if value is None:
        return ""

    return str(value).strip().lower()


def _safe_int(
    value: Any,
    field_name: str,
    context: str,
) -> int:

    try:
        return int(value)

    except (TypeError, ValueError):

        raise Journey1SkillGapError(
            f"Invalid integer value for "
            f"'{field_name}' in {context}: {value}"
        )


def _safe_float(
    value: Any,
    field_name: str,
    context: str,
) -> float:

    try:
        return float(value)

    except (TypeError, ValueError):

        raise Journey1SkillGapError(
            f"Invalid numeric value for "
            f"'{field_name}' in {context}: {value}"
        )


# ============================================================
# CAREER SKILL MATRIX
# ============================================================

def _skill_records(
    matrix: Dict[str, Any],
    career: str,
) -> Dict[str, Dict[str, Any]]:
    """
    Read required canonical skills for one career.

    IMPORTANT:
    target_level, category and weight ALWAYS come from
    career_skill_matrix.json.

    This function does NOT infer target levels from
    Exploring evidence.
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
            f"Invalid career configuration for "
            f"'{career}'."
        )

    raw = career_data.get("required_skills")

    if raw is None:

        raise Journey1SkillGapError(
            f"Career '{career}' does not contain "
            f"'required_skills'."
        )

    records: Dict[str, Dict[str, Any]] = {}

    # --------------------------------------------------------
    # Dictionary format
    # --------------------------------------------------------

    if isinstance(raw, dict):

        for skill_id, meta in raw.items():

            if not isinstance(meta, dict):

                raise Journey1SkillGapError(
                    f"Invalid skill metadata for "
                    f"'{career}:{skill_id}'."
                )

            canonical_id = _normalize_id(skill_id)

            if not canonical_id:

                raise Journey1SkillGapError(
                    f"Empty skill ID for career "
                    f"'{career}'."
                )

            if "target_level" not in meta:

                raise Journey1SkillGapError(
                    f"Missing target_level for "
                    f"'{career}:{skill_id}'."
                )

            target_level = _safe_int(
                meta["target_level"],
                "target_level",
                f"{career}:{skill_id}",
            )

            if not 1 <= target_level <= 5:

                raise Journey1SkillGapError(
                    f"target_level must be between "
                    f"1 and 5 for "
                    f"'{career}:{skill_id}'."
                )

            records[canonical_id] = {
                "id": canonical_id,
                "name": (
                    str(meta.get("name")).strip()
                    if meta.get("name")
                    else canonical_id.replace(
                        "_",
                        " ",
                    ).title()
                ),
                "target_level": target_level,
                "category": meta.get(
                    "category",
                    "supporting",
                ),
                "weight": _safe_float(
                    meta.get(
                        "weight",
                        1.0,
                    ),
                    "weight",
                    f"{career}:{skill_id}",
                ),
            }

        return records

    # --------------------------------------------------------
    # List format
    # --------------------------------------------------------

    if isinstance(raw, list):

        for item in raw:

            if (
                not isinstance(item, dict)
                or not item.get("id")
            ):

                raise Journey1SkillGapError(
                    f"Invalid required skill entry "
                    f"for career '{career}'."
                )

            skill_id = _normalize_id(
                item["id"]
            )

            if "target_level" not in item:

                raise Journey1SkillGapError(
                    f"Missing target_level for "
                    f"'{career}:{skill_id}'."
                )

            target_level = _safe_int(
                item["target_level"],
                "target_level",
                f"{career}:{skill_id}",
            )

            if not 1 <= target_level <= 5:

                raise Journey1SkillGapError(
                    f"target_level must be between "
                    f"1 and 5 for "
                    f"'{career}:{skill_id}'."
                )

            records[skill_id] = {
                "id": skill_id,
                "name": (
                    str(item.get("name")).strip()
                    if item.get("name")
                    else skill_id.replace(
                        "_",
                        " ",
                    ).title()
                ),
                "target_level": target_level,
                "category": item.get(
                    "category",
                    "supporting",
                ),
                "weight": _safe_float(
                    item.get(
                        "weight",
                        1.0,
                    ),
                    "weight",
                    f"{career}:{skill_id}",
                ),
            }

        return records

    raise Journey1SkillGapError(
        f"career_skill_matrix.json career "
        f"'{career}' must contain required_skills "
        f"as either an object or list."
    )


# ============================================================
# NORMALIZATION
# ============================================================

def _extract_career_mappings(
    config: Dict[str, Any],
) -> Tuple[
    Dict[str, Dict[str, str]],
    Dict[str, set[str]],
]:
    """
    Read the finalized career-specific normalization structure.

    Expected:

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

        normalization:
        {
            career: {
                source_signal: canonical_skill
            }
        }

        diagnostic_only:
        {
            career: {
                source_signal,
                ...
            }
        }

    Rules:
    - diagnostic_only never contributes
    - canonical_skill == null never contributes
    - career mappings remain career-specific
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

    diagnostic_only: Dict[
        str,
        set[str],
    ] = {}

    for career in CAREERS:

        career_config = career_mappings.get(
            career
        )

        if career_config is None:

            result[career] = {}
            diagnostic_only[career] = set()

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
        career_diagnostic_only: set[str] = set()

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
            # Diagnostic-only mapping
            # ------------------------------------------------

            if mapping_type == "diagnostic_only":

                source_id = _normalize_id(
                    source_skill
                )

                if source_id:

                    career_diagnostic_only.add(
                        source_id
                    )

                continue

            # ------------------------------------------------
            # Null source/canonical mapping
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

        diagnostic_only[
            career
        ] = career_diagnostic_only

    total_mappings = sum(
        len(mapping)
        for mapping in result.values()
    )

    if total_mappings == 0:

        raise Journey1SkillGapError(
            "skill_normalization.json contains no "
            "usable career-specific mappings."
        )

    return (
        result,
        diagnostic_only,
    )


# ============================================================
# TARGET CAREERS
# ============================================================

def _target_careers(
    recommendation: Dict[str, Any],
) -> List[str]:
    """
    Determine which career(s) should receive
    Skill Gap analysis.

    Supported recommendation types:
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

    rec_type = _normalize_id(
        rec.get(
            "type",
            "",
        )
    )

    # --------------------------------------------------------
    # Single primary
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

        if isinstance(
            tie,
            dict,
        ):

            tied = tie.get(
                "tied_career_ids",
                [],
            )

            if isinstance(
                tied,
                list,
            ):

                careers = []

                for value in tied:

                    career = _normalize_id(
                        value
                    )

                    if (
                        career in CAREERS
                        and career not in careers
                    ):

                        careers.append(
                            career
                        )

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

    Journey 1 evidence is intentionally capped at level 3.

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

    1 question -> maximum base 0.35
    2 questions -> maximum base 0.50
    Absolute hard cap -> 0.60

    Confidence is based on evidence belonging to the
    same career, not another career.
    """

    if question_count <= 0:
        return 0.0

    base = {
        1: 0.35,
        2: 0.50,
    }.get(
        min(
            question_count,
            2,
        ),
        0.50,
    )

    consistency = (
        0.5
        + (
            0.5
            * max(
                0.0,
                min(
                    evidence_ratio,
                    1.0,
                ),
            )
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
    career_diagnostic_only: set[str],
    required_skill_ids: set[str],
) -> Tuple[
    Dict[str, Dict[str, Any]],
    List[str],
]:
    """
    Convert Exploring behavior signals into canonical skills
    using ONLY the normalization mappings for the target career.

    Important:
    A mapping is usable only when its canonical target is
    actually required by that career.

    This prevents unrelated normalization entries from
    being counted as usable skill evidence.
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

            # ------------------------------------------------
            # Diagnostic-only signal
            # ------------------------------------------------

            if signal in career_diagnostic_only:

                continue

            # ------------------------------------------------
            # No mapping for this career
            # ------------------------------------------------

            canonical = career_normalization.get(
                signal
            )

            if not canonical:

                unmapped.add(
                    signal
                )

                continue

            # ------------------------------------------------
            # Mapping exists, but canonical skill is NOT
            # required by this target career.
            #
            # This is intentionally ignored rather than
            # counted as usable evidence.
            # ------------------------------------------------

            if canonical not in required_skill_ids:

                continue

            # ------------------------------------------------
            # Prevent duplicate counting of the same
            # canonical skill inside one question.
            # ------------------------------------------------

            if canonical in seen_canonical_this_question:

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
                ].add(
                    question_id
                )

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
    diagnostic_only: Dict[str, set[str]],
) -> Dict[str, Any]:
    """
    Build preliminary current skill profile and gap analysis.

    IMPORTANT DESIGN RULES:

    1. Evidence is collected separately for every career.
    2. Shared canonical skills are NOT allowed to inflate
       evidence merely because the same skill appears in
       multiple career mappings.
    3. No Evidence remains None.
    4. No Evidence is excluded from weak_areas and
       skill_gap_analysis.
    5. Confidence remains conservative.
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

    # Remove duplicates while preserving order.

    target_careers = list(
        dict.fromkeys(
            target_careers
        )
    )

    # --------------------------------------------------------
    # Load required skills PER CAREER
    # --------------------------------------------------------

    career_required_skills: Dict[
        str,
        Dict[str, Dict[str, Any]],
    ] = {}

    for career in target_careers:

        career_required_skills[
            career
        ] = _skill_records(
            matrix,
            career,
        )

    # --------------------------------------------------------
    # Collect evidence PER CAREER
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

        required_skill_ids = set(
            career_required_skills[
                career
            ].keys()
        )

        evidence, unmapped = (
            _collect_evidence_for_career(
                exploring_result=exploring_result,
                career=career,
                career_normalization=normalization.get(
                    career,
                    {},
                ),
                career_diagnostic_only=diagnostic_only.get(
                    career,
                    set(),
                ),
                required_skill_ids=required_skill_ids,
            )
        )

        career_evidence[
            career
        ] = evidence

        career_unmapped[
            career
        ] = unmapped

    # --------------------------------------------------------
    # Build career-specific skill items.
    #
    # This is the important correction:
    #
    # If two target careers require the same canonical skill,
    # each career keeps its OWN evidence and target metadata.
    #
    # We do not combine:
    #
    #     Career A evidence
    #     +
    #     Career B evidence
    #
    # into an artificially stronger single evidence score.
    # --------------------------------------------------------

    skills = []
    strengths = []
    weak_areas = []

    for career in target_careers:

        career_skills = career_required_skills[
            career
        ]

        career_evidence_map = career_evidence[
            career
        ]

        for skill_id, meta in career_skills.items():

            ev = career_evidence_map.get(
                skill_id
            )

            # ====================================================
            # NO EVIDENCE
            # ====================================================

            if (
                not ev
                or not ev["question_ids"]
            ):

                item = {
                    "career": career,
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
                    "positive_evidence": 0,
                    "negative_evidence": 0,
                    "evidence_status": "No Evidence",
                    "gap": None,
                    "gap_label": "No Evidence",
                    "priority": "None",
                }

                skills.append(
                    item
                )

                continue

            # ====================================================
            # PRELIMINARY EVIDENCE
            # ====================================================

            positive = int(
                ev["positive"]
            )

            negative = int(
                ev["negative"]
            )

            total = positive + negative

            if total <= 0:

                item = {
                    "career": career,
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
                    "positive_evidence": 0,
                    "negative_evidence": 0,
                    "evidence_status": "No Evidence",
                    "gap": None,
                    "gap_label": "No Evidence",
                    "priority": "None",
                }

                skills.append(
                    item
                )

                continue

            ratio = (
                positive / total
            )

            current_level = (
                _level_from_evidence(
                    ratio
                )
            )

            question_count = len(
                ev["question_ids"]
            )

            confidence = _confidence(
                question_count,
                ratio,
            )

            gap = max(
                meta["target_level"]
                - current_level,
                0,
            )

            item = {
                "career": career,
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
                "evidence_careers": [
                    career
                ],
                "positive_evidence": positive,
                "negative_evidence": negative,
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

            skills.append(
                item
            )

            # ----------------------------------------------------
            # Strength vs. weak area
            # ----------------------------------------------------
            # IMPORTANT FIX:
            # Previously this used gap == 0 for "strength" and
            # gap > 0 for "weak area". That meant a skill with
            # current_level 3 ("Functional"), positive-only
            # evidence, and a Low-priority remaining gap (e.g.
            # target_level 4) was labeled a weak area even though
            # it is demonstrated, evidence-backed competence with
            # some remaining room to grow.
            #
            # A skill is now treated as a strength whenever the
            # evidence shows current_level >= 3 ("Functional" or
            # higher), regardless of whether a gap remains to a
            # higher target_level. The gap/priority fields on the
            # item itself still communicate that remaining
            # development need — the skill is not duplicated into
            # weak_areas as well.
            #
            # weak_areas is reserved for skills where the
            # evidence itself shows current_level < 3 (i.e.
            # "Needs Foundation" / "Developing" — negative or
            # weak evidence), which is a genuine current weakness
            # rather than a strength with room to grow.
            # ----------------------------------------------------

            if current_level >= 3:

                strengths.append(
                    item
                )

            elif gap > 0:

                weak_areas.append(
                    item
                )

    # ========================================================
    # SORT STRENGTHS
    # ========================================================

    strengths.sort(
        key=lambda item: (
            -item["current_level"],
            item["career"],
            item["skill_name"],
        )
    )

    # ========================================================
    # SORT WEAK AREAS
    # ========================================================

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
            item["career"],
            item["skill_name"],
        )
    )

    # ========================================================
    # SORT ALL SKILLS
    # ========================================================

    skills.sort(
        key=lambda item: (
            (
                0
                if item["gap"] is not None
                else 1
            ),
            item["career"],
            item["skill_name"],
        )
    )

    # ========================================================
    # UNMAPPED SIGNALS
    # ========================================================

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
                (
                    f"{item['career']}: "
                    f"{item['skill_name']}"
                )
                for item in high[:3]
            )

            return (
                "Begin guided practice on the "
                "highest-priority preliminary gaps: "
                f"{names}. Validate these skills later "
                "with deeper assessment or practical work."
            )

        names = ", ".join(
            (
                f"{item['career']}: "
                f"{item['skill_name']}"
            )
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
# MAPPED SIGNAL COUNT
# ============================================================

def _count_mapped_behavior_signals(
    exploring_result: Dict[str, Any],
    target_careers: List[str],
    normalization: Dict[str, Dict[str, str]],
    diagnostic_only: Dict[str, set[str]],
    career_required_skills: Dict[
        str,
        Dict[str, Dict[str, Any]],
    ],
) -> Tuple[
    int,
    List[str],
]:
    """
    Count unique behavior signals that are actually usable.

    A signal counts as mapped ONLY when:

        signal exists in Exploring
        AND
        signal has a usable mapping for at least one target career
        AND
        mapped canonical skill is required by that career
        AND
        signal is not diagnostic-only.

    This prevents unrelated mappings from inflating
    mapped_signal_count.
    """

    all_behavior_signals = set()

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

    for question in question_results:

        if not isinstance(
            question,
            dict,
        ):
            continue

        signals = question.get(
            "behavior_signals",
            [],
        )

        if not isinstance(
            signals,
            list,
        ):
            continue

        for signal in signals:

            normalized_signal = _normalize_id(
                signal
            )

            if normalized_signal:

                all_behavior_signals.add(
                    normalized_signal
                )

    mapped_signals = set()

    for career in target_careers:

        career_mapping = normalization.get(
            career,
            {},
        )

        career_diagnostic = diagnostic_only.get(
            career,
            set(),
        )

        required_skill_ids = set(
            career_required_skills[
                career
            ].keys()
        )

        for signal in all_behavior_signals:

            if signal in career_diagnostic:
                continue

            canonical = career_mapping.get(
                signal
            )

            if not canonical:
                continue

            if canonical not in required_skill_ids:
                continue

            mapped_signals.add(
                signal
            )

    unmapped_signals = sorted(
        all_behavior_signals
        - mapped_signals
    )

    return (
        len(mapped_signals),
        unmapped_signals,
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

    # ========================================================
    # LOAD FILES
    # ========================================================

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

    # ========================================================
    # NORMALIZATION
    # ========================================================

    (
        normalization,
        diagnostic_only,
    ) = _extract_career_mappings(
        normalization_config
    )

    # ========================================================
    # TARGET CAREERS
    # ========================================================

    target_careers = _target_careers(
        recommendation
    )

    # ========================================================
    # LOAD REQUIRED SKILLS FOR TARGET CAREERS
    # ========================================================

    career_required_skills = {}

    for career in target_careers:

        career_required_skills[
            career
        ] = _skill_records(
            matrix,
            career,
        )

    # ========================================================
    # BUILD PRELIMINARY PROFILE
    # ========================================================

    profile = build_preliminary_skill_profile(
        exploring_result=exploring,
        target_careers=target_careers,
        matrix=matrix,
        normalization=normalization,
        diagnostic_only=diagnostic_only,
    )

    # ========================================================
    # CAREER MAPPING COUNTS
    # ========================================================

    career_mapping_counts = {}

    for career in target_careers:

        career_mapping_counts[
            career
        ] = len(
            normalization.get(
                career,
                {},
            )
        )

    # ========================================================
    # MAPPED SIGNAL COUNT
    # ========================================================

    (
        mapped_behavior_signal_count,
        calculated_unmapped_signals,
    ) = _count_mapped_behavior_signals(
        exploring_result=exploring,
        target_careers=target_careers,
        normalization=normalization,
        diagnostic_only=diagnostic_only,
        career_required_skills=career_required_skills,
    )

    # ========================================================
    # UNMAPPED DATA
    # ========================================================

    profile_unmapped = profile.pop(
        "unmapped_behavior_signals"
    )

    # Use the profile's career-aware unmapped information.

    career_unmapped_behavior_signals = (
        profile.pop(
            "career_unmapped_behavior_signals"
        )
    )

    # --------------------------------------------------------
    # Combine calculated and profile-level unmapped signals.
    # --------------------------------------------------------

    unmapped_behavior_signals = sorted(
        set(profile_unmapped)
        | set(calculated_unmapped_signals)
    )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    final = {

        # ----------------------------------------------------
        # Journey metadata
        # ----------------------------------------------------

        "journey": 1,

        "mode": "exploring",

        "status": (
            "preliminary_skill_evidence"
        ),

        # ----------------------------------------------------
        # Original recommendation
        #
        # NEVER modified.
        # ----------------------------------------------------

        "career_recommendation": (
            recommendation
        ),

        # ----------------------------------------------------
        # Target careers
        # ----------------------------------------------------

        "target_careers": (
            target_careers
        ),

        # ----------------------------------------------------
        # Normalization information
        # ----------------------------------------------------

        "skill_normalization": {

            "source": Path(
                normalization_path
            ).name,

            "mapping_structure": (
                "career_mappings[career].mappings"
            ),

            "mapped_signal_count": (
                mapped_behavior_signal_count
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
        # Evidence-backed gaps only
        #
        # No Evidence is excluded.
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
            (
                f"{item['career']}: "
                f"{item['skill_name']}"
            )
            for item in profile[
                "strengths"
            ]
        ],

        "strength_details": (
            profile["strengths"]
        ),

        # ----------------------------------------------------
        # Weak areas
        # ----------------------------------------------------

        "weak_areas": [
            (
                f"{item['career']}: "
                f"{item['skill_name']}"
            )
            for item in profile[
                "weak_areas"
            ]
        ],

        "weak_area_details": (
            profile["weak_areas"]
        ),

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

            "shared_skill_evidence_is_not_cross_career_inflated": True,

            "mapped_signal_requires_required_skill": True,

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

        # ----------------------------------------------------
        # Gap labels
        # ----------------------------------------------------

        "gap_labels": {

            "0": "No Gap",

            "1": "Low Gap",

            "2": "Moderate Gap",

            "3-4": "High Gap",
        },

        # ----------------------------------------------------
        # Priority rules
        # ----------------------------------------------------

        "priority_rules": {

            "gap >= 3": "High",

            "gap == 2": "Medium",

            "gap == 1": "Low",

            "gap == 0": "None",
        },
    }

    # ========================================================
    # SAVE
    # ========================================================

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