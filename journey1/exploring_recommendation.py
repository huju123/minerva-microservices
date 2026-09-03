"""
============================================================
MINERVA — JOURNEY 1: EXPLORING
Career Recommendation Engine — FINAL v5.0
============================================================

Purpose:
    Takes the deterministic assessment result produced by
    exploring_scoring.py and the local interpretation produced
    by exploring_ai.py, then generates a safe career
    recommendation.

Architecture:

    assessment.json
            ↓
    exploring_scoring.py
            ↓
    exploring_result.json
            ↓
    exploring_ai.py
            ↓
    exploring_ai_result.json
            ↓
    exploring_recommendation.py
            ↓
    exploring_recommendation.json

IMPORTANT PRINCIPLES:

    - Deterministic scoring remains the source of truth.
    - This engine does NOT recalculate career scores.
    - This engine does NOT evaluate answers.
    - This engine does NOT receive question answers.
    - This engine does NOT receive answer keys.
    - This engine does NOT receive question text.
    - This engine does NOT change deterministic rankings.
    - This engine does NOT invent careers.
    - Complete career ties are respected.
    - Partial highest-score ties are respected.
    - No external API.
    - No OpenAI API.
    - No internet.
    - No external AI package.
    - Recommendations are generated locally.
    - AI interpretation is supporting context only.

Output:
    exploring_recommendation.json
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

RECOMMENDATION_FILE = (
    BASE_DIR / "exploring_recommendation.json"
)

EXPECTED_CAREER_COUNT = 5


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
    Convert a value safely to trimmed text.
    """

    if value is None:
        return ""

    return str(value).strip()


def safe_int(
    value: Any,
    default: int = 0
) -> int:
    """
    Safely convert value to integer.
    """

    try:
        return int(value)

    except (
        ValueError,
        TypeError
    ):
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

    except (
        ValueError,
        TypeError
    ):
        return default


def format_percentage(value: Any) -> str:
    """
    Format percentage for display.
    """

    percentage = safe_float(
        value,
        0.0
    )

    if percentage.is_integer():
        return f"{int(percentage)}%"

    return f"{percentage:.1f}%"


def normalize_key(value: Any) -> str:
    """
    Normalize a string for safe comparison.
    """

    return normalize_text(
        value
    ).casefold()


# ============================================================
# CAREER LOOKUP
# ============================================================

def build_career_lookup(
    assessment: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """
    Build a lookup of canonical career IDs to career metadata
    from the assessment definition.
    """

    careers = assessment.get("careers", [])

    if not isinstance(careers, list):
        raise ValueError(
            "Assessment 'careers' must be a list."
        )

    lookup: Dict[str, Dict[str, Any]] = {}

    for career in careers:
        if not isinstance(career, dict):
            continue

        career_id = normalize_text(
            career.get("id")
        )

        if not career_id:
            continue

        lookup[career_id] = career

    if not lookup:
        raise ValueError(
            "No valid careers found in assessment."
        )

    return lookup


# ============================================================
# ASSESSMENT VALIDATION
# ============================================================

def validate_assessment(
    assessment: Dict[str, Any]
) -> None:
    """
    Validate the assessment structure required by
    the recommendation engine.
    """

    required_fields = [
        "assessment_id",
        "title",
        "version",
        "careers"
    ]

    missing = [
        field
        for field in required_fields
        if field not in assessment
    ]

    if missing:
        raise ValueError(
            "Assessment is missing required fields: "
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
            career.get("id")
        )

        career_name = normalize_text(
            career.get("name")
        )

        if not career_id:
            raise ValueError(
                "Every career must have an 'id'."
            )

        if not career_name:
            raise ValueError(
                f"Career '{career_id}' must have a 'name'."
            )

        if career_id in career_ids:
            raise ValueError(
                f"Duplicate career ID found: {career_id}"
            )

        career_ids.add(
            career_id
        )


# ============================================================
# DETERMINISTIC RESULT VALIDATION
# ============================================================

def validate_scoring_result(
    result: Dict[str, Any]
) -> None:
    """
    Validate the deterministic result produced by
    exploring_scoring.py.
    """

    required_fields = [
        "journey",
        "mode",
        "assessment_id",
        "assessment_version",
        "career_scores",
        "top_career",
        "second_career"
    ]

    missing = [
        field
        for field in required_fields
        if field not in result
    ]

    if missing:
        raise ValueError(
            "Deterministic result is missing required fields: "
            + ", ".join(missing)
        )

    if safe_int(
        result.get("journey"),
        0
    ) != 1:
        raise ValueError(
            "Deterministic result must have journey = 1."
        )

    if normalize_key(
        result.get("mode")
    ) != "exploring":
        raise ValueError(
            "Deterministic result must have mode = 'exploring'."
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

        required_score_fields = [
            "career_name",
            "score",
            "max_score",
            "percentage"
        ]

        missing_fields = [
            field
            for field in required_score_fields
            if field not in item
        ]

        if missing_fields:
            raise ValueError(
                "Career score is missing fields: "
                + ", ".join(missing_fields)
            )

        career_id = normalize_text(
            item.get("career_id")
            or item.get("career")
        )
        
        career_name = normalize_text(
            item.get("career_name")
        )

        if not career_id:
            raise ValueError(
                "Career score contains an empty career_id."
            )

        if career_id in seen_ids:
            raise ValueError(
                f"Duplicate career score found: {career_id}"
            )

        seen_ids.add(
            career_id
        )

        maximum = safe_float(
            item.get("max_score"),
            0
        )

        if maximum <= 0:
            raise ValueError(
                f"Invalid max_score for career: {career_id}"
            )

        percentage = safe_float(
            item.get("percentage"),
            -1
        )

        if percentage < 0 or percentage > 100:
            raise ValueError(
                f"Invalid percentage for career "
                f"{career_id}: {percentage}"
            )

    for field in [
        "top_career",
        "second_career"
    ]:

        if not isinstance(
            result.get(field),
            dict
        ):
            raise ValueError(
                f"'{field}' must be an object."
            )


# ============================================================
# AI RESULT VALIDATION
# ============================================================

def validate_ai_result(
    ai_result: Dict[str, Any]
) -> None:
    """
    Validate the output generated by exploring_ai.py.
    """

    if "ai_evaluation" not in ai_result:
        raise ValueError(
            "AI result is missing 'ai_evaluation'."
        )

    ai_evaluation = ai_result.get(
        "ai_evaluation"
    )

    if not isinstance(
        ai_evaluation,
        dict
    ):
        raise ValueError(
            "'ai_evaluation' must be an object."
        )

    required_fields = [
        "ai_insights",
        "strengths",
        "improvement_areas",
        "personalized_feedback",
        "recommended_domains",
        "next_step"
    ]

    missing = [
        field
        for field in required_fields
        if field not in ai_evaluation
    ]

    if missing:
        raise ValueError(
            "AI evaluation is missing fields: "
            + ", ".join(missing)
        )

    if not isinstance(
        ai_evaluation.get("ai_insights"),
        dict
    ):
        raise ValueError(
            "'ai_insights' must be an object."
        )

    if not isinstance(
        ai_evaluation.get("strengths"),
        list
    ):
        raise ValueError(
            "'strengths' must be a list."
        )

    if not isinstance(
        ai_evaluation.get("improvement_areas"),
        list
    ):
        raise ValueError(
            "'improvement_areas' must be a list."
        )

    if not isinstance(
        ai_evaluation.get("recommended_domains"),
        list
    ):
        raise ValueError(
            "'recommended_domains' must be a list."
        )

    if not isinstance(
        ai_evaluation.get("personalized_feedback"),
        str
    ):
        raise ValueError(
            "'personalized_feedback' must be a string."
        )

    if not isinstance(
        ai_evaluation.get("next_step"),
        str
    ):
        raise ValueError(
            "'next_step' must be a string."
        )


# ============================================================
# CAREER SCORE NORMALIZATION
# ============================================================

def normalize_career_scores(
    result: Dict[str, Any],
    career_lookup: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Normalize deterministic career scores without recalculating them.

    ranked_careers is preferred because it preserves the ranking
    produced by exploring_scoring.py.
    """

    normalized: List[Dict[str, Any]] = []

    career_scores = result.get("ranked_careers")

    if not isinstance(career_scores, list) or not career_scores:
        career_scores = result.get("career_scores", [])

    if not isinstance(career_scores, list):
        return normalized

    for index, item in enumerate(career_scores, start=1):

        if not isinstance(item, dict):
            continue

        career_id = normalize_text(
            item.get("career_id")
            or item.get("career")
        )

        if not career_id:
            continue

        # Resolve the canonical career ID if a display name
        # was supplied instead.
        if career_id not in career_lookup:

            for known_id, metadata in career_lookup.items():

                known_name = normalize_text(
                    metadata.get("name")
                )

                known_short_name = normalize_text(
                    metadata.get("short_name")
                )

                if (
                    normalize_key(known_name)
                    == normalize_key(career_id)
                    or
                    normalize_key(known_short_name)
                    == normalize_key(career_id)
                ):
                    career_id = known_id
                    break

        metadata = career_lookup.get(
            career_id,
            {}
        )

        career_name = normalize_text(
            item.get("career_name")
        )

        if not career_name:
            career_name = normalize_text(
                metadata.get("name")
            )

        if not career_name:
            career_name = career_id

        normalized.append({
            "rank": safe_int(
                item.get("rank"),
                index
            ),
            "career_id": career_id,
            "career_name": career_name,
            "score": safe_int(
                item.get("score"),
                0
            ),
            "max_score": safe_int(
                item.get("max_score"),
                0
            ),
            "percentage": safe_float(
                item.get("percentage"),
                0.0
            )
        })

    # Preserve deterministic ranking from exploring_scoring.py.
    normalized.sort(
        key=lambda item: item["rank"]
    )

    return normalized

# ============================================================
# TIE ANALYSIS
# ============================================================

def analyze_career_tie(
    career_scores: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Analyze highest deterministic score.

    Handles:

        no tie
        partial tie
        complete tie
    """

    if not career_scores:
        return {
            "is_tie": False,
            "complete_tie": False,
            "highest_percentage": 0.0,
            "tied_careers": [],
            "tied_career_ids": []
        }

    highest_percentage = max(
        safe_float(
            item.get("percentage"),
            0
        )
        for item in career_scores
    )

    tied_items = [
        item
        for item in career_scores
        if safe_float(
            item.get("percentage"),
            0
        ) == highest_percentage
    ]

    tied_careers = [
        normalize_text(
            item.get("career_name")
        )
        for item in tied_items
    ]

    tied_ids = [
        normalize_text(
            item.get("career_id")
        )
        for item in tied_items
    ]

    return {
        "is_tie": len(tied_items) > 1,

        "complete_tie": (
            len(tied_items)
            == len(career_scores)
        ),

        "highest_percentage": highest_percentage,

        "tied_careers": tied_careers,

        "tied_career_ids": tied_ids
    }


# ============================================================
# DIMENSION HELPERS
# ============================================================

def extract_dimensions_for_career(
    career_id: str,
    deterministic_result: Dict[str, Any],
) -> List[str]:
    """
    Extract career-specific dimensions from the deterministic scoring result.

    The current exploring_scoring.py schema may provide dimensions either as:
    1. A dictionary containing career-specific primary/secondary dimensions, or
    2. A list of dimension objects.

    Important:
    Global dimension objects are NOT assigned to a career unless the
    dimension object explicitly contains a matching career_id.
    """

    dimensions = deterministic_result.get("dimensions", [])

    if not dimensions:
        return []

    extracted: List[str] = []

    # ---------------------------------------------------------
    # Schema 1:
    # {
    #     "primary": [
    #         {
    #             "career_id": "data",
    #             "dimension": "analytical_reasoning"
    #         }
    #     ]
    # }
    # ---------------------------------------------------------
    if isinstance(dimensions, dict):

        for category in ("primary", "secondary"):

            items = dimensions.get(category, [])

            if not isinstance(items, list):
                continue

            for item in items:

                if not isinstance(item, dict):
                    continue

                item_career_id = normalize_text(
                    item.get("career_id")
                    or item.get("career")
                )

                dimension = normalize_text(
                    item.get("dimension")
                )

                if (
                    item_career_id == normalize_text(career_id)
                    and dimension
                ):
                    extracted.append(dimension)

        return list(dict.fromkeys(extracted))

    # ---------------------------------------------------------
    # Schema 2:
    # [
    #     {
    #         "dimension": "analytical_reasoning",
    #         "correct": 2,
    #         "total": 2,
    #         "percentage": 100,
    #         "level": "Strong"
    #     }
    # ]
    #
    # These are GLOBAL dimensions.
    #
    # Therefore, only use them here if the individual dimension
    # explicitly identifies a career.
    # ---------------------------------------------------------
    if isinstance(dimensions, list):

        for item in dimensions:

            if not isinstance(item, dict):
                continue

            item_career_id = normalize_text(
                item.get("career_id")
                or item.get("career")
            )

            dimension = normalize_text(
                item.get("dimension")
            )

            if (
                item_career_id
                and item_career_id == normalize_text(career_id)
                and dimension
            ):
                extracted.append(dimension)

        return list(dict.fromkeys(extracted))

    return []


def clean_dimension_label(
    value: Any
) -> str:
    """
    Convert internal dimension identifiers into readable
    user-facing labels.

    Examples:

        machine_learning_reasoning
            →
        Machine Learning Reasoning

        data_reasoning
            →
        Data Reasoning
    """

    text = normalize_text(
        value
    )

    if not text:
        return ""

    text = text.replace(
        "_",
        " "
    )

    text = text.replace(
        "-",
        " "
    )

    words = text.split()

    return " ".join(
        word.capitalize()
        for word in words
    )


def extract_supporting_strengths(
    career_id: str,
    ai_result: Dict[str, Any],
    deterministic_result: Dict[str, Any]
) -> List[str]:
    """
    Select a small, career-relevant set of supporting strengths.

    Priority:

        1. Career-specific deterministic dimensions
        2. AI strength dimensions
        3. Deduplicated fallback

    IMPORTANT:
        This function does NOT assign the same dimensions to every
        career merely because the user has global strengths.
    """

    output: List[str] = []

    # --------------------------------------------------------
    # Career-specific deterministic dimensions
    # --------------------------------------------------------

    deterministic_dimensions = (
        extract_dimensions_for_career(
            career_id,
            deterministic_result
        )
    )

    for dimension in deterministic_dimensions:

        label = clean_dimension_label(
            dimension
        )

        if label and label not in output:
            output.append(
                label
            )

        if len(output) >= 5:
            return output

    # --------------------------------------------------------
    # AI strengths as supporting fallback
    # --------------------------------------------------------

    ai_evaluation = ai_result.get(
        "ai_evaluation",
        {}
    )

    strengths = ai_evaluation.get(
        "strengths",
        []
    )

    if isinstance(
        strengths,
        list
    ):

        for item in strengths:

            if not isinstance(
                item,
                dict
            ):
                continue

            dimension = normalize_text(
                item.get("dimension")
            )

            label = clean_dimension_label(
                dimension
            )

            if label and label not in output:
                output.append(
                    label
                )

            if len(output) >= 5:
                break

    return output[:5]


# ============================================================
# CAREER DESCRIPTIONS
# ============================================================

CAREER_FOCUS: Dict[str, str] = {

    "ui_ux": (
        "designing user experiences, interfaces, usability, "
        "visual hierarchy, user research, and interaction flows"
    ),

    "development": (
        "building software, solving programming problems, "
        "debugging systems, designing algorithms, and developing "
        "applications"
    ),

    "data_analytics": (
        "working with data, cleaning information, finding patterns, "
        "creating visualizations, analyzing evidence, and "
        "supporting decisions with data"
    ),

    "ai_ml": (
        "building intelligent systems, working with machine "
        "learning, prediction, pattern recognition, model "
        "evaluation, and data-driven systems"
    ),

    "cybersecurity": (
        "understanding security risks, detecting threats, "
        "reasoning about incidents, identifying vulnerabilities, "
        "and protecting systems"
    )
}


def get_career_focus(
    career_id: str,
    career_name: str
) -> str:
    """
    Return a safe career focus description.

    Unknown careers receive a generic description rather than
    inventing unsupported details.
    """

    if career_id in CAREER_FOCUS:
        return CAREER_FOCUS[
            career_id
        ]

    return (
        f"exploring the skills and practical work associated "
        f"with {career_name}"
    )


# ============================================================
# EXPLORATION PROJECTS
# ============================================================

CAREER_PROJECTS: Dict[str, str] = {

    "ui_ux": (
        "Redesign a simple mobile app screen and create a basic "
        "clickable prototype."
    ),

    "development": (
        "Build a small beginner-friendly application such as a "
        "to-do list, calculator, or simple CRUD app."
    ),

    "data_analytics": (
        "Take a small public dataset, clean it, create 2–3 "
        "meaningful visualizations, and write three findings "
        "from the data."
    ),

    "ai_ml": (
        "Build a small beginner machine-learning project using "
        "a simple dataset and compare the performance of two "
        "basic models."
    ),

    "cybersecurity": (
        "Complete a beginner cybersecurity lab focused on "
        "identifying common security risks and documenting "
        "safe defensive steps."
    )
}


def get_beginner_project(
    career_id: str,
    career_name: str
) -> str:
    """
    Return a safe beginner-level exploration project.
    """

    if career_id in CAREER_PROJECTS:
        return CAREER_PROJECTS[
            career_id
        ]

    return (
        f"Complete a small beginner-level project related to "
        f"{career_name} and record what you learned."
    )


# ============================================================
# WHY-IT-FITS GENERATION
# ============================================================

def build_why_it_fits(
    career_id: str,
    career_name: str,
    percentage: Any,
    supporting_dimensions: List[str],
    complete_tie: bool,
    partial_tie: bool,
    is_primary: bool = True
) -> str:
    """
    Generate explanation for why a career is recommended.

    Does not alter deterministic ranking.
    """

    score_text = format_percentage(
        percentage
    )

    focus = get_career_focus(
        career_id,
        career_name
    )

    if complete_tie:

        if supporting_dimensions:

            dimensions_text = ", ".join(
                supporting_dimensions[:3]
            )

            return (
                f"{career_name} is a strong exploration area with "
                f"a deterministic score of {score_text}. It is tied "
                f"with all other assessed careers, so it should not "
                f"be treated as the single best career. Its relevant "
                f"supporting signals include {dimensions_text}. "
                f"This area involves {focus}."
            )

        return (
            f"{career_name} is a strong exploration area with a "
            f"deterministic score of {score_text}. It is tied with "
            "all other assessed careers, so it should be explored "
            "alongside the other equally strong options."
        )

    if partial_tie:

        if supporting_dimensions:

            dimensions_text = ", ".join(
                supporting_dimensions[:3]
            )

            return (
                f"{career_name} received an equal highest "
                f"deterministic score of {score_text}. It is one "
                f"of the strongest assessed areas, supported by "
                f"signals such as {dimensions_text}. This area "
                f"involves {focus}."
            )

        return (
            f"{career_name} received an equal highest deterministic "
            f"score of {score_text}. It is therefore one of the "
            "strongest areas to explore further."
        )

    score_phrase = (
        "received the highest deterministic score of"
        if is_primary
        else "received a deterministic score of"
    )

    if supporting_dimensions:

        dimensions_text = ", ".join(
            supporting_dimensions[:3]
        )

        return (
            f"{career_name} {score_phrase} "
            f"{score_text}. The result is supported by "
            f"signals such as {dimensions_text}. This area "
            f"involves {focus} and is a useful direction to "
            "explore further."
        )

    return (
        f"{career_name} {score_phrase} "
        f"{score_text}. This makes it a useful area to explore "
        "further through practical learning and small projects."
    )


# ============================================================
# PRIMARY CAREER
# ============================================================

def build_primary_career(
    career_scores: List[Dict[str, Any]],
    tie_info: Dict[str, Any],
    ai_result: Dict[str, Any],
    deterministic_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build the primary-career section.

    Complete tie:
        no primary career

    Partial tie:
        no single primary career

    No tie:
        highest deterministic career is primary
    """

    if not career_scores:

        return {
            "career_id": None,
            "career": None,
            "score": None,
            "max_score": None,
            "percentage": None,
            "status": "not_available",
            "why_it_fits": (
                "No deterministic career result is available."
            ),
            "supporting_dimensions": []
        }

    if tie_info.get(
        "complete_tie"
    ):

        return {
            "career_id": None,
            "career": None,
            "score": None,
            "max_score": None,
            "percentage": tie_info.get(
                "highest_percentage"
            ),
            "status": "no_single_primary",
            "why_it_fits": (
                "No single primary career is identified because "
                "all assessed careers have the same deterministic "
                "score."
            ),
            "supporting_dimensions": []
        }

    if tie_info.get(
        "is_tie"
    ):

        return {
            "career_id": None,
            "career": None,
            "score": None,
            "max_score": None,
            "percentage": tie_info.get(
                "highest_percentage"
            ),
            "status": "highest_score_tie",
            "why_it_fits": (
                "No single primary career is identified because "
                "multiple careers share the highest deterministic "
                "score."
            ),
            "supporting_dimensions": []
        }

    top = career_scores[0]

    career_id = normalize_text(
        top.get("career_id")
    )

    career_name = normalize_text(
        top.get("career_name")
    )

    supporting_dimensions = (
        extract_supporting_strengths(
            career_id,
            ai_result,
            deterministic_result
        )
    )

    return {
        "career_id": career_id,

        "career": career_name,

        "score": top.get(
            "score"
        ),

        "max_score": top.get(
            "max_score"
        ),

        "percentage": top.get(
            "percentage"
        ),

        "status": "primary",

        "why_it_fits": build_why_it_fits(
    career_id,
    career_name,
    top.get("percentage"),
    supporting_dimensions,
    False,
    False,
    is_primary=True
),

        "supporting_dimensions": (
            supporting_dimensions
        )
    }


# ============================================================
# ALTERNATIVE CAREERS
# ============================================================

def build_alternative_careers(
    career_scores: List[Dict[str, Any]],
    tie_info: Dict[str, Any],
    ai_result: Dict[str, Any],
    deterministic_result: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Build alternative/exploration career list.

    Complete tie:
        all careers are returned.

    Partial tie:
        all tied highest careers are returned.

    No tie:
        next two strongest careers are returned.

    Supporting dimensions are career-specific. They must only be
    attached when deterministic evidence exists for that career.
    """

    output: List[Dict[str, Any]] = []

    if not career_scores:
        return output

    if tie_info.get("complete_tie"):

        selected = career_scores

    elif tie_info.get("is_tie"):

        tied_ids = set(
            tie_info.get(
                "tied_career_ids",
                []
            )
        )

        selected = [
            item
            for item in career_scores
            if normalize_text(
                item.get("career_id")
            ) in tied_ids
        ]

    else:

        selected = career_scores[1:3]

    for item in selected:

        career_id = normalize_text(
            item.get("career_id")
        )

        career_name = normalize_text(
            item.get("career_name")
        )

        percentage = item.get(
            "percentage"
        )

        # IMPORTANT:
        # Do not use global AI strengths here.
        # Extract only dimensions that have actual deterministic
        # evidence for this specific career.
        supporting_dimensions = extract_dimensions_for_career(
            deterministic_result,
            career_id
        )

        output.append({
            "career_id": career_id,

            "career": career_name,

            "score": item.get(
                "score"
            ),

            "max_score": item.get(
                "max_score"
            ),

            "percentage": percentage,

            "why_it_fits": build_why_it_fits(
                career_id,
                career_name,
                percentage,
                supporting_dimensions,
                tie_info.get(
                    "complete_tie",
                    False
                ),
                tie_info.get(
                    "is_tie",
                    False
                ),
                is_primary=False
            ),

            "supporting_dimensions": (
                supporting_dimensions
            )
        })

    return output


# ============================================================
# RECOMMENDATION TYPE
# ============================================================

def determine_recommendation_type(
    tie_info: Dict[str, Any],
    career_scores: List[Dict[str, Any]]
) -> str:
    """
    Determine recommendation state.
    """

    if not career_scores:
        return "insufficient_result"

    if tie_info.get(
        "complete_tie"
    ):
        return "complete_tie"

    if tie_info.get(
        "is_tie"
    ):
        return "highest_score_tie"

    return "single_primary"


# ============================================================
# SUMMARY
# ============================================================

def build_recommendation_summary(
    career_scores: List[Dict[str, Any]],
    tie_info: Dict[str, Any],
    recommendation_type: str
) -> str:
    """
    Build a student-friendly recommendation summary.
    """

    if recommendation_type == "complete_tie":

        careers = [
            normalize_text(
                item.get("career_name")
            )
            for item in career_scores
            if normalize_text(
                item.get("career_name")
            )
        ]

        career_text = ", ".join(
            careers
        )

        percentage = format_percentage(
            tie_info.get(
                "highest_percentage"
            )
        )

        return (
            f"All five assessed career areas received the same "
            f"deterministic score of {percentage}. No single primary "
            f"career can therefore be selected. The strongest "
            f"recommendation is to explore all five assessed areas — "
            f"{career_text} — through small practical projects "
            "before narrowing your focus."
        )

    if recommendation_type == "highest_score_tie":

        tied = ", ".join(
            tie_info.get(
                "tied_careers",
                []
            )
        )

        percentage = format_percentage(
            tie_info.get(
                "highest_percentage"
            )
        )

        return (
            f"{tied} share the highest deterministic score of "
            f"{percentage}. No single primary career is selected. "
            "These tied areas should be explored through practical "
            "activities before choosing a stronger long-term focus."
        )

    if career_scores:

        top = career_scores[0]

        career = normalize_text(
            top.get("career_name")
        )

        percentage = format_percentage(
            top.get("percentage")
        )

        return (
            f"{career} is the primary exploration recommendation "
            f"with the highest deterministic score of "
            f"{percentage}. The result is a useful guide for "
            "exploration rather than a guaranteed career outcome."
        )

    return (
        "The assessment does not contain enough information to "
        "produce a career recommendation."
    )


# ============================================================
# NEXT STEPS
# ============================================================

def build_next_steps(
    career_scores: List[Dict[str, Any]],
    tie_info: Dict[str, Any],
    recommendation_type: str
) -> List[Dict[str, str]]:
    """
    Generate practical next steps.

    COMPLETE TIE:
        All five careers receive an exploration activity.

    HIGHEST-SCORE TIE:
        All tied careers receive an exploration activity.

    SINGLE PRIMARY:
        Primary career receives the first activity, followed by
        reflection and comparison.
    """

    output: List[Dict[str, str]] = []

    # ========================================================
    # COMPLETE TIE
    # ========================================================

    if recommendation_type == "complete_tie":

        for item in career_scores:

            career_id = normalize_text(
                item.get("career_id")
            )

            career_name = normalize_text(
                item.get("career_name")
            )

            output.append({
                "step": (
                    f"Explore {career_name}"
                ),

                "action": get_beginner_project(
                    career_id,
                    career_name
                )
            })

        output.append({
            "step": "Compare your experience",

            "action": (
                "After completing the exploration activities, "
                "compare which type of work you found most "
                "interesting, enjoyable, motivating, and worth "
                "learning further."
            )
        })

        return output

    # ========================================================
    # HIGHEST-SCORE TIE
    # ========================================================

    if recommendation_type == "highest_score_tie":

        tied_ids = set(
            tie_info.get(
                "tied_career_ids",
                []
            )
        )

        selected = [
            item
            for item in career_scores
            if normalize_text(
                item.get("career_id")
            ) in tied_ids
        ]

        for item in selected:

            career_id = normalize_text(
                item.get("career_id")
            )

            career_name = normalize_text(
                item.get("career_name")
            )

            output.append({
                "step": (
                    f"Explore {career_name}"
                ),

                "action": get_beginner_project(
                    career_id,
                    career_name
                )
            })

        output.append({
            "step": "Compare the tied areas",

            "action": (
                "Compare the type of work, skills, problem "
                "solving, and practical experience involved in "
                "each tied area before choosing where to focus."
            )
        })

        return output

    # ========================================================
    # SINGLE PRIMARY
    # ========================================================

    if recommendation_type == "single_primary":

        if career_scores:

            top = career_scores[0]

            career_id = normalize_text(
                top.get("career_id")
            )

            career_name = normalize_text(
                top.get("career_name")
            )

            output.append({
                "step": (
                    f"Start with {career_name}"
                ),

                "action": get_beginner_project(
                    career_id,
                    career_name
                )
            })

            output.append({
                "step": "Reflect on the experience",

                "action": (
                    f"After completing the project, evaluate "
                    f"whether you enjoyed the type of work involved "
                    f"in {career_name} and whether you want to "
                    "continue developing the related skills."
                )
            })

            output.append({
                "step": "Compare before deciding",

                "action": (
                    "Try at least one small activity from another "
                    "assessed career before making a longer-term "
                    "specialization decision."
                )
            })

            return output

    # ========================================================
    # INSUFFICIENT RESULT
    # ========================================================

    output.append({
        "step": "Continue exploration",

        "action": (
            "Choose one assessed computer science area and "
            "complete a small beginner-level practical project."
        )
    })

    return output


# ============================================================
# AI INSIGHT SUMMARY
# ============================================================

def build_ai_context_summary(
    ai_result: Dict[str, Any],
    deterministic_result: Dict[str, Any],
    career_scores: List[Dict[str, Any]],
    tie_info: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Preserve useful interpretation information for the
    recommendation output.

    IMPORTANT:
        Deterministic career ranking is the source of truth.

        AI interpretation may provide supporting context, but
        it must never determine or override the top career.
    """

    ai_evaluation = ai_result.get(
        "ai_evaluation",
        {}
    )

    insights = ai_evaluation.get(
        "ai_insights",
        {}
    )

    strengths = ai_evaluation.get(
        "strengths",
        []
    )

    improvement_areas = ai_evaluation.get(
        "improvement_areas",
        []
    )

    # ========================================================
    # DETERMINISTIC OVERALL RESULT
    # ========================================================

    if not career_scores:
        raise ValueError(
            "Cannot build supporting AI insights because "
            "deterministic career scores are missing."
        )

    # career_scores has already been normalized from the
    # deterministic ranking produced by exploring_scoring.py.
    top_career = career_scores[0]

    top_career_name = normalize_text(
        top_career.get(
            "career_name"
        )
    )

    top_percentage = safe_float(
        top_career.get(
            "percentage"
        ),
        0.0
    )

    # --------------------------------------------------------
    # Calculate totals from deterministic scores.
    # --------------------------------------------------------

    total_correct = sum(
        safe_int(
            item.get("score"),
            0
        )
        for item in career_scores
        if isinstance(item, dict)
    )

    total_questions = sum(
        safe_int(
            item.get("max_score"),
            0
        )
        for item in career_scores
        if isinstance(item, dict)
    )

    # ========================================================
    # DETERMINISTIC OVERALL MESSAGE
    # ========================================================

    if tie_info.get("complete_tie"):

        overall = (
            f"You answered {total_correct} of "
            f"{total_questions} questions correctly. "
            f"All assessed career areas share the same "
            f"deterministic career score of "
            f"{format_percentage(top_percentage)}."
        )

        top_career_explanation = (
            "The assessment produced a complete tie across "
            "the available career areas. No single career "
            "has a stronger deterministic result."
        )

    elif tie_info.get("is_tie"):

        tied_careers = [
            normalize_text(name)
            for name in tie_info.get(
                "tied_careers",
                []
            )
            if normalize_text(name)
        ]

        tied_text = ", ".join(
            tied_careers
        )

        overall = (
            f"You answered {total_correct} of "
            f"{total_questions} questions correctly. "
            f"{tied_text} share the highest deterministic "
            f"career result at "
            f"{format_percentage(top_percentage)}."
        )

        top_career_explanation = (
            f"{tied_text} share the highest deterministic "
            f"career result at "
            f"{format_percentage(top_percentage)}. "
            "The assessment therefore does not establish "
            "a single highest-scoring career."
        )

    else:

        overall = (
            f"You answered {total_correct} of "
            f"{total_questions} questions correctly. "
            f"Your strongest deterministic career result "
            f"is {top_career_name} at "
            f"{format_percentage(top_percentage)}."
        )

        top_career_explanation = (
            f"{top_career_name} achieved the highest "
            f"deterministic career result at "
            f"{format_percentage(top_percentage)}. "
            "This means your current assessment profile "
            "aligns most strongly with this career area "
            "among the available options."
        )

    # ========================================================
    # STRENGTHS
    # ========================================================

    strength_names: List[str] = []

    if isinstance(
        strengths,
        list
    ):

        for item in strengths:

            if not isinstance(
                item,
                dict
            ):
                continue

            name = clean_dimension_label(
                item.get("dimension")
            )

            if name and name not in strength_names:
                strength_names.append(
                    name
                )

            if len(strength_names) >= 7:
                break

    # ========================================================
    # IMPROVEMENT AREAS
    # ========================================================

    improvement_names: List[str] = []

    if isinstance(
        improvement_areas,
        list
    ):

        for item in improvement_areas:

            if not isinstance(
                item,
                dict
            ):
                continue

            name = clean_dimension_label(
                item.get("dimension")
            )

            if name and name not in improvement_names:
                improvement_names.append(
                    name
                )

            if len(improvement_names) >= 5:
                break

    # ========================================================
    # FINAL SUPPORTING INSIGHTS
    # ========================================================

    return {
        # These two fields are ALWAYS generated from the
        # deterministic result.
        "overall": overall,

        "thinking_pattern": normalize_text(
            insights.get(
                "thinking_pattern"
            )
        ),

        "top_career_explanation": (
            top_career_explanation
        ),

        "personalized_feedback": normalize_text(
            ai_evaluation.get(
                "personalized_feedback"
            )
        ),

        "strengths": strength_names,

        "improvement_areas": improvement_names
    }


# ============================================================
# FINAL RECOMMENDATION BUILD
# ============================================================

def generate_recommendation(
    assessment: Dict[str, Any],
    deterministic_result: Dict[str, Any],
    ai_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Main recommendation engine.

    Deterministic scores remain authoritative.
    """

    career_lookup = build_career_lookup(
        assessment
    )

    career_scores = normalize_career_scores(
        deterministic_result,
        career_lookup
    )

    tie_info = analyze_career_tie(
        career_scores
    )

    recommendation_type = (
        determine_recommendation_type(
            tie_info,
            career_scores
        )
    )

    primary_career = build_primary_career(
        career_scores,
        tie_info,
        ai_result,
        deterministic_result
    )

    alternatives = build_alternative_careers(
        career_scores,
        tie_info,
        ai_result,
        deterministic_result
    )

    summary = build_recommendation_summary(
        career_scores,
        tie_info,
        recommendation_type
    )

    next_steps = build_next_steps(
        career_scores,
        tie_info,
        recommendation_type
    )

    ai_summary = build_ai_context_summary(
        ai_result=ai_result,
    deterministic_result=deterministic_result,
    career_scores=career_scores,
    tie_info=tie_info
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

            "journey": 1,

            "mode": "exploring"
        },

        "source": {
            "deterministic_engine": (
                "exploring_scoring.py"
            ),

            "deterministic_result": (
                "exploring_result.json"
            ),

            "interpretation_engine": (
                "exploring_ai.py"
            ),

            "interpretation_result": (
                "exploring_ai_result.json"
            ),

            "recommendation_engine": (
                "exploring_recommendation.py"
            ),

            "engine_type": (
                "local_rule_based"
            ),

            "external_api": False,

            "score_recalculation": False,

            "answer_evaluation": False,

            "question_access": False,

            "answer_key_access": False
        },

        "recommendation": {
            "type": recommendation_type,

            "summary": summary,

            "career_tie": tie_info,

            "primary_career": primary_career,

            "alternative_careers": alternatives,

            "next_steps": next_steps
        },

        "supporting_ai_insights": ai_summary,

        "deterministic_career_scores": career_scores
    }


# ============================================================
# OUTPUT VALIDATION
# ============================================================

def validate_recommendation_output(
    output: Dict[str, Any]
) -> None:
    """
    Validate final recommendation structure.
    """

    required = [
        "assessment",
        "source",
        "recommendation",
        "supporting_ai_insights",
        "deterministic_career_scores"
    ]

    missing = [
        field
        for field in required
        if field not in output
    ]

    if missing:
        raise ValueError(
            "Recommendation output is missing fields: "
            + ", ".join(missing)
        )

    assessment = output.get(
        "assessment"
    )

    if not isinstance(
        assessment,
        dict
    ):
        raise ValueError(
            "'assessment' must be an object."
        )

    source = output.get(
        "source"
    )

    if not isinstance(
        source,
        dict
    ):
        raise ValueError(
            "'source' must be an object."
        )

    recommendation = output.get(
        "recommendation"
    )

    if not isinstance(
        recommendation,
        dict
    ):
        raise ValueError(
            "'recommendation' must be an object."
        )

    required_recommendation_fields = [
        "type",
        "summary",
        "career_tie",
        "primary_career",
        "alternative_careers",
        "next_steps"
    ]

    missing_recommendation_fields = [
        field
        for field in required_recommendation_fields
        if field not in recommendation
    ]

    if missing_recommendation_fields:
        raise ValueError(
            "Recommendation is missing fields: "
            + ", ".join(
                missing_recommendation_fields
            )
        )

    recommendation_type = normalize_text(
        recommendation.get(
            "type"
        )
    )

    allowed_types = {
        "single_primary",
        "highest_score_tie",
        "complete_tie",
        "insufficient_result"
    }

    if recommendation_type not in allowed_types:
        raise ValueError(
            f"Invalid recommendation type: "
            f"{recommendation_type}"
        )

    if not isinstance(
        recommendation.get(
            "primary_career"
        ),
        dict
    ):
        raise ValueError(
            "'primary_career' must be an object."
        )

    if not isinstance(
        recommendation.get(
            "alternative_careers"
        ),
        list
    ):
        raise ValueError(
            "'alternative_careers' must be a list."
        )

    if not isinstance(
        recommendation.get(
            "next_steps"
        ),
        list
    ):
        raise ValueError(
            "'next_steps' must be a list."
        )

    career_scores = output.get(
        "deterministic_career_scores"
    )

    if not isinstance(
        career_scores,
        list
    ):
        raise ValueError(
            "'deterministic_career_scores' must be a list."
        )

    for item in career_scores:

        if not isinstance(
            item,
            dict
        ):
            raise ValueError(
                "Every deterministic career score must be "
                "an object."
            )

        for field in [
            "career_id",
            "career_name",
            "score",
            "max_score",
            "percentage"
        ]:

            if field not in item:
                raise ValueError(
                    "Deterministic career score is missing "
                    f"'{field}'."
                )

    # ========================================================
    # Primary career validation
    # ========================================================

    primary = recommendation.get(
        "primary_career"
    )

    primary_status = normalize_text(
        primary.get("status")
    )

    if recommendation_type == "single_primary":

        if not primary.get("career_id"):
            raise ValueError(
                "single_primary recommendation must contain "
                "a primary career."
            )

        if primary_status != "primary":
            raise ValueError(
                "Primary career status must be 'primary'."
            )

    else:

        if primary.get("career_id") is not None:
            raise ValueError(
                "A tied recommendation must not select a "
                "single primary career."
            )

    # ========================================================
    # Alternative career validation
    # ========================================================

    allowed_ids = {
        normalize_text(
            item.get("career_id")
        )
        for item in career_scores
    }

    for item in recommendation.get(
        "alternative_careers",
        []
    ):

        if not isinstance(
            item,
            dict
        ):
            raise ValueError(
                "Every alternative career must be an object."
            )

        career_id = normalize_text(
            item.get("career_id")
        )

        if career_id not in allowed_ids:
            raise ValueError(
                "Alternative career is not present in "
                "deterministic career scores: "
                f"{career_id}"
            )

        if not item.get("career"):
            raise ValueError(
                "Alternative career must have a career name."
            )

        if not item.get("why_it_fits"):
            raise ValueError(
                "Alternative career must have a why_it_fits "
                "explanation."
            )

    # ========================================================
    # Next-step validation
    # ========================================================

    for item in recommendation.get(
        "next_steps",
        []
    ):

        if not isinstance(
            item,
            dict
        ):
            raise ValueError(
                "Every next step must be an object."
            )

        if not item.get("step"):
            raise ValueError(
                "Next step is missing 'step'."
            )

        if not item.get("action"):
            raise ValueError(
                "Next step is missing 'action'."
            )


# ============================================================
# DETERMINISTIC SAFETY CHECKS
# ============================================================

def enforce_recommendation_constraints(
    output: Dict[str, Any]
) -> None:
    """
    Enforce rules that prevent recommendation drift.

    The recommendation engine may only use careers present in
    deterministic career scores.
    """

    recommendation = output.get(
        "recommendation",
        {}
    )

    career_scores = output.get(
        "deterministic_career_scores",
        []
    )

    allowed_ids = {
        normalize_text(
            item.get("career_id")
        )
        for item in career_scores
        if isinstance(
            item,
            dict
        )
    }

    allowed_names = {
        normalize_key(
            item.get("career_name")
        )
        for item in career_scores
        if isinstance(
            item,
            dict
        )
    }

    recommendation_type = normalize_text(
        recommendation.get("type")
    )

    primary = recommendation.get(
        "primary_career",
        {}
    )

    # ========================================================
    # Primary career safety
    # ========================================================

    primary_id = normalize_text(
        primary.get("career_id")
    )

    if primary_id:

        if primary_id not in allowed_ids:
            raise ValueError(
                "Primary career is not present in deterministic "
                "career scores."
            )

        primary_name = normalize_key(
            primary.get("career")
        )

        if primary_name not in allowed_names:
            raise ValueError(
                "Primary career name does not match deterministic "
                "career results."
            )

    # ========================================================
    # Complete tie safety
    # ========================================================

    tie_info = recommendation.get(
        "career_tie",
        {}
    )

    if recommendation_type == "complete_tie":

        if not tie_info.get(
            "complete_tie"
        ):
            raise ValueError(
                "Recommendation says complete_tie but tie "
                "analysis does not."
            )

        if primary_id:
            raise ValueError(
                "Complete tie cannot contain a primary career."
            )

        # Complete tie must return every assessed career.
        alternative_ids = {
            normalize_text(
                item.get("career_id")
            )
            for item in recommendation.get(
                "alternative_careers",
                []
            )
        }

        if alternative_ids != allowed_ids:
            raise ValueError(
                "Complete tie must return all assessed careers "
                "as exploration careers."
            )

    # ========================================================
    # Highest-score tie safety
    # ========================================================

    if recommendation_type == "highest_score_tie":

        if not tie_info.get(
            "is_tie"
        ):
            raise ValueError(
                "Recommendation says highest_score_tie but "
                "tie analysis does not."
            )

        if primary_id:
            raise ValueError(
                "Highest-score tie cannot contain a single "
                "primary career."
            )

        tied_ids = set(
            tie_info.get(
                "tied_career_ids",
                []
            )
        )

        alternative_ids = {
            normalize_text(
                item.get("career_id")
            )
            for item in recommendation.get(
                "alternative_careers",
                []
            )
        }

        if alternative_ids != tied_ids:
            raise ValueError(
                "Highest-score tie must return all tied careers "
                "as exploration careers."
            )

    # ========================================================
    # Alternative career safety
    # ========================================================

    alternatives = recommendation.get(
        "alternative_careers",
        []
    )

    for item in alternatives:

        career_id = normalize_text(
            item.get("career_id")
        )

        if career_id not in allowed_ids:
            raise ValueError(
                "Recommendation contains a career outside the "
                "deterministic career list: "
                f"{career_id}"
            )

    # ========================================================
    # Recommendation cannot be empty
    # ========================================================

    if recommendation_type != "insufficient_result":

        if not alternatives and not primary_id:
            raise ValueError(
                "Recommendation contains neither a primary "
                "career nor alternative careers."
            )


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


def print_recommendation_result(
    result: Dict[str, Any]
) -> None:
    """
    Display recommendation in a clean terminal format.
    """

    recommendation = result.get(
        "recommendation",
        {}
    )

    recommendation_type = normalize_text(
        recommendation.get(
            "type"
        )
    )

    print_header(
        "MINERVA — JOURNEY 1: CAREER RECOMMENDATION"
    )

    # ========================================================
    # STATUS
    # ========================================================

    print()
    print(
        "RECOMMENDATION STATUS"
    )
    print("-" * 70)

    if recommendation_type == "complete_tie":

        print(
            "COMPLETE TIE — NO SINGLE PRIMARY CAREER"
        )

    elif recommendation_type == "highest_score_tie":

        print(
            "HIGHEST-SCORE TIE — NO SINGLE PRIMARY CAREER"
        )

    elif recommendation_type == "single_primary":

        print(
            "SINGLE PRIMARY CAREER IDENTIFIED"
        )

    else:

        print(
            "INSUFFICIENT RESULT"
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print(
        "RECOMMENDATION SUMMARY"
    )
    print("-" * 70)

    print(
        recommendation.get(
            "summary",
            "N/A"
        )
    )

    # ========================================================
    # PRIMARY CAREER
    # ========================================================

    print()
    print(
        "PRIMARY CAREER"
    )
    print("-" * 70)

    primary = recommendation.get(
        "primary_career",
        {}
    )

    primary_name = normalize_text(
        primary.get(
            "career"
        )
    )

    if primary_name:

        print(
            f"Career: {primary_name}"
        )

        print(
            f"Score: "
            f"{format_percentage(primary.get('percentage'))}"
        )

        print(
            f"Why it fits: "
            f"{primary.get('why_it_fits', 'N/A')}"
        )

        dimensions = primary.get(
            "supporting_dimensions",
            []
        )

        if dimensions:

            print(
                "Supporting dimensions: "
                + ", ".join(
                    dimensions
                )
            )

    else:

        print(
            "No single primary career identified."
        )

    # ========================================================
    # ALTERNATIVE / EXPLORATION CAREERS
    # ========================================================

    print()
    print(
        "ALTERNATIVE / EXPLORATION CAREERS"
    )
    print("-" * 70)

    alternatives = recommendation.get(
        "alternative_careers",
        []
    )

    if alternatives:

        for index, item in enumerate(
            alternatives,
            start=1
        ):

            career = normalize_text(
                item.get(
                    "career"
                )
            )

            percentage = format_percentage(
                item.get(
                    "percentage"
                )
            )

            print(
                f"{index}. {career} "
                f"({percentage})"
            )

            print(
                f"   Why it fits: "
                f"{item.get('why_it_fits', '')}"
            )

            dimensions = item.get(
                "supporting_dimensions",
                []
            )

            if dimensions:

                print(
                    "   Supporting dimensions: "
                    + ", ".join(
                        dimensions
                    )
                )

    else:

        print(
            "No alternative careers returned."
        )

    # ========================================================
    # NEXT STEPS
    # ========================================================

    print()
    print(
        "NEXT STEPS"
    )
    print("-" * 70)

    next_steps = recommendation.get(
        "next_steps",
        []
    )

    if next_steps:

        for index, item in enumerate(
            next_steps,
            start=1
        ):

            print(
                f"{index}. "
                f"{item.get('step', 'Step')}"
            )

            print(
                f"   {item.get('action', '')}"
            )

    else:

        print(
            "No next steps returned."
        )

    # ========================================================
    # AI SUPPORTING INSIGHTS
    # ========================================================

    print()
    print(
        "SUPPORTING AI INSIGHTS"
    )
    print("-" * 70)

    ai_summary = result.get(
        "supporting_ai_insights",
        {}
    )

    thinking_pattern = normalize_text(
        ai_summary.get(
            "thinking_pattern"
        )
    )

    if thinking_pattern:

        print(
            f"Thinking Pattern: {thinking_pattern}"
        )

    strengths = ai_summary.get(
        "strengths",
        []
    )

    if strengths:

        print(
            "Key Strength Signals: "
            + ", ".join(
                strengths[:5]
            )
        )

    improvements = ai_summary.get(
        "improvement_areas",
        []
    )

    if improvements:

        print(
            "Improvement Signals: "
            + ", ".join(
                improvements[:5]
            )
        )


# ============================================================
# MAIN ENGINE
# ============================================================

def run() -> Dict[str, Any]:

    print_header(
        "MINERVA JOURNEY 1 — "
        "EXPLORING CAREER RECOMMENDATION ENGINE"
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
        deterministic_result
    )

    print(
        "Deterministic result validated."
    )

    # ========================================================
    # LOAD AI INTERPRETATION
    # ========================================================

    print()
    print(
        "Loading local interpretation..."
    )

    ai_result = load_json(
        AI_RESULT_FILE
    )

    print(
        "Local interpretation loaded successfully."
    )

    # ========================================================
    # VALIDATE AI RESULT
    # ========================================================

    print()
    print(
        "Validating local interpretation..."
    )

    validate_ai_result(
        ai_result
    )

    print(
        "Local interpretation validated."
    )

    # ========================================================
    # SAFETY INFORMATION
    # ========================================================

    print()
    print(
        "Preparing recommendation context..."
    )

    print(
        "Question answers are not used."
    )

    print(
        "Answer keys are not used."
    )

    print(
        "Question text is not used."
    )

    print(
        "Deterministic career scores remain the source of truth."
    )

    print(
        "AI interpretation is used only as supporting context."
    )

    # ========================================================
    # TIE ANALYSIS
    # ========================================================

    career_lookup = build_career_lookup(
        assessment
    )

    career_scores = normalize_career_scores(
        deterministic_result,
        career_lookup
    )

    tie_info = analyze_career_tie(
        career_scores
    )

    print()
    print(
        "Career recommendation tie analysis:"
    )

    if tie_info.get(
        "complete_tie"
    ):

        print(
            "  COMPLETE TIE detected."
        )

        print(
            "  No single primary career will be selected."
        )

        print(
            "  All assessed careers will remain equally "
            "available for exploration."
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
            f"  Highest-score tie detected: {tied}"
        )

        print(
            "  No single primary career will be selected."
        )

    else:

        if career_scores:

            print(
                "  No highest-score tie detected."
            )

            print(
                "  A single primary career can be identified."
            )

    # ========================================================
    # GENERATE RECOMMENDATION
    # ========================================================

    print()
    print(
        "Generating local career recommendation..."
    )

    recommendation = generate_recommendation(
        assessment,
        deterministic_result,
        ai_result
    )

    print(
        "Career recommendation generated successfully."
    )

    # ========================================================
    # VALIDATE RECOMMENDATION
    # ========================================================

    print()
    print(
        "Validating recommendation output..."
    )

    validate_recommendation_output(
        recommendation
    )

    print(
        "Recommendation output structure validated."
    )

    # ========================================================
    # SAFETY CHECKS
    # ========================================================

    print()
    print(
        "Checking recommendation against deterministic "
        "constraints..."
    )

    enforce_recommendation_constraints(
        recommendation
    )

    print(
        "Recommendation passed deterministic safety checks."
    )

    # ========================================================
    # SAVE
    # ========================================================

    print()
    print(
        "Saving recommendation result..."
    )

    save_json(
        RECOMMENDATION_FILE,
        recommendation
    )

    print(
        "Recommendation result saved successfully."
    )

    # ========================================================
    # DISPLAY
    # ========================================================

    print_recommendation_result(
        recommendation
    )

    # ========================================================
    # COMPLETE
    # ========================================================

    print()
    print("=" * 70)

    print(
        "CAREER RECOMMENDATION COMPLETE"
    )

    print("=" * 70)

    print()
    print(
        f"Result saved to: "
        f"{RECOMMENDATION_FILE.name}"
    )

    return recommendation


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        run()

    except KeyboardInterrupt:

        print()
        print(
            "Career recommendation cancelled by user."
        )

        sys.exit(1)

    except Exception as exc:

        print()
        print("=" * 70)

        print(
            "MINERVA JOURNEY 1 CAREER RECOMMENDATION ERROR"
        )

        print("=" * 70)

        print(
            f"{type(exc).__name__}: {exc}"
        )

        sys.exit(1)