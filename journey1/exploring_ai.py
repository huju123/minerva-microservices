"""
============================================================
MINERVA — JOURNEY 1: EXPLORING
Local Interpretation Engine — FINAL v5.1
============================================================

Purpose:
    Takes the deterministic result produced by
    exploring_scoring.py and generates a local,
    rule-based interpretation.

Architecture:

    Deterministic Scoring Engine
                ↓
        exploring_result.json
                ↓
        Safe Interpretation Context
                ↓
      Local Rule-Based Engine
                ↓
      exploring_ai_result.json

IMPORTANT DESIGN RULES:

    1. No OpenAI API.
    2. No API key.
    3. No internet.
    4. No external AI package.
    5. Deterministic scoring remains the source of truth.
    6. This file does NOT calculate career scores.
    7. This file does NOT determine correct answers.
    8. This file does NOT receive selected answers.
    9. This file does NOT receive answer keys.
    10. This file does NOT receive question text.
    11. This file only interprets already-computed results.
    12. Deterministic rankings are never changed.
    13. Career recommendations must already exist in
        deterministic career_scores.
    14. Career ties are respected.
    15. Complete ties are handled safely.
    16. A 0-0-0-0-0 result is treated as a complete tie.
    17. The interpretation is deterministic and reproducible.
    18. Deterministic dimensions are a LIST.
============================================================
"""

import json
import sys

from pathlib import Path
from typing import Any, Dict, List, Set


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

ASSESSMENT_FILE = BASE_DIR / "assessment.json"
SCORING_RESULT_FILE = BASE_DIR / "exploring_result.json"
AI_RESULT_FILE = BASE_DIR / "exploring_ai_result.json"

EXPECTED_CAREER_COUNT = 5
EXPECTED_EXPLORING_QUESTIONS = 10
EXPECTED_QUESTIONS_PER_CAREER = 2

JOURNEY_NUMBER = 1
JOURNEY_MODE = "exploring"

ENGINE_NAME = "exploring_ai.py"
ENGINE_TYPE = "local_rule_based"
ENGINE_VERSION = "5.1"


# ============================================================
# GENERAL HELPERS
# ============================================================

def load_json(path: Path) -> Dict[str, Any]:
    """
    Load a JSON object from disk.
    """

    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path.name}"
        )

    try:
        with path.open(
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)

    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {path.name}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"{path.name} must contain a JSON object."
        )

    return data


def save_json(
    path: Path,
    data: Dict[str, Any]
) -> None:
    """
    Save JSON in readable UTF-8 format.
    """

    with path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False
        )


def normalize_text(value: Any) -> str:
    """
    Convert any value safely to trimmed text.
    """

    if value is None:
        return ""

    return str(value).strip()


def clean_display_text(value: Any) -> str:
    """
    Clean text for student-facing display.

    This function only fixes formatting.
    It does not change deterministic meaning.
    """

    text = normalize_text(value)

    if not text:
        return ""

    replacements = {
        "UI/UXDesign": "UI/UX Design",
        "SoftwareDevelopment": "Software Development",
        "Data&Analytics": "Data & Analytics",
        "AI&MachineLearning": "AI & Machine Learning",
        "User-CenteredDesign": "User-Centered Design",
        "LogicalProblemSolving": "Logical Problem Solving",
        "MachineLearning": "Machine Learning",
        "DataScience": "Data Science",
        "WebDevelopment": "Web Development",
        "CyberSecurity": "Cybersecurity",
        "treatedas": "treated as",
        "practiceand": "practice and",
        "continuedeveloping": "continue developing",
        "strongsignal": "strong signal",
        "areasrather": "areas rather",
        "narrowingyour": "narrowing your",
    }

    for old, new in replacements.items():
        text = text.replace(
            old,
            new
        )

    while "  " in text:
        text = text.replace(
            "  ",
            " "
        )

    return text.strip()


def safe_int(
    value: Any,
    default: int = 0
) -> int:
    """
    Safely convert value to integer.
    """

    try:
        return int(value)

    except (ValueError, TypeError):
        return default


def safe_float(
    value: Any,
    default: float = 0.0
) -> float:
    """
    Safely convert value to float.
    """

    try:
        return float(value)

    except (ValueError, TypeError):
        return default


def format_percentage(value: Any) -> str:
    """
    Format percentage for readable display.
    """

    number = safe_float(
        value,
        0.0
    )

    if number.is_integer():
        return f"{int(number)}%"

    return f"{number:.2f}%"


def percentage_from_score(
    score: Any,
    max_score: Any
) -> float:
    """
    Calculate percentage only for interpretation/display.

    This does NOT modify deterministic scoring.
    """

    score_value = safe_float(
        score,
        0.0
    )

    max_value = safe_float(
        max_score,
        0.0
    )

    if max_value <= 0:
        return 0.0

    return round(
        (score_value / max_value) * 100,
        2
    )


# ============================================================
# ASSESSMENT VALIDATION
# ============================================================

def validate_assessment(
    assessment: Dict[str, Any]
) -> None:
    """
    Validate only the assessment structure required by
    the local interpretation engine.
    """

    required = [
        "assessment_id",
        "version",
        "careers",
        "dimensions"
    ]

    missing = [
        key
        for key in required
        if key not in assessment
    ]

    if missing:
        raise ValueError(
            "assessment.json is missing required fields: "
            + ", ".join(missing)
        )

    careers = assessment.get(
        "careers"
    )

    if not isinstance(
        careers,
        list
    ):
        raise ValueError(
            "'careers' must be a list."
        )

    if len(careers) != EXPECTED_CAREER_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_CAREER_COUNT} careers, "
            f"found {len(careers)}."
        )

    career_ids: Set[str] = set()

    for career in careers:

        if not isinstance(
            career,
            dict
        ):
            raise ValueError(
                "Every career must be an object."
            )

        career_id = normalize_text(
            career.get(
                "id"
            )
            or career.get(
                "career_id"
            )
            or career.get("career"
            )   
        )

        if not career_id:
            raise ValueError(
                "Every career must have an id."
            )

        if career_id in career_ids:
            raise ValueError(
                f"Duplicate career ID: {career_id}"
            )

        career_ids.add(
            career_id
        )

    dimensions = assessment.get(
        "dimensions"
    )

    if not isinstance(
        dimensions,
        dict
    ):
        raise ValueError(
            "assessment.json 'dimensions' must be an object."
        )


# ============================================================
# CAREER LOOKUP
# ============================================================

def build_career_lookup(
    assessment: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """
    Build:

        career_id -> career metadata
    """

    lookup: Dict[str, Dict[str, Any]] = {}

    careers = assessment.get(
        "careers",
        []
    )

    if not isinstance(
        careers,
        list
    ):
        return lookup

    for career in careers:

        if not isinstance(
            career,
            dict
        ):
            continue

        career_id = normalize_text(
            career.get("id")
            or career.get("career_id")
        )

        if not career_id:
            continue

        career_name = normalize_text(
            career.get("name")
            or career.get("career_name")
            or career.get("title")
        )

        lookup[career_id] = {
            "career_id": career_id,
            "career_name": (
                clean_display_text(
                    career_name
                )
                or career_id
            ),
            "primary_dimension": normalize_text(
                career.get(
                    "primary_dimension"
                )
            ),
            "primary_dimension_name": clean_display_text(
                career.get(
                    "primary_dimension_name"
                )
            ),
            "secondary_dimensions": (
                career.get(
                    "secondary_dimensions",
                    []
                )
                if isinstance(
                    career.get(
                        "secondary_dimensions",
                        []
                    ),
                    list
                )
                else []
            )
        }

    return lookup


def get_career_id(
    career_data: Any
) -> str:
    """
    Extract career ID from supported formats.
    """

    if isinstance(
        career_data,
        dict
    ):
        return normalize_text(
            career_data.get(
                "career_id"
            )
            or career_data.get(
                "id"
            )or career_data.get("career")
        )

    return normalize_text(
        career_data
    )


def get_career_name(
    career_data: Any,
    career_lookup: Dict[str, Dict[str, Any]]
) -> str:
    """
    Extract readable career name.
    """

    career_id = get_career_id(
        career_data
    )

    if isinstance(
        career_data,
        dict
    ):

        direct_name = normalize_text(
            career_data.get(
                "career_name"
            )
            or career_data.get(
                "name"
            )
            or career_data.get(
                "career"
            )
        )

        if direct_name:
            return clean_display_text(
                direct_name
            )

    if career_id in career_lookup:
        return clean_display_text(
            career_lookup[career_id].get(
                "career_name"
            )
        )

    return clean_display_text(
        career_id
    )


# ============================================================
# DIMENSION HELPERS
# ============================================================

def make_dimension_name(
    dimension_id: str
) -> str:
    """
    Convert an internal dimension ID into readable text.
    """

    dimension_id = normalize_text(
        dimension_id
    )

    if not dimension_id:
        return ""

    return " ".join(
        word.capitalize()
        for word in dimension_id.split("_")
    )


def build_dimension_lookup(
    assessment: Dict[str, Any]
) -> Dict[str, str]:
    """
    Build:

        dimension_id -> readable dimension name

    NOTE:
        This reads assessment.json metadata.

        It is completely separate from the deterministic
        result's `dimensions`, which is a LIST.
    """

    lookup: Dict[str, str] = {}

    dimensions = assessment.get(
        "dimensions",
        {}
    )

    if not isinstance(
        dimensions,
        dict
    ):
        return lookup

    # --------------------------------------------------------
    # Primary dimensions
    # --------------------------------------------------------

    primary = dimensions.get(
        "primary",
        []
    )

    if isinstance(
        primary,
        list
    ):

        for dimension in primary:

            if not isinstance(
                dimension,
                dict
            ):
                continue

            dimension_id = normalize_text(
                dimension.get(
                    "id"
                )
            )

            dimension_name_value = normalize_text(
                dimension.get(
                    "name"
                )
            )

            if dimension_id:

                lookup[dimension_id] = (
                    clean_display_text(
                        dimension_name_value
                    )
                    or make_dimension_name(
                        dimension_id
                    )
                )

    # --------------------------------------------------------
    # Secondary dimensions
    # --------------------------------------------------------

    secondary = dimensions.get(
        "secondary",
        []
    )

    if isinstance(
        secondary,
        list
    ):

        for dimension in secondary:

            if not isinstance(
                dimension,
                dict
            ):
                continue

            dimension_id = normalize_text(
                dimension.get(
                    "id"
                )
            )

            dimension_name_value = normalize_text(
                dimension.get(
                    "name"
                )
            )

            if dimension_id:

                lookup[dimension_id] = (
                    clean_display_text(
                        dimension_name_value
                    )
                    or make_dimension_name(
                        dimension_id
                    )
                )

    # --------------------------------------------------------
    # Career-level mappings
    # --------------------------------------------------------

    for career in assessment.get(
        "careers",
        []
    ):

        if not isinstance(
            career,
            dict
        ):
            continue

        primary_id = normalize_text(
            career.get(
                "primary_dimension"
            )
        )

        primary_name = normalize_text(
            career.get(
                "primary_dimension_name"
            )
        )

        if primary_id:

            lookup[primary_id] = (
                clean_display_text(
                    primary_name
                )
                or lookup.get(
                    primary_id,
                    make_dimension_name(
                        primary_id
                    )
                )
            )

        secondary_ids = career.get(
            "secondary_dimensions",
            []
        )

        if isinstance(
            secondary_ids,
            list
        ):

            for secondary_id in secondary_ids:

                secondary_id = normalize_text(
                    secondary_id
                )

                if (
                    secondary_id
                    and secondary_id not in lookup
                ):

                    lookup[secondary_id] = (
                        make_dimension_name(
                            secondary_id
                        )
                    )

    return lookup


def dimension_name(
    dimension_id: str,
    lookup: Dict[str, str]
) -> str:
    """
    Return readable dimension name.
    """

    dimension_id = normalize_text(
        dimension_id
    )

    if not dimension_id:
        return ""

    return clean_display_text(
        lookup.get(
            dimension_id,
            make_dimension_name(
                dimension_id
            )
        )
    )


# ============================================================
# DETERMINISTIC RESULT VALIDATION
# ============================================================

def validate_result_career_reference(
    career_data: Any,
    career_lookup: Dict[str, Dict[str, Any]],
    field_name: str
) -> None:
    """
    Validate a top_career / second_career reference.
    """

    if not isinstance(
        career_data,
        dict
    ):
        raise ValueError(
            f"'{field_name}' must be an object."
        )

    career_id = get_career_id(
        career_data
    )

    if not career_id:
        raise ValueError(
            f"'{field_name}' is missing career_id."
        )

    if career_id not in career_lookup:
        raise ValueError(
            f"'{field_name}' references unknown career "
            f"'{career_id}'."
        )


def validate_scoring_result(
    result: Dict[str, Any],
    assessment: Dict[str, Any]
) -> None:
    """
    Validate schema produced by exploring_scoring.py.

    IMPORTANT:
        dimensions is validated as a LIST.

    This function does not recalculate the assessment.
    It only verifies structural consistency and safety.
    """

    required = [
        "journey",
        "mode",
        "assessment_id",
        "assessment_version",
        "total_questions",
        "answered_questions",
        "total_correct",
        "career_scores",
        "top_career",
        "second_career",
        "dimensions",
        "strengths",
        "improvement_areas"
    ]

    missing = [
        key
        for key in required
        if key not in result
    ]

    if missing:
        raise ValueError(
            "exploring_result.json is missing required fields: "
            + ", ".join(missing)
        )

    if safe_int(
        result.get("journey"),
        -1
    ) != JOURNEY_NUMBER:

        raise ValueError(
            "exploring_result.json must have journey = 1."
        )

    if normalize_text(
        result.get("mode")
    ).lower() != JOURNEY_MODE:

        raise ValueError(
            "exploring_result.json must have "
            "mode = 'exploring'."
        )

    # --------------------------------------------------------
    # Assessment identity
    # --------------------------------------------------------

    assessment_id = normalize_text(
        assessment.get(
            "assessment_id"
        )
    )

    result_assessment_id = normalize_text(
        result.get(
            "assessment_id"
        )
    )

    if result_assessment_id != assessment_id:

        raise ValueError(
            "Assessment ID mismatch between assessment.json "
            f"('{assessment_id}') and exploring_result.json "
            f"('{result_assessment_id}')."
        )

    assessment_version = normalize_text(
        assessment.get(
            "version"
        )
    )

    result_version = normalize_text(
        result.get(
            "assessment_version"
        )
    )

    if result_version != assessment_version:

        raise ValueError(
            "Assessment version mismatch between assessment.json "
            f"('{assessment_version}') and exploring_result.json "
            f"('{result_version}')."
        )

    # --------------------------------------------------------
    # Question counts
    # --------------------------------------------------------

    total_questions = safe_int(
        result.get(
            "total_questions"
        ),
        -1
    )

    answered_questions = safe_int(
        result.get(
            "answered_questions"
        ),
        -1
    )

    total_correct = safe_int(
        result.get(
            "total_correct"
        ),
        -1
    )

    if total_questions != EXPECTED_EXPLORING_QUESTIONS:

        raise ValueError(
            f"Expected {EXPECTED_EXPLORING_QUESTIONS} "
            f"questions, found {total_questions}."
        )

    if answered_questions < 0:
        raise ValueError(
            "'answered_questions' cannot be negative."
        )

    if answered_questions > total_questions:

        raise ValueError(
            "'answered_questions' cannot exceed "
            "'total_questions'."
        )

    if total_correct < 0:
        raise ValueError(
            "'total_correct' cannot be negative."
        )

    if total_correct > answered_questions:

        raise ValueError(
            "'total_correct' cannot exceed "
            "'answered_questions'."
        )

    # --------------------------------------------------------
    # Career scores
    # --------------------------------------------------------

    career_lookup = build_career_lookup(
        assessment
    )

    career_scores = result.get(
        "career_scores"
    )

    if not isinstance(
        career_scores,
        list
    ):

        raise ValueError(
            "'career_scores' must be a list."
        )

    if len(career_scores) != EXPECTED_CAREER_COUNT:

        raise ValueError(
            f"Expected {EXPECTED_CAREER_COUNT} career scores, "
            f"found {len(career_scores)}."
        )

    seen_ids: Set[str] = set()

    for item in career_scores:

        if not isinstance(
            item,
            dict
        ):
            raise ValueError(
                "Every career score must be an object."
            )

        career_id = get_career_id(
            item
        )

        if not career_id:
            raise ValueError(
                "Career score is missing career_id."
            )

        if career_id in seen_ids:
            raise ValueError(
                f"Duplicate career score: {career_id}"
            )

        seen_ids.add(
            career_id
        )

        if career_id not in career_lookup:

            raise ValueError(
                f"Career score references unknown career "
                f"'{career_id}'."
            )

        career_name = get_career_name(
            item,
            career_lookup
        )

        expected_name = career_lookup[
            career_id
        ].get(
            "career_name",
            ""
        )

        if (
            clean_display_text(
                career_name
            ).lower()
            != clean_display_text(
                expected_name
            ).lower()
        ):

            raise ValueError(
                f"Career name mismatch for '{career_id}': "
                f"result='{career_name}', "
                f"assessment='{expected_name}'."
            )

    if seen_ids != set(
        career_lookup.keys()
    ):

        missing_ids = (
            set(career_lookup.keys())
            - seen_ids
        )

        extra_ids = (
            seen_ids
            - set(career_lookup.keys())
        )

        raise ValueError(
            "Career score IDs do not exactly match "
            "assessment careers. "
            f"Missing={sorted(missing_ids)}, "
            f"Extra={sorted(extra_ids)}."
        )

    # --------------------------------------------------------
    # Top and second career
    # --------------------------------------------------------

    for field in [
        "top_career",
        "second_career"
    ]:

        validate_result_career_reference(
            result.get(field),
            career_lookup,
            field
        )

    # --------------------------------------------------------
    # DIMENSIONS
    #
    # CURRENT exploring_scoring.py SCHEMA:
    #
    # "dimensions": [
    #     {
    #         "dimension": "Problem Solving",
    #         "correct": 2,
    #         "total": 2,
    #         "percentage": 100,
    #         "level": "Strong"
    #     }
    # ]
    # --------------------------------------------------------

    dimensions = result.get(
        "dimensions"
    )

    if not isinstance(
        dimensions,
        list
    ):

        raise ValueError(
            "'dimensions' must be a list."
        )

    for index, item in enumerate(
        dimensions
    ):

        if not isinstance(
            item,
            dict
        ):

            raise ValueError(
                f"dimensions[{index}] must be an object."
            )

        required_dimension_fields = [
            "dimension",
            "correct",
            "total",
            "percentage",
            "level"
        ]

        missing_fields = [
            field
            for field in required_dimension_fields
            if field not in item
        ]

        if missing_fields:

            raise ValueError(
                f"dimensions[{index}] is missing fields: "
                + ", ".join(
                    missing_fields
                )
            )

        name = clean_display_text(
            item.get(
                "dimension"
            )
        )

        if not name:

            raise ValueError(
                f"dimensions[{index}].dimension "
                "cannot be empty."
            )

        correct = safe_int(
            item.get(
                "correct"
            ),
            -1
        )

        total = safe_int(
            item.get(
                "total"
            ),
            -1
        )

        percentage = safe_float(
            item.get(
                "percentage"
            ),
            -1.0
        )

        if correct < 0:

            raise ValueError(
                f"dimensions[{index}].correct "
                "cannot be negative."
            )

        if total < 0:

            raise ValueError(
                f"dimensions[{index}].total "
                "cannot be negative."
            )

        if correct > total:

            raise ValueError(
                f"dimensions[{index}].correct "
                "cannot exceed total."
            )

        if percentage < 0 or percentage > 100:

            raise ValueError(
                f"dimensions[{index}].percentage "
                "must be between 0 and 100."
            )

        expected_percentage = (
            percentage_from_score(
                correct,
                total
            )
        )

        if abs(
            percentage
            - expected_percentage
        ) > 0.01:

            raise ValueError(
                f"dimensions[{index}].percentage is "
                "inconsistent with correct/total."
            )

        level = clean_display_text(
            item.get(
                "level"
            )
        )

        if not level:

            raise ValueError(
                f"dimensions[{index}].level "
                "cannot be empty."
            )

    # --------------------------------------------------------
    # Strengths / improvement areas
    # --------------------------------------------------------

    if not isinstance(
        result.get("strengths"),
        list
    ):

        raise ValueError(
            "'strengths' must be a list."
        )
    
    improvement_areas_value = result.get("improvement_areas")
    


    if not isinstance(
        improvement_areas_value,
        dict
    ):

        raise ValueError(
            "'improvement_areas' must be an object with "
            "'dimensions' and 'questions' lists."
        )
    if not isinstance(
        improvement_areas_value.get("dimensions"),
        list
    ):

        raise ValueError(
            "'improvement_areas.dimensions' must be a list."
        )

    if not isinstance(
        improvement_areas_value.get("questions"),
        list
    ):
        raise ValueError(
            "'improvement_areas.questions' must be a list."
        )

# ============================================================
# CAREER NORMALIZATION
# ============================================================

def normalize_career_scores(
    result: Dict[str, Any],
    career_lookup: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Normalize deterministic career scores.

    No ranking is recalculated.
    Existing deterministic rank is preserved.
    """

    values = result.get(
        "career_scores",
        []
    )

    if not isinstance(
        values,
        list
    ):
        return []

    output: List[Dict[str, Any]] = []

    for item in values:

        if not isinstance(
            item,
            dict
        ):
            continue

        career_id = get_career_id(
            item
        )

        if not career_id:
            continue

        career_name = get_career_name(
            item,
            career_lookup
        )

        score = safe_float(
            item.get(
                "score"
            ),
            0.0
        )

        max_score = safe_float(
            item.get(
                "max_score"
            ),
            0.0
        )

        percentage = safe_float(
            item.get(
                "percentage"
            ),
            percentage_from_score(
                score,
                max_score
            )
        )

        rank = safe_int(
            item.get(
                "rank"
            ),
            0
        )

        output.append({
            "career_id": career_id,
            "career_name": career_name,
            "score": score,
            "max_score": max_score,
            "percentage": round(
                percentage,
                2
            ),
            "rank": rank
        })

    return output


# ============================================================
# TIE DETECTION
# ============================================================

def detect_career_tie(
    career_scores: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Detect highest-score ties.

    Important:
        This does NOT change ranking.

    It only describes whether a tie exists.
    """

    if not career_scores:

        return {
            "is_tie": False,
            "complete_tie": False,
            "tied_career_ids": [],
            "tied_careers": []
        }

    percentages = [
        safe_float(
            item.get(
                "percentage"
            ),
            0.0
        )
        for item in career_scores
    ]

    highest = max(
        percentages
    )

    tied_items = [
        item
        for item in career_scores
        if abs(
            safe_float(
                item.get(
                    "percentage"
                ),
                0.0
            )
            - highest
        ) < 0.000001
    ]

    tied_ids = [
        normalize_text(
            item.get(
                "career_id"
            )
        )
        for item in tied_items
    ]

    tied_names = [
        clean_display_text(
            item.get(
                "career_name"
            )
        )
        for item in tied_items
    ]

    is_tie = len(
        tied_items
    ) > 1

    complete_tie = (
        len(tied_items)
        == len(career_scores)
    )

    return {
        "is_tie": is_tie,
        "complete_tie": complete_tie,
        "highest_percentage": highest,
        "tied_career_ids": tied_ids,
        "tied_careers": tied_names
    }


# ============================================================
# CURRENT DETERMINISTIC DIMENSIONS
# ============================================================

def normalize_primary_dimensions(
    result: Dict[str, Any],
    dimension_lookup: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Normalize the CURRENT deterministic dimensions list.

    Current scoring schema:

        [
            {
                "dimension": "...",
                "correct": 2,
                "total": 2,
                "percentage": 100,
                "level": "Strong"
            }
        ]

    No old `primary` object is expected here.
    """

    raw_dimensions = result.get(
        "dimensions",
        []
    )

    if not isinstance(
        raw_dimensions,
        list
    ):
        return []

    output: List[Dict[str, Any]] = []

    seen = set()

    for item in raw_dimensions:

        if not isinstance(
            item,
            dict
        ):
            continue

        name = clean_display_text(
            item.get(
                "dimension"
            )
        )

        if not name:
            continue

        correct = safe_int(
            item.get(
                "correct"
            ),
            0
        )

        total = safe_int(
            item.get(
                "total"
            ),
            0
        )

        percentage = safe_float(
            item.get(
                "percentage"
            ),
            percentage_from_score(
                correct,
                total
            )
        )

        level = clean_display_text(
            item.get(
                "level"
            )
        )

        dedupe_key = name.lower()

        if dedupe_key in seen:
            continue

        seen.add(
            dedupe_key
        )

        output.append({
            "dimension": name,
            "correct": correct,
            "total": total,
            "percentage": round(
                percentage,
                2
            ),
            "level": level
        })

    return output


# ============================================================
# THINKING PATTERN
# ============================================================

def normalize_thinking_pattern(
    result: Dict[str, Any],
    dimensions: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Generate a lightweight thinking-pattern interpretation
    from the deterministic dimension results.

    The scoring engine does NOT provide a separate
    `thinking_pattern` object, so this function does not
    expect one.

    It only interprets the existing dimensions.
    """

    if not dimensions:

        return {
            "label": "Insufficient evidence",
            "dimensions": []
        }

    strong = [
        item
        for item in dimensions
        if safe_float(
            item.get(
                "percentage"
            ),
            0.0
        ) >= 75
    ]

    moderate = [
        item
        for item in dimensions
        if 50
        <= safe_float(
            item.get(
                "percentage"
            ),
            0.0
        )
        < 75
    ]

    developing = [
        item
        for item in dimensions
        if safe_float(
            item.get(
                "percentage"
            ),
            0.0
        ) < 50
    ]

    if len(strong) >= 2:

        label = (
            "Strong and consistent "
            "problem-solving pattern"
        )

    elif strong:

        label = (
            "Developing but promising "
            "problem-solving pattern"
        )

    elif moderate:

        label = (
            "Balanced and developing "
            "problem-solving pattern"
        )

    else:

        label = (
            "Foundational problem-solving "
            "pattern"
        )

    return {
        "label": label,
        "dimensions": [
            {
                "dimension": item.get(
                    "dimension"
                ),
                "percentage": item.get(
                    "percentage"
                ),
                "level": item.get(
                    "level"
                )
            }
            for item in dimensions
        ],
        "strong_count": len(
            strong
        ),
        "moderate_count": len(
            moderate
        ),
        "developing_count": len(
            developing
        )
    }


# ============================================================
# SIGNAL NORMALIZATION
# ============================================================

def normalize_signal_list(
    values: Any,
    dimension_lookup: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Normalize strengths and improvement areas.

    Compatible with current dimension objects:

        {
            "dimension": "...",
            "correct": ...,
            "total": ...,
            "percentage": ...,
            "level": ...
        }

    Also accepts older fields safely.
    """

    if not isinstance(
        values,
        list
    ):
        return []

    output: List[Dict[str, Any]] = []

    seen = set()

    for value in values:

        if not isinstance(
            value,
            dict
        ):
            continue

        dimension_id = normalize_text(
            value.get(
                "dimension_id"
            )
            or value.get(
                "id"
            )
        )

        name = normalize_text(
            value.get(
                "dimension"
            )
            or value.get(
                "dimension_name"
            )
            or value.get(
                "name"
            )
        )

        if not name and dimension_id:

            name = dimension_name(
                dimension_id,
                dimension_lookup
            )

        name = clean_display_text(
            name
        )

        if not name:
            continue

        dedupe_key = (
            dimension_id.lower(),
            name.lower()
        )

        if dedupe_key in seen:
            continue

        seen.add(
            dedupe_key
        )

        normalized_item = {
            "type": normalize_text(
                value.get(
                    "type"
                )
            ),
            "dimension_id": dimension_id,
            "dimension": name
        }

        if "correct" in value:

            normalized_item["correct"] = safe_int(
                value.get(
                    "correct"
                ),
                0
            )

        if "total" in value:

            normalized_item["total"] = safe_int(
                value.get(
                    "total"
                ),
                0
            )

        if "percentage" in value:

            normalized_item["percentage"] = safe_float(
                value.get(
                    "percentage"
                ),
                0.0
            )

        if "level" in value:

            normalized_item["level"] = clean_display_text(
                value.get(
                    "level"
                )
            )

        if "score" in value:

            normalized_item["score"] = safe_float(
                value.get(
                    "score"
                ),
                0.0
            )

        if "max_score" in value:

            normalized_item["max_score"] = safe_float(
                value.get(
                    "max_score"
                ),
                0.0
            )

        if "evidence_count" in value:

            normalized_item["evidence_count"] = safe_int(
                value.get(
                    "evidence_count"
                ),
                0
            )

        output.append(
            normalized_item
        )

    return output


# ============================================================
# SAFE INTERPRETATION CONTEXT
# ============================================================

def build_ai_context(
    assessment: Dict[str, Any],
    result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build ONLY data required for local interpretation.

    NEVER includes:

        - question_results
        - selected answers
        - correct answers
        - answer keys
        - question text
    """

    career_lookup = build_career_lookup(
        assessment
    )

    dimension_lookup = build_dimension_lookup(
        assessment
    )

    career_scores = normalize_career_scores(
        result,
        career_lookup
    )

    tie_info = detect_career_tie(
        career_scores
    )

    top_career = result.get(
        "top_career",
        {}
    )

    second_career = result.get(
        "second_career",
        {}
    )

    top_career_name = get_career_name(
        top_career,
        career_lookup
    )

    second_career_name = get_career_name(
        second_career,
        career_lookup
    )

    primary_dimensions = normalize_primary_dimensions(
        result,
        dimension_lookup
    )

    thinking_pattern = normalize_thinking_pattern(
        result,
        primary_dimensions
    )

    strengths = normalize_signal_list(
        result.get(
            "strengths",
            []
        ),
        dimension_lookup
    )

    # improvement_areas = normalize_signal_list(
    #     result.get(
    #         "improvement_areas",
    #         []
    #     ),
    #     dimension_lookup
    # )
    improvement_areas_raw = result.get(
        "improvement_areas",
        {}
    )
    if isinstance(
        improvement_areas_raw,
        dict
    ):
        improvement_areas_source = improvement_areas_raw.get(
            "dimensions",
            []
        )
    else:

        improvement_areas_source = improvement_areas_raw

    improvement_areas = normalize_signal_list(
        improvement_areas_source,
        dimension_lookup
    )

    total_questions = safe_int(
        result.get(
            "total_questions",
            EXPECTED_EXPLORING_QUESTIONS
        ),
        EXPECTED_EXPLORING_QUESTIONS
    )

    answered_questions = safe_int(
        result.get(
            "answered_questions",
            total_questions
        ),
        total_questions
    )

    total_correct = safe_int(
        result.get(
            "total_correct",
            0
        ),
        0
    )

    def safe_career_summary(
        career: Any,
        name: str
    ) -> Dict[str, Any]:

        if not isinstance(
            career,
            dict
        ):
            career = {}

        return {
            "career_id": get_career_id(
                career
            ),
            "career_name": name,
            "score": safe_float(
                career.get(
                    "score"
                ),
                0.0
            ),
            "max_score": safe_float(
                career.get(
                    "max_score"
                ),
                0.0
            ),
            "percentage": safe_float(
                career.get(
                    "percentage"
                ),
                0.0
            )
        }

    return {
        "assessment_id": normalize_text(
            result.get(
                "assessment_id"
            )
        ),

        "assessment_version": normalize_text(
            result.get(
                "assessment_version"
            )
        ),

        "journey": JOURNEY_NUMBER,

        "mode": JOURNEY_MODE,

        "total_questions": total_questions,

        "answered_questions": answered_questions,

        "total_correct": total_correct,

        "career_scores": career_scores,

        "career_tie": tie_info,

        "top_career": safe_career_summary(
            top_career,
            top_career_name
        ),

        "second_career": safe_career_summary(
            second_career,
            second_career_name
        ),

        "thinking_pattern": thinking_pattern,

        "primary_dimensions": primary_dimensions,

        "strengths": strengths,

        "improvement_areas": improvement_areas
    }


# ============================================================
# LOCAL INTERPRETATION HELPERS
# ============================================================

def percentage_level(
    percentage: Any
) -> str:
    """
    Convert percentage into a neutral interpretation level.
    """

    value = safe_float(
        percentage,
        0.0
    )

    if value >= 90:
        return "very strong"

    if value >= 75:
        return "strong"

    if value >= 50:
        return "moderate"

    return "developing"


# ============================================================
# OVERALL INSIGHT
# ============================================================

def build_overall_insight(
    context: Dict[str, Any]
) -> str:
    """
    Generate overall interpretation locally.
    """

    tie_info = context.get(
        "career_tie",
        {}
    )

    career_scores = context.get(
        "career_scores",
        []
    )

    total_correct = safe_int(
        context.get(
            "total_correct"
        ),
        0
    )

    total_questions = safe_int(
        context.get(
            "total_questions"
        ),
        EXPECTED_EXPLORING_QUESTIONS
    )

    if not career_scores:

        return (
            "The assessment results do not contain enough "
            "career information to provide an overall "
            "interpretation."
        )

    if tie_info.get(
        "complete_tie"
    ):

        return (
            f"You answered {total_correct} of "
            f"{total_questions} questions correctly. "
            "Your career results are completely tied, "
            "so the assessment does not identify one "
            "career as uniquely stronger than the others. "
            "Use the recommended areas as equally promising "
            "directions and continue exploring them."
        )

    # --------------------------------------------------------
    # IMPORTANT FIX:
    # career_scores here preserves the ORIGINAL input order
    # (not sorted by rank/percentage), so career_scores[0] is
    # NOT guaranteed to be the actual top-scoring career. Use
    # context["top_career"], which is taken directly from the
    # deterministic scoring engine's own top_career field (the
    # same source build_top_career_explanation already uses
    # correctly), instead of guessing from list position.
    # --------------------------------------------------------

    top = context.get(
        "top_career",
        {}
    ) or (
        career_scores[0]
        if career_scores
        else {}
    )

    top_name = clean_display_text(
        top.get(
            "career_name"
        )
    )

    top_percentage = format_percentage(
        top.get(
            "percentage"
        )
    )

    if tie_info.get(
        "is_tie"
    ):

        tied_names = ", ".join(
            tie_info.get(
                "tied_careers",
                []
            )
        )

        return (
            f"You answered {total_correct} of "
            f"{total_questions} questions correctly. "
            f"The highest result is shared by "
            f"{tied_names} at {top_percentage}. "
            "This means the assessment identifies "
            "multiple promising career directions rather "
            "than one uniquely dominant option."
        )

    return (
        f"You answered {total_correct} of "
        f"{total_questions} questions correctly. "
        f"Your strongest deterministic career result is "
        f"{top_name} at {top_percentage}. "
        "Your dimension results also highlight the areas "
        "where your current strengths and development "
        "opportunities are most visible."
    )


# ============================================================
# THINKING PATTERN INSIGHT
# ============================================================

def build_thinking_pattern_insight(
    context: Dict[str, Any]
) -> str:
    """
    Explain the deterministic dimension pattern.
    """

    dimensions = context.get(
        "primary_dimensions",
        []
    )

    if not dimensions:

        return (
            "There is not enough dimension-level information "
            "to identify a clear thinking pattern."
        )

    strong = [
        item
        for item in dimensions
        if safe_float(
            item.get(
                "percentage"
            ),
            0.0
        ) >= 75
    ]

    developing = [
        item
        for item in dimensions
        if safe_float(
            item.get(
                "percentage"
            ),
            0.0
        ) < 50
    ]

    if strong:

        names = [
            clean_display_text(
                item.get(
                    "dimension"
                )
            )
            for item in strong[:2]
        ]

        names = [
            name
            for name in names
            if name
        ]

        if names:

            joined = " and ".join(
                names
            )

            if developing:

                return (
                    f"Your results show stronger performance "
                    f"in {joined}, while some other areas are "
                    "still developing. This suggests a "
                    "problem-solving profile with clear "
                    "strength areas alongside opportunities "
                    "for further growth."
                )

            return (
                f"Your results show particularly strong "
                f"performance in {joined}. This suggests a "
                "consistent problem-solving profile that may "
                "support several analytical or technical "
                "career directions."
            )

    if developing:

        names = [
            clean_display_text(
                item.get(
                    "dimension"
                )
            )
            for item in developing[:2]
        ]

        names = [
            name
            for name in names
            if name
        ]

        if names:

            return (
                "Your current results suggest a developing "
                "problem-solving profile, particularly around "
                + " and ".join(names)
                + ". These areas can improve with targeted "
                  "practice and real-world projects."
            )

    return (
        "Your dimension results are relatively balanced, "
        "suggesting that no single problem-solving area "
        "dominates the current profile."
    )


# ============================================================
# TOP CAREER EXPLANATION
# ============================================================

def build_top_career_explanation(
    context: Dict[str, Any]
) -> str:
    """
    Explain why the deterministic top career appears first.

    Does not calculate or change the ranking.
    """

    tie_info = context.get(
        "career_tie",
        {}
    )

    top = context.get(
        "top_career",
        {}
    )

    top_name = clean_display_text(
        top.get(
            "career_name"
        )
    )

    top_percentage = format_percentage(
        top.get(
            "percentage"
        )
    )

    if not top_name:

        return (
            "No unique top career was provided by the "
            "deterministic scoring engine."
        )

    if tie_info.get(
        "complete_tie"
    ):

        return (
            f"{top_name} is one of the equally scored career "
            "areas. Because all careers have the same highest "
            "result, this assessment should not be interpreted "
            "as selecting this career over the others."
        )

    if tie_info.get(
        "is_tie"
    ):

        tied_names = ", ".join(
            tie_info.get(
                "tied_careers",
                []
            )
        )

        return (
            f"{top_name} is among the highest-scoring career "
            f"areas at {top_percentage}. The highest result is "
            f"shared with {tied_names}, so both directions "
            "should be considered promising."
        )

    return (
        f"{top_name} achieved the highest deterministic career "
        f"result at {top_percentage}. This means your current "
        "assessment profile aligns most strongly with this "
        "career area among the available options."
    )


# ============================================================
# SECOND CAREER EXPLANATION
# ============================================================

def build_second_career_explanation(
    context: Dict[str, Any]
) -> str:
    """
    Explain the second deterministic career result.
    """

    tie_info = context.get(
        "career_tie",
        {}
    )

    second = context.get(
        "second_career",
        {}
    )

    second_name = clean_display_text(
        second.get(
            "career_name"
        )
    )

    second_percentage = format_percentage(
        second.get(
            "percentage"
        )
    )

    if not second_name:

        return (
            "A second career result was not available."
        )

    if tie_info.get(
        "complete_tie"
    ):

        return (
            f"{second_name} is also equally scored with the "
            "other career areas. Treat it as an equally valid "
            "direction rather than a lower-ranked alternative."
        )

    if tie_info.get(
        "is_tie"
    ):

        return (
            f"{second_name} is also part of the highest-scoring "
            "career group at {second_percentage}. This indicates "
            "that your current profile can support more than one "
            "career direction."
        )

    return (
        f"{second_name} is your next strongest deterministic "
        f"career result at {second_percentage}. It represents "
        "a useful alternative direction if you want to explore "
        "a career path different from your top result."
    )


# ============================================================
# STRENGTH EXPLANATIONS
# ============================================================

def build_strength_explanation(
    item: Dict[str, Any]
) -> str:
    """
    Generate deterministic explanation for a strength.
    """

    dimension = clean_display_text(
        item.get(
            "dimension"
        )
    )

    percentage = safe_float(
        item.get(
            "percentage"
        ),
        0.0
    )

    level = clean_display_text(
        item.get(
            "level"
        )
    )

    if not level:

        level = percentage_level(
            percentage
        )

    if percentage >= 90:

        return (
            f"{dimension} is a very strong area, with "
            f"{format_percentage(percentage)} performance. "
            "This is a clear positive signal in your current "
            "assessment profile."
        )

    if percentage >= 75:

        return (
            f"{dimension} is a strong area, with "
            f"{format_percentage(percentage)} performance. "
            "This suggests good current capability that can "
            "be strengthened further through practical work."
        )

    return (
        f"{dimension} currently shows {level} performance at "
        f"{format_percentage(percentage)}. It is one of the "
        "more positive signals in your current results."
    )


# ============================================================
# IMPROVEMENT EXPLANATIONS
# ============================================================

def build_improvement_explanation(
    item: Dict[str, Any]
) -> str:
    """
    Generate deterministic explanation for an improvement area.
    """

    dimension = clean_display_text(
        item.get(
            "dimension"
        )
    )

    percentage = safe_float(
        item.get(
            "percentage"
        ),
        0.0
    )

    if percentage < 50:

        return (
            f"{dimension} is currently developing at "
            f"{format_percentage(percentage)}. "
            "Focused practice, guided exercises, and practical "
            "projects can help strengthen this area."
        )

    return (
        f"{dimension} is currently at "
        f"{format_percentage(percentage)}. "
        "This is an area where additional practice can help "
        "turn a developing capability into a stronger skill."
    )


# ============================================================
# RECOMMENDED DOMAINS
# ============================================================

def build_recommended_domains(
    context: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Build career recommendations strictly from deterministic
    career scores.

    No new career is invented here.
    """

    career_scores = context.get(
        "career_scores",
        []
    )

    tie_info = context.get(
        "career_tie",
        {}
    )

    if not career_scores:
        return []

    if tie_info.get(
        "complete_tie"
    ):

        selected = career_scores

    elif tie_info.get(
        "is_tie"
    ):

        tied_ids = {
            normalize_text(
                value
            )
            for value in tie_info.get(
                "tied_career_ids",
                []
            )
        }

        selected = [
            item
            for item in career_scores
            if normalize_text(
                item.get(
                    "career_id"
                )
            ) in tied_ids
        ]

    else:

        selected = career_scores[:2]

    output: List[Dict[str, Any]] = []

    for item in selected:

        career_name = clean_display_text(
            item.get(
                "career_name"
            )
        )

        percentage = format_percentage(
            item.get(
                "percentage"
            )
        )

        if not career_name:
            continue

        if tie_info.get(
            "complete_tie"
        ):

            reason = (
                f"{career_name} is equally scored with the "
                f"other career areas at {percentage}. "
                "It should be explored as one of several "
                "equally promising directions."
            )

        elif tie_info.get(
            "is_tie"
        ):

            reason = (
                f"{career_name} shares the highest deterministic "
                f"result at {percentage}. It is therefore one "
                "of the strongest career directions identified "
                "by the assessment."
            )

        else:

            reason = (
                f"{career_name} is among your strongest "
                f"deterministic career results at {percentage}. "
                "It is a useful direction to explore further."
            )

        output.append({
            "career": career_name,
            "reason": reason
        })

    return output


# ============================================================
# PERSONALIZED FEEDBACK
# ============================================================

def build_personalized_feedback(
    context: Dict[str, Any]
) -> str:
    """
    Generate practical but deterministic feedback.
    """

    improvements = context.get(
        "improvement_areas",
        []
    )

    strengths = context.get(
        "strengths",
        []
    )

    tie_info = context.get(
        "career_tie",
        {}
    )

    if tie_info.get(
        "complete_tie"
    ):

        return (
            "Your results do not identify one uniquely dominant "
            "career, so avoid narrowing your options too early. "
            "Compare the equally scored career areas through "
            "small practical projects, courses, or real-world "
            "tasks before making a final decision."
        )

    if strengths and improvements:

        strength_name = clean_display_text(
            strengths[0].get(
                "dimension"
            )
        )

        improvement_name = clean_display_text(
            improvements[0].get(
                "dimension"
            )
        )

        return (
            f"Build on your strength in {strength_name} while "
            f"actively developing {improvement_name}. A good "
            "next step is to choose a small practical project "
            "that uses your stronger ability while deliberately "
            "practicing the weaker area."
        )

    if strengths:

        strength_name = clean_display_text(
            strengths[0].get(
                "dimension"
            )
        )

        return (
            f"Continue building on your strength in "
            f"{strength_name}. The best way to validate your "
            "career direction is through practical projects "
            "that allow you to apply this strength."
        )

    if improvements:

        improvement_name = clean_display_text(
            improvements[0].get(
                "dimension"
            )
        )

        return (
            f"Focus first on developing {improvement_name}. "
            "Consistent practice and small real-world projects "
            "will give you stronger evidence of your readiness."
        )

    return (
        "Use your assessment result as a starting point rather "
        "than a final decision. Practical projects are the best "
        "way to validate your interests and current abilities."
    )


# ============================================================
# NEXT STEP
# ============================================================

def build_next_step(
    context: Dict[str, Any]
) -> str:
    """
    Generate the next practical action.
    """

    tie_info = context.get(
        "career_tie",
        {}
    )

    recommended = build_recommended_domains(
        context
    )

    if tie_info.get(
        "complete_tie"
    ):

        return (
            "Explore the equally scored career areas through "
            "one small practical project in each area, then "
            "compare which type of work feels most suitable."
        )

    if tie_info.get(
        "is_tie"
    ):

        names = [
            clean_display_text(
                item.get(
                    "career"
                )
            )
            for item in recommended
        ]

        names = [
            name
            for name in names
            if name
        ]

        if names:

            return (
                "Compare the strongest career directions — "
                + ", ".join(names)
                + " — through practical projects or beginner "
                  "courses before choosing one to pursue more deeply."
            )

    top = context.get(
        "top_career",
        {}
    )

    top_name = clean_display_text(
        top.get(
            "career_name"
        )
    )

    if top_name:

        return (
            f"Start validating {top_name} through a practical "
            "beginner project and a focused learning path. "
            "Use the experience to determine whether you want "
            "to continue toward this career."
        )

    return (
        "Choose one of the strongest career areas and test it "
        "through a small practical project."
    )


# ============================================================
# LOCAL INTERPRETATION GENERATOR
# ============================================================

def generate_local_interpretation(
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate the complete local interpretation.
    """

    dimensions = context.get(
        "primary_dimensions",
        []
    )

    normalized_strengths = context.get(
        "strengths",
        []
    )

    normalized_improvements = context.get(
        "improvement_areas",
        []
    )

    # --------------------------------------------------------
    # If scoring engine returned empty signal lists, derive
    # them from the current dimension list for interpretation.
    #
    # This does NOT modify exploring_result.json.
    # --------------------------------------------------------

    if not normalized_strengths:

        normalized_strengths = [
            item
            for item in dimensions
            if safe_float(
                item.get(
                    "percentage"
                ),
                0.0
            ) >= 75
        ]

    if not normalized_improvements:

        normalized_improvements = [
            item
            for item in dimensions
            if safe_float(
                item.get(
                    "percentage"
                ),
                0.0
            ) < 50
        ]

    strength_output: List[Dict[str, Any]] = []

    for item in normalized_strengths:

        name = clean_display_text(
            item.get(
                "dimension"
            )
        )

        if not name:
            continue

        strength_output.append({
            "dimension": name,
            "explanation": build_strength_explanation(
                item
            )
        })

    improvement_output: List[Dict[str, Any]] = []

    for item in normalized_improvements:

        name = clean_display_text(
            item.get(
                "dimension"
            )
        )

        if not name:
            continue

        improvement_output.append({
            "dimension": name,
            "explanation": build_improvement_explanation(
                item
            )
        })

    return {
        "ai_insights": {
            "overall": build_overall_insight(
                context
            ),

            "thinking_pattern": build_thinking_pattern_insight(
                context
            ),

            "top_career_explanation": (
                build_top_career_explanation(
                    context
                )
            ),

            "second_career_explanation": (
                build_second_career_explanation(
                    context
                )
            )
        },

        "strengths": strength_output,

        "improvement_areas": improvement_output,

        "personalized_feedback": (
            build_personalized_feedback(
                context
            )
        ),

        "recommended_domains": (
            build_recommended_domains(
                context
            )
        ),

        "next_step": build_next_step(
            context
        )
    }


# ============================================================
# AI OUTPUT VALIDATION
# ============================================================

def validate_ai_output(
    output: Dict[str, Any]
) -> None:
    """
    Validate local interpretation output.
    """

    required = [
        "ai_insights",
        "strengths",
        "improvement_areas",
        "personalized_feedback",
        "recommended_domains",
        "next_step"
    ]

    missing = [
        key
        for key in required
        if key not in output
    ]

    if missing:

        raise ValueError(
            "Local interpretation output is missing "
            "required fields: "
            + ", ".join(missing)
        )

    if not isinstance(
        output["ai_insights"],
        dict
    ):

        raise ValueError(
            "'ai_insights' must be an object."
        )

    required_insights = [
        "overall",
        "thinking_pattern",
        "top_career_explanation",
        "second_career_explanation"
    ]

    missing_insights = [
        key
        for key in required_insights
        if key not in output["ai_insights"]
    ]

    if missing_insights:

        raise ValueError(
            "Local interpretation 'ai_insights' "
            "is missing fields: "
            + ", ".join(
                missing_insights
            )
        )

    for field in required_insights:

        if not isinstance(
            output["ai_insights"][field],
            str
        ):

            raise ValueError(
                f"'ai_insights.{field}' must be a string."
            )

    if not isinstance(
        output["strengths"],
        list
    ):

        raise ValueError(
            "'strengths' must be a list."
        )

    if not isinstance(
        output["improvement_areas"],
        list
    ):

        raise ValueError(
            "'improvement_areas' must be a list."
        )

    if not isinstance(
        output["recommended_domains"],
        list
    ):

        raise ValueError(
            "'recommended_domains' must be a list."
        )

    if not isinstance(
        output["personalized_feedback"],
        str
    ):

        raise ValueError(
            "'personalized_feedback' must be a string."
        )

    if not isinstance(
        output["next_step"],
        str
    ):

        raise ValueError(
            "'next_step' must be a string."
        )

    # --------------------------------------------------------
    # Strength validation
    # --------------------------------------------------------

    for item in output["strengths"]:

        if not isinstance(
            item,
            dict
        ):

            raise ValueError(
                "Every strength must be an object."
            )

        if "dimension" not in item:

            raise ValueError(
                "Strength item missing 'dimension'."
            )

        if "explanation" not in item:

            raise ValueError(
                "Strength item missing 'explanation'."
            )

        if not isinstance(
            item["dimension"],
            str
        ):

            raise ValueError(
                "Strength 'dimension' must be a string."
            )

        if not isinstance(
            item["explanation"],
            str
        ):

            raise ValueError(
                "Strength 'explanation' must be a string."
            )

    # --------------------------------------------------------
    # Improvement validation
    # --------------------------------------------------------

    for item in output["improvement_areas"]:

        if not isinstance(
            item,
            dict
        ):

            raise ValueError(
                "Every improvement area must be an object."
            )

        if "dimension" not in item:

            raise ValueError(
                "Improvement item missing 'dimension'."
            )

        if "explanation" not in item:

            raise ValueError(
                "Improvement item missing 'explanation'."
            )

        if not isinstance(
            item["dimension"],
            str
        ):

            raise ValueError(
                "Improvement 'dimension' must be a string."
            )

        if not isinstance(
            item["explanation"],
            str
        ):

            raise ValueError(
                "Improvement 'explanation' must be a string."
            )

    # --------------------------------------------------------
    # Recommended domain validation
    # --------------------------------------------------------

    for item in output["recommended_domains"]:

        if not isinstance(
            item,
            dict
        ):

            raise ValueError(
                "Every recommended domain must be an object."
            )

        if "career" not in item:

            raise ValueError(
                "Recommended domain missing 'career'."
            )

        if "reason" not in item:

            raise ValueError(
                "Recommended domain missing 'reason'."
            )

        if not isinstance(
            item["career"],
            str
        ):

            raise ValueError(
                "Recommended domain 'career' "
                "must be a string."
            )

        if not isinstance(
            item["reason"],
            str
        ):

            raise ValueError(
                "Recommended domain 'reason' "
                "must be a string."
            )


# ============================================================
# DETERMINISTIC SAFETY CHECKS
# ============================================================

def enforce_ai_output_constraints(
    output: Dict[str, Any],
    context: Dict[str, Any]
) -> None:
    """
    Ensure local interpretation cannot contradict
    deterministic career results.
    """

    career_scores = context.get(
        "career_scores",
        []
    )

    allowed_career_ids = {
        normalize_text(
            item.get(
                "career_id"
            )
        )
        for item in career_scores
        if isinstance(
            item,
            dict
        )
    }

    allowed_career_names = {
        clean_display_text(
            item.get(
                "career_name"
            )
        ).lower()
        for item in career_scores
        if isinstance(
            item,
            dict
        )
    }

    recommended_domains = output.get(
        "recommended_domains",
        []
    )

    # --------------------------------------------------------
    # Career recommendation safety
    # --------------------------------------------------------

    for item in recommended_domains:

        career = clean_display_text(
            item.get(
                "career"
            )
        )

        if career.lower() not in allowed_career_names:

            raise ValueError(
                "Local interpretation recommended a career "
                "that is not present in deterministic career "
                f"scores: {career}"
            )

    # --------------------------------------------------------
    # Complete tie safety
    # --------------------------------------------------------

    tie_info = context.get(
        "career_tie",
        {}
    )

    if tie_info.get(
        "complete_tie"
    ):

        tied_ids = {
            normalize_text(
                value
            )
            for value in tie_info.get(
                "tied_career_ids",
                []
            )
        }

        if tied_ids != allowed_career_ids:

            raise ValueError(
                "Complete tie information does not match "
                "deterministic career scores."
            )

        if len(
            recommended_domains
        ) != len(
            allowed_career_ids
        ):

            raise ValueError(
                "Complete tie must recommend all equally "
                "scored career areas."
            )

    # --------------------------------------------------------
    # Partial tie safety
    # --------------------------------------------------------

    if (
        tie_info.get(
            "is_tie"
        )
        and not tie_info.get(
            "complete_tie"
        )
    ):

        tied_ids = {
            normalize_text(
                value
            )
            for value in tie_info.get(
                "tied_career_ids",
                []
            )
        }

        if len(
            tied_ids
        ) <= 1:

            raise ValueError(
                "Invalid partial tie information."
            )

        recommended_names = {
            clean_display_text(
                item.get(
                    "career"
                )
            ).lower()
            for item in recommended_domains
        }

        expected_names = {
            clean_display_text(
                item.get(
                    "career_name"
                )
            ).lower()
            for item in career_scores
            if normalize_text(
                item.get(
                    "career_id"
                )
            ) in tied_ids
        }

        if recommended_names != expected_names:

            raise ValueError(
                "Partial tie recommendations do not exactly "
                "match the deterministic tied careers."
            )

    # --------------------------------------------------------
    # Basic recommendation safety
    # --------------------------------------------------------

    seen_names = set()

    for item in recommended_domains:

        career_name = clean_display_text(
            item.get(
                "career"
            )
        )

        key = career_name.lower()

        if key in seen_names:

            raise ValueError(
                "Duplicate career found in "
                f"recommended_domains: {career_name}"
            )

        seen_names.add(
            key
        )

    # --------------------------------------------------------
    # Career count safety
    # --------------------------------------------------------

    if len(
        allowed_career_ids
    ) != EXPECTED_CAREER_COUNT:

        raise ValueError(
            "Deterministic career count changed unexpectedly."
        )


# ============================================================
# FINAL RESULT BUILD
# ============================================================

def build_final_ai_result(
    assessment: Dict[str, Any],
    deterministic_result: Dict[str, Any],
    ai_output: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Combine deterministic source data with local interpretation.

    The deterministic result is preserved as-is.
    """

    career_lookup = build_career_lookup(
        assessment
    )

    normalized_scores = normalize_career_scores(
        deterministic_result,
        career_lookup
    )

    tie_info = detect_career_tie(
        normalized_scores
    )

    return {
        "assessment": {
            "assessment_id": normalize_text(
                assessment.get(
                    "assessment_id"
                )
            ),

            "title": normalize_text(
                assessment.get(
                    "title"
                )
            ),

            "version": normalize_text(
                assessment.get(
                    "version"
                )
            ),

            "journey": JOURNEY_NUMBER,

            "mode": JOURNEY_MODE
        },

        "source": {
            "deterministic_engine": (
                "exploring_scoring.py"
            ),

            "deterministic_result": (
                "exploring_result.json"
            ),

            "interpretation_engine": (
                ENGINE_NAME
            ),

            "interpretation_engine_version": (
                ENGINE_VERSION
            ),

            "engine_type": ENGINE_TYPE,

            "external_api": False,

            "openai_used": False,

            "internet_required": False,

            "source_of_truth": (
                "deterministic_scoring_engine"
            )
        },

        "deterministic_summary": {

            "assessment_id": deterministic_result.get(
                "assessment_id"
            ),

            "assessment_version": deterministic_result.get(
                "assessment_version"
            ),

            "total_questions": deterministic_result.get(
                "total_questions"
            ),

            "answered_questions": deterministic_result.get(
                "answered_questions"
            ),

            "total_correct": deterministic_result.get(
                "total_correct"
            ),

            "career_scores": deterministic_result.get(
                "career_scores",
                []
            ),

            "top_career": deterministic_result.get(
                "top_career",
                {}
            ),

            "second_career": deterministic_result.get(
                "second_career",
                {}
            ),

            # IMPORTANT:
            # Current scoring schema is LIST.
            "dimensions": deterministic_result.get(
                "dimensions",
                []
            ),

            "strengths": deterministic_result.get(
                "strengths",
                []
            ),

            "improvement_areas": deterministic_result.get(
                "improvement_areas",
                []
            ),

            "career_tie": tie_info
        },

        "ai_evaluation": ai_output
    }


# ============================================================
# DISPLAY HELPERS
# ============================================================

def print_header(
    title: str
) -> None:

    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def print_ai_result(
    result: Dict[str, Any]
) -> None:

    ai = result.get(
        "ai_evaluation",
        {}
    )

    insights = ai.get(
        "ai_insights",
        {}
    )

    print_header(
        "MINERVA — JOURNEY 1: LOCAL AI EVALUATION"
    )

    # --------------------------------------------------------
    # OVERALL
    # --------------------------------------------------------

    print()
    print(
        "OVERALL AI INSIGHT"
    )
    print("-" * 70)

    print(
        clean_display_text(
            insights.get(
                "overall",
                "N/A"
            )
        )
    )

    # --------------------------------------------------------
    # THINKING PATTERN
    # --------------------------------------------------------

    print()
    print(
        "THINKING PATTERN"
    )
    print("-" * 70)

    print(
        clean_display_text(
            insights.get(
                "thinking_pattern",
                "N/A"
            )
        )
    )

    # --------------------------------------------------------
    # TOP CAREER
    # --------------------------------------------------------

    print()
    print(
        "TOP CAREER EXPLANATION"
    )
    print("-" * 70)

    print(
        clean_display_text(
            insights.get(
                "top_career_explanation",
                "N/A"
            )
        )
    )

    # --------------------------------------------------------
    # SECOND CAREER
    # --------------------------------------------------------

    print()
    print(
        "SECOND CAREER EXPLANATION"
    )
    print("-" * 70)

    print(
        clean_display_text(
            insights.get(
                "second_career_explanation",
                "N/A"
            )
        )
    )

    # --------------------------------------------------------
    # STRENGTHS
    # --------------------------------------------------------

    print()
    print(
        "STRENGTHS"
    )
    print("-" * 70)

    strengths = ai.get(
        "strengths",
        []
    )

    if strengths:

        for item in strengths:

            dimension = clean_display_text(
                item.get(
                    "dimension",
                    "Unknown"
                )
            )

            explanation = clean_display_text(
                item.get(
                    "explanation",
                    ""
                )
            )

            print(
                f"+ {dimension}: {explanation}"
            )

    else:

        print(
            "No strengths returned."
        )

    # --------------------------------------------------------
    # IMPROVEMENT AREAS
    # --------------------------------------------------------

    print()
    print(
        "IMPROVEMENT AREAS"
    )
    print("-" * 70)

    improvements = ai.get(
        "improvement_areas",
        []
    )

    if improvements:

        for item in improvements:

            dimension = clean_display_text(
                item.get(
                    "dimension",
                    "Unknown"
                )
            )

            explanation = clean_display_text(
                item.get(
                    "explanation",
                    ""
                )
            )

            print(
                f"- {dimension}: {explanation}"
            )

    else:

        print(
            "No major improvement areas identified."
        )

    # --------------------------------------------------------
    # PERSONALIZED FEEDBACK
    # --------------------------------------------------------

    print()
    print(
        "PERSONALIZED FEEDBACK"
    )
    print("-" * 70)

    print(
        clean_display_text(
            ai.get(
                "personalized_feedback",
                "N/A"
            )
        )
    )

    # --------------------------------------------------------
    # RECOMMENDED DOMAINS
    # --------------------------------------------------------

    print()
    print(
        "RECOMMENDED DOMAINS"
    )
    print("-" * 70)

    domains = ai.get(
        "recommended_domains",
        []
    )

    if domains:

        for domain in domains:

            career = clean_display_text(
                domain.get(
                    "career",
                    "Unknown"
                )
            )

            reason = clean_display_text(
                domain.get(
                    "reason",
                    ""
                )
            )

            print(
                f"+ {career}: {reason}"
            )

    else:

        print(
            "No recommended domains returned."
        )

    # --------------------------------------------------------
    # NEXT STEP
    # --------------------------------------------------------

    print()
    print(
        "NEXT STEP"
    )
    print("-" * 70)

    print(
        clean_display_text(
            ai.get(
                "next_step",
                "N/A"
            )
        )
    )


# ============================================================
# MAIN ENGINE
# ============================================================

def run() -> Dict[str, Any]:

    print_header(
        "MINERVA JOURNEY 1 — "
        "EXPLORING LOCAL INTERPRETATION ENGINE"
    )

    # ========================================================
    # LOAD ASSESSMENT
    # ========================================================

    print()
    print(
        "Loading Minerva Assessment..."
    )

    assessment = load_json(
        ASSESSMENT_FILE
    )

    print(
        "Assessment loaded successfully."
    )

    print(
        f"Assessment ID: "
        f"{assessment.get('assessment_id')}"
    )

    print(
        f"Version: "
        f"{assessment.get('version')}"
    )

    # ========================================================
    # VALIDATE ASSESSMENT
    # ========================================================

    print()
    print(
        "Validating assessment structure..."
    )

    validate_assessment(
        assessment
    )

    print(
        "Assessment structure validated."
    )

    # ========================================================
    # LOAD DETERMINISTIC RESULT
    # ========================================================

    print()
    print(
        "Loading deterministic evaluation..."
    )

    deterministic_result = load_json(
        SCORING_RESULT_FILE
    )

    print(
        "Deterministic result loaded successfully."
    )

    # ========================================================
    # VALIDATE DETERMINISTIC RESULT
    # ========================================================

    print()
    print(
        "Validating deterministic result..."
    )

    validate_scoring_result(
        deterministic_result,
        assessment
    )

    print(
        "Deterministic result validated."
    )

    # ========================================================
    # BUILD SAFE CONTEXT
    # ========================================================

    print()
    print(
        "Preparing safe local interpretation context..."
    )

    ai_context = build_ai_context(
        assessment,
        deterministic_result
    )

    print(
        "Interpretation context prepared."
    )

    print()
    print(
        "Question results excluded from interpretation."
    )

    print(
        "Answer keys excluded from interpretation."
    )

    print(
        "Selected answers excluded from interpretation."
    )

    print(
        "Question text excluded from interpretation."
    )

    print(
        "Deterministic scores remain the source of truth."
    )

    # ========================================================
    # SHOW CAREER RESULTS
    # ========================================================

    print()
    print(
        "Deterministic career results:"
    )

    for item in ai_context.get(
        "career_scores",
        []
    ):

        career = clean_display_text(
            item.get(
                "career_name"
            )
        )

        percentage = format_percentage(
            item.get(
                "percentage"
            )
        )

        rank = item.get(
            "rank"
        )

        print(
            f"  Rank {rank}: "
            f"{career} — {percentage}"
        )

    # ========================================================
    # SHOW DIMENSION RESULTS
    # ========================================================

    print()
    print(
        "Deterministic dimension results:"
    )

    for item in ai_context.get(
        "primary_dimensions",
        []
    ):

        dimension = clean_display_text(
            item.get(
                "dimension"
            )
        )

        percentage = format_percentage(
            item.get(
                "percentage"
            )
        )

        level = clean_display_text(
            item.get(
                "level"
            )
        )

        print(
            f"  {dimension}: "
            f"{percentage} "
            f"({level})"
        )

    # ========================================================
    # SHOW TIE STATUS
    # ========================================================

    tie_info = ai_context.get(
        "career_tie",
        {}
    )

    print()
    print(
        "Career tie analysis:"
    )

    if tie_info.get(
        "complete_tie"
    ):

        print(
            "  COMPLETE TIE detected."
        )

        print(
            "  All five careers have the same highest score."
        )

        print(
            "  No career will be treated as uniquely strongest."
        )

    elif tie_info.get(
        "is_tie"
    ):

        tied = ", ".join(
            tie_info.get(
                "tied_careers",
                []
            )
        )

        print(
            f"  Partial tie detected among: {tied}"
        )

    else:

        print(
            "  No highest-score tie detected."
        )

    # ========================================================
    # LOCAL ENGINE
    # ========================================================

    print()
    print(
        "Interpretation Engine: LOCAL RULE-BASED"
    )

    print(
        f"Engine Version: {ENGINE_VERSION}"
    )

    print(
        "External API: DISABLED"
    )

    print(
        "OpenAI: NOT USED"
    )

    print(
        "Internet connection: NOT REQUIRED"
    )

    # ========================================================
    # GENERATE INTERPRETATION
    # ========================================================

    print()
    print(
        "Generating local interpretation..."
    )

    ai_output = generate_local_interpretation(
        ai_context
    )

    print(
        "Local interpretation generated successfully."
    )

    # ========================================================
    # VALIDATE OUTPUT
    # ========================================================

    print()
    print(
        "Validating interpretation output..."
    )

    validate_ai_output(
        ai_output
    )

    print(
        "Interpretation output structure validated."
    )

    # ========================================================
    # SAFETY CHECKS
    # ========================================================

    print()
    print(
        "Checking interpretation against deterministic "
        "constraints..."
    )

    enforce_ai_output_constraints(
        ai_output,
        ai_context
    )

    print(
        "Interpretation passed deterministic safety checks."
    )

    # ========================================================
    # BUILD FINAL RESULT
    # ========================================================

    print()
    print(
        "Building final interpretation result..."
    )

    final_result = build_final_ai_result(
        assessment,
        deterministic_result,
        ai_output
    )

    # ========================================================
    # SAVE
    # ========================================================

    save_json(
        AI_RESULT_FILE,
        final_result
    )

    print(
        "Interpretation result saved successfully."
    )

    # ========================================================
    # DISPLAY
    # ========================================================

    print_ai_result(
        final_result
    )

    # ========================================================
    # COMPLETE
    # ========================================================

    print()
    print("=" * 70)

    print(
        "LOCAL AI EVALUATION COMPLETE"
    )

    print("=" * 70)

    print()

    print(
        f"Result saved to: "
        f"{AI_RESULT_FILE.name}"
    )

    return final_result


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        run()

    except KeyboardInterrupt:

        print()

        print(
            "Local evaluation cancelled by user."
        )

        sys.exit(1)

    except Exception as exc:

        print()

        print("=" * 70)

        print(
            "MINERVA JOURNEY 1 LOCAL EVALUATION ERROR"
        )

        print("=" * 70)

        print()

        print(
            f"{type(exc).__name__}: {exc}"
        )

        sys.exit(1)