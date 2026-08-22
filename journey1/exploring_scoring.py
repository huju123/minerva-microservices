"""
============================================================
MINERVA CAREER DISCOVERY
JOURNEY 1 — EXPLORING
Assessment Evaluation & Scoring Engine
Version 4.0 FINAL
============================================================

PURPOSE
-------
This file evaluates ONLY Journey 1 — Exploring.

QUESTIONS
---------
Questions are loaded dynamically from:

    assessment.json

Path:

    assessment["questions"]["exploring"]

EXPECTED STRUCTURE
------------------
10 Exploring questions total.

2 questions for each career:

1. UI/UX Design
2. Software Development
3. Data & Analytics
4. AI & Machine Learning
5. Cybersecurity

SCORING
-------
Each correct answer = 1 point.

Each career:
    2 questions
    2 maximum points
    100% maximum

DIMENSIONS
----------
The assessment contains:

    primary_dimension
    secondary_dimension
    behavior_signals

PRIMARY / SECONDARY DIMENSIONS
------------------------------
These are treated as the actual behavioral capabilities.

A correctly answered question contributes:

    +1 to primary_dimension
    +1 to secondary_dimension

An incorrectly answered question contributes:

    +0

BEHAVIOR SIGNALS
----------------
behavior_signals are tracked separately as supporting
behavioral evidence.

A behavior signal receives credit when the question
containing that signal is answered correctly.

STRENGTHS
---------
Dimension percentage >= 60%

IMPROVEMENT AREAS
-----------------
Dimension percentage < 60%

OUTPUT
------
The final deterministic evaluation is saved to:

    exploring_result.json

The result contains:

1. Overall score
2. Career scores
3. Career ranking
4. Top career
5. Second career
6. Behavioral dimensions
7. Behavioral signals
8. Strengths
9. Improvement areas
10. Question-level results
11. Final message

IMPORTANT
---------
This engine does NOT hard-code questions.

All questions, correct answers, career metadata,
behavior signals and dimensions come from assessment.json.

This engine does NOT use AI/LLM scoring.

exploring_ai.py can later read:

    exploring_result.json

and generate the interpretation/recommendation layer.

============================================================
"""

import json
from pathlib import Path
from collections import defaultdict


# ============================================================
# CONFIGURATION
# ============================================================

ASSESSMENT_FILE = "assessment.json"
RESULT_FILE = "exploring_result.json"

SUPPORTED_CAREERS = {
    "ui_ux",
    "development",
    "data",
    "ai",
    "cyber",
}

VALID_OPTIONS = {
    "A",
    "B",
    "C",
    "D",
}

EXPECTED_TOTAL_QUESTIONS = 10
EXPECTED_QUESTIONS_PER_CAREER = 2
POINTS_PER_CORRECT_ANSWER = 1

STRENGTH_THRESHOLD = 60


# ============================================================
# CAREER ORDER
# ============================================================
#
# Used ONLY for deterministic tie-breaking.
#
# If two careers have the same percentage, the career
# appearing earlier in this list gets the higher rank.
# ============================================================

CAREER_ORDER = [
    "ui_ux",
    "development",
    "data",
    "ai",
    "cyber",
]


# ============================================================
# PERFORMANCE LEVELS
# ============================================================

def get_performance_level(percentage):
    """
    Convert percentage into a performance level.

    80-100  -> Strong
    60-79   -> Good
    40-59   -> Moderate
    0-39    -> Needs Development
    """

    if percentage >= 80:
        return "Strong"

    if percentage >= 60:
        return "Good"

    if percentage >= 40:
        return "Moderate"

    return "Needs Development"


# ============================================================
# LOAD ASSESSMENT
# ============================================================

def load_assessment(json_path):
    """
    Load assessment.json.

    Questions are NOT stored in this Python file.

    They are read dynamically from:

        assessment["questions"]["exploring"]
    """

    path = Path(json_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Assessment file not found: {path}"
        )

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            assessment = json.load(file)

    except json.JSONDecodeError as error:

        raise ValueError(
            f"Invalid JSON file: {error}"
        ) from error

    return assessment


# ============================================================
# SAVE RESULT
# ============================================================

def save_result(result, json_path):
    """
    Save final Journey 1 evaluation result.

    Output:
        exploring_result.json
    """

    path = Path(json_path)

    try:

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                result,
                file,
                indent=2,
                ensure_ascii=False
            )

    except OSError as error:

        raise OSError(
            f"Could not save result file: {path}. "
            f"Reason: {error}"
        ) from error

    return path


# ============================================================
# VALIDATE ASSESSMENT
# ============================================================

def validate_assessment(assessment):
    """
    Validate the complete Journey 1 assessment structure.
    """

    if not isinstance(assessment, dict):

        raise ValueError(
            "Assessment must be a JSON object."
        )

    # --------------------------------------------------------
    # Required top-level fields
    # --------------------------------------------------------

    required_fields = [
        "assessment_id",
        "title",
        "version",
        "careers",
        "modes",
        "questions",
    ]

    for field in required_fields:

        if field not in assessment:

            raise ValueError(
                "Assessment is missing required field: "
                f"'{field}'"
            )

    # --------------------------------------------------------
    # Version
    # --------------------------------------------------------

    if str(
        assessment["version"]
    ).strip() != "4.0":

        raise ValueError(
            "This Journey 1 scoring engine expects "
            "assessment version 4.0."
        )

    # --------------------------------------------------------
    # Modes
    # --------------------------------------------------------

    modes = assessment["modes"]

    if not isinstance(modes, (dict, list)):

        raise ValueError(
            "'modes' must be an object or list."
        )

    # If modes is a dictionary, ensure exploring exists.
    if isinstance(modes, dict):

        if "exploring" not in modes:

            raise ValueError(
                "'modes' must contain 'exploring'."
            )

    # If modes is a list, ensure exploring exists.
    elif isinstance(modes, list):

        mode_ids = set()

        for mode in modes:

            if isinstance(mode, str):

                mode_ids.add(
                    mode.strip().lower()
                )

            elif isinstance(mode, dict):

                if "id" in mode:

                    mode_ids.add(
                        str(
                            mode["id"]
                        ).strip().lower()
                    )

        if "exploring" not in mode_ids:

            raise ValueError(
                "'modes' must contain 'exploring'."
            )

    # --------------------------------------------------------
    # Careers
    # --------------------------------------------------------

    careers = assessment["careers"]

    if not isinstance(careers, list):

        raise ValueError(
            "'careers' must be a list."
        )

    career_ids = []
    career_names = {}

    for career in careers:

        if not isinstance(career, dict):

            raise ValueError(
                "Every career must be an object."
            )

        if "id" not in career:

            raise ValueError(
                "Every career must contain an 'id'."
            )

        if "name" not in career:

            raise ValueError(
                f"Career '{career['id']}' "
                "must contain a 'name'."
            )

        career_id = str(
            career["id"]
        ).strip()

        career_name = career["name"]

        if not career_id:

            raise ValueError(
                "Career ID cannot be empty."
            )

        if not isinstance(
            career_name,
            str
        ) or not career_name.strip():

            raise ValueError(
                f"Career '{career_id}' "
                "has an invalid name."
            )

        career_ids.append(
            career_id
        )

        career_names[
            career_id
        ] = career_name.strip()

    if len(career_ids) != len(
        set(career_ids)
    ):

        raise ValueError(
            "Duplicate career IDs found."
        )

    if set(career_ids) != SUPPORTED_CAREERS:

        raise ValueError(
            "Assessment must contain exactly these "
            f"careers: {sorted(SUPPORTED_CAREERS)}"
        )

    # --------------------------------------------------------
    # Questions container
    # --------------------------------------------------------

    questions = assessment["questions"]

    if not isinstance(
        questions,
        dict
    ):

        raise ValueError(
            "'questions' must be an object."
        )

    # --------------------------------------------------------
    # Exploring questions
    # --------------------------------------------------------

    if "exploring" not in questions:

        raise ValueError(
            "Assessment questions must contain "
            "'exploring' for Journey 1."
        )

    exploring_questions = questions[
        "exploring"
    ]

    if not isinstance(
        exploring_questions,
        list
    ):

        raise ValueError(
            "'questions.exploring' must be a list."
        )

    if len(
        exploring_questions
    ) != EXPECTED_TOTAL_QUESTIONS:

        raise ValueError(
            "Journey 1 must contain exactly "
            f"{EXPECTED_TOTAL_QUESTIONS} questions. "
            f"Found {len(exploring_questions)}."
        )

    # --------------------------------------------------------
    # Individual question validation
    # --------------------------------------------------------

    question_ids = set()

    career_counts = defaultdict(int)

    for question in exploring_questions:

        if not isinstance(
            question,
            dict
        ):

            raise ValueError(
                "Every exploring question must "
                "be an object."
            )

        required_question_fields = [
            "id",
            "title",
            "type",
            "interaction",
            "instruction",
            "options",
            "correct_option",
            "score",
            "career",
            "career_name",
            "behavior_signals",
            "primary_dimension",
            "secondary_dimension",
        ]

        for field in required_question_fields:

            if field not in question:

                raise ValueError(
                    f"Question "
                    f"'{question.get('id', 'UNKNOWN')}' "
                    f"is missing '{field}'."
                )

        # ----------------------------------------------------
        # Question ID
        # ----------------------------------------------------

        question_id = str(
            question["id"]
        ).strip()

        if not question_id:

            raise ValueError(
                "Question ID cannot be empty."
            )

        if question_id in question_ids:

            raise ValueError(
                f"Duplicate question ID: "
                f"'{question_id}'"
            )

        question_ids.add(
            question_id
        )

        # ----------------------------------------------------
        # Career
        # ----------------------------------------------------

        career = str(
            question["career"]
        ).strip()

        if career not in SUPPORTED_CAREERS:

            raise ValueError(
                f"Question '{question_id}' "
                f"has invalid career '{career}'."
            )

        career_counts[
            career
        ] += 1

        # ----------------------------------------------------
        # Career name
        # ----------------------------------------------------

        question_career_name = (
            question["career_name"]
        )

        if not isinstance(
            question_career_name,
            str
        ):

            raise ValueError(
                f"Question '{question_id}' "
                "'career_name' must be a string."
            )

        if not question_career_name.strip():

            raise ValueError(
                f"Question '{question_id}' "
                "'career_name' cannot be empty."
            )

        # ----------------------------------------------------
        # Correct option
        # ----------------------------------------------------

        correct_option = str(
            question["correct_option"]
        ).strip().upper()

        if correct_option not in VALID_OPTIONS:

            raise ValueError(
                f"Question '{question_id}' has invalid "
                f"correct_option '{correct_option}'."
            )

        # ----------------------------------------------------
        # Score
        # ----------------------------------------------------

        if question["score"] != POINTS_PER_CORRECT_ANSWER:

            raise ValueError(
                f"Question '{question_id}' must have "
                f"score = {POINTS_PER_CORRECT_ANSWER}."
            )

        # ----------------------------------------------------
        # Options
        # ----------------------------------------------------

        options = question["options"]

        if not isinstance(
            options,
            list
        ):

            raise ValueError(
                f"Question '{question_id}' "
                "'options' must be a list."
            )

        option_ids = set()

        for option in options:

            if not isinstance(
                option,
                dict
            ):

                raise ValueError(
                    f"Question '{question_id}' "
                    "contains an invalid option."
                )

            if (
                "id" not in option
                or "text" not in option
            ):

                raise ValueError(
                    f"Question '{question_id}' "
                    "options must contain id and text."
                )

            option_id = str(
                option["id"]
            ).strip().upper()

            if option_id in option_ids:

                raise ValueError(
                    f"Question '{question_id}' "
                    f"contains duplicate option "
                    f"'{option_id}'."
                )

            option_ids.add(
                option_id
            )

            if option_id not in VALID_OPTIONS:

                raise ValueError(
                    f"Question '{question_id}' has "
                    f"invalid option '{option_id}'."
                )

        if option_ids != VALID_OPTIONS:

            raise ValueError(
                f"Question '{question_id}' must contain "
                "A, B, C and D options."
            )

        # ----------------------------------------------------
        # Behavior signals
        # ----------------------------------------------------

        signals = question[
            "behavior_signals"
        ]

        if not isinstance(
            signals,
            list
        ):

            raise ValueError(
                f"Question '{question_id}' "
                "'behavior_signals' must be a list."
            )

        if not signals:

            raise ValueError(
                f"Question '{question_id}' "
                "must contain at least one "
                "behavior signal."
            )

        seen_signals = set()

        for signal in signals:

            if not isinstance(
                signal,
                str
            ):

                raise ValueError(
                    f"Question '{question_id}' "
                    "contains an invalid behavior signal."
                )

            signal = signal.strip()

            if not signal:

                raise ValueError(
                    f"Question '{question_id}' "
                    "contains an empty behavior signal."
                )

            if signal in seen_signals:

                raise ValueError(
                    f"Question '{question_id}' "
                    f"contains duplicate behavior signal "
                    f"'{signal}'."
                )

            seen_signals.add(
                signal
            )

        # ----------------------------------------------------
        # Primary dimension
        # ----------------------------------------------------

        primary_dimension = question[
            "primary_dimension"
        ]

        if (
            not isinstance(
                primary_dimension,
                str
            )
            or not primary_dimension.strip()
        ):

            raise ValueError(
                f"Question '{question_id}' "
                "'primary_dimension' must be a "
                "non-empty string."
            )

        # ----------------------------------------------------
        # Secondary dimension
        # ----------------------------------------------------

        secondary_dimension = question[
            "secondary_dimension"
        ]

        if (
            not isinstance(
                secondary_dimension,
                str
            )
            or not secondary_dimension.strip()
        ):

            raise ValueError(
                f"Question '{question_id}' "
                "'secondary_dimension' must be a "
                "non-empty string."
            )

    # --------------------------------------------------------
    # Exactly 2 questions per career
    # --------------------------------------------------------

    for career in SUPPORTED_CAREERS:

        count = career_counts[
            career
        ]

        if count != EXPECTED_QUESTIONS_PER_CAREER:

            raise ValueError(
                "Journey 1 must contain exactly "
                f"{EXPECTED_QUESTIONS_PER_CAREER} "
                f"questions for '{career}'. "
                f"Found {count}."
            )

    return True


# ============================================================
# GET CAREER NAME
# ============================================================

def get_career_name(
    assessment,
    career_id
):
    """
    Get career display name from assessment.json.
    """

    for career in assessment["careers"]:

        if career["id"] == career_id:

            return career["name"]

    return career_id


# ============================================================
# GET EXPLORING QUESTIONS
# ============================================================

def get_exploring_questions(
    assessment
):
    """
    Return Journey 1 questions directly from:

        assessment["questions"]["exploring"]

    No questions are hard-coded here.
    """

    if "questions" not in assessment:

        raise ValueError(
            "Assessment is missing 'questions'."
        )

    questions = assessment[
        "questions"
    ]

    if "exploring" not in questions:

        raise ValueError(
            "Assessment is missing "
            "'questions.exploring'."
        )

    exploring_questions = questions[
        "exploring"
    ]

    if not isinstance(
        exploring_questions,
        list
    ):

        raise ValueError(
            "'questions.exploring' must be a list."
        )

    if len(
        exploring_questions
    ) != EXPECTED_TOTAL_QUESTIONS:

        raise ValueError(
            "Journey 1 must contain exactly "
            f"{EXPECTED_TOTAL_QUESTIONS} questions."
        )

    return exploring_questions


# ============================================================
# VALIDATE USER ANSWERS
# ============================================================

def validate_answers(
    questions,
    answers
):
    """
    Validate submitted answers.

    Requirements:

    - answers must be a dictionary
    - exactly all 10 questions must be answered
    - no missing question IDs
    - no extra question IDs
    - every answer must be A/B/C/D
    """

    if not isinstance(
        answers,
        dict
    ):

        raise ValueError(
            "Answers must be provided as a dictionary."
        )

    expected_ids = {
        question["id"]
        for question in questions
    }

    submitted_ids = set(
        answers.keys()
    )

    # --------------------------------------------------------
    # Missing
    # --------------------------------------------------------

    missing = (
        expected_ids
        - submitted_ids
    )

    if missing:

        raise ValueError(
            "Missing answers for: "
            f"{sorted(missing)}"
        )

    # --------------------------------------------------------
    # Extra
    # --------------------------------------------------------

    extra = (
        submitted_ids
        - expected_ids
    )

    if extra:

        raise ValueError(
            "Unexpected question IDs: "
            f"{sorted(extra)}"
        )

    # --------------------------------------------------------
    # Answer values
    # --------------------------------------------------------

    for question_id, answer in answers.items():

        normalized = str(
            answer
        ).strip().upper()

        if normalized not in VALID_OPTIONS:

            raise ValueError(
                f"Invalid answer '{answer}' "
                f"for question '{question_id}'. "
                "Answer must be A, B, C or D."
            )


# ============================================================
# NORMALIZE ANSWERS
# ============================================================

def normalize_answers(answers):
    """
    Return a normalized copy of answers.

    Example:

        {"Q1": " a "}

    becomes:

        {"Q1": "A"}
    """

    return {
        question_id:
            str(answer).strip().upper()
        for question_id, answer
        in answers.items()
    }


# ============================================================
# CALCULATE CAREER SCORES
# ============================================================

def calculate_career_scores(
    questions,
    answers,
    assessment
):
    """
    Calculate score for all five careers.

    Each correct answer = 1 point.

    Maximum per career = 2 points.
    """

    stats = {}

    for career in CAREER_ORDER:

        stats[career] = {

            "career":
                career,

            "career_name":
                get_career_name(
                    assessment,
                    career
                ),

            "correct":
                0,

            "total":
                0,

            "max_score":
                0,
        }

    # --------------------------------------------------------
    # Score each question
    # --------------------------------------------------------

    for question in questions:

        question_id = question[
            "id"
        ]

        career = question[
            "career"
        ]

        stats[
            career
        ]["total"] += 1

        stats[
            career
        ]["max_score"] += (
            POINTS_PER_CORRECT_ANSWER
        )

        submitted = str(
            answers[
                question_id
            ]
        ).strip().upper()

        correct = str(
            question[
                "correct_option"
            ]
        ).strip().upper()

        if submitted == correct:

            stats[
                career
            ]["correct"] += (
                POINTS_PER_CORRECT_ANSWER
            )

    # --------------------------------------------------------
    # Convert to percentages
    # --------------------------------------------------------

    results = []

    for career in CAREER_ORDER:

        item = stats[
            career
        ]

        if item["max_score"]:

            percentage = round(
                (
                    item["correct"]
                    / item["max_score"]
                ) * 100,
                2
            )

        else:

            percentage = 0.0

        results.append({

            "career":
                item["career"],

            "career_name":
                item["career_name"],

            "score":
                item["correct"],

            "max_score":
                item["max_score"],

            "total_questions":
                item["total"],

            "percentage":
                percentage,

            "level":
                get_performance_level(
                    percentage
                ),
        })

    return results


# ============================================================
# RANK CAREERS
# ============================================================

def rank_careers(
    career_scores
):
    """
    Rank careers from highest to lowest.

    Primary criterion:
        percentage DESC

    Tie-breaker:
        CAREER_ORDER
    """

    order = {
        career: index
        for index, career
        in enumerate(
            CAREER_ORDER
        )
    }

    ranked = sorted(
        career_scores,
        key=lambda item: (
            -item["percentage"],
            order[item["career"]]
        )
    )

    for index, item in enumerate(
        ranked,
        start=1
    ):

        item["rank"] = index

    return ranked


# ============================================================
# QUESTION RESULTS
# ============================================================

def calculate_question_results(
    questions,
    answers,
    assessment
):
    """
    Produce detailed question-level scoring results.
    """

    results = []

    for question in questions:

        question_id = question[
            "id"
        ]

        submitted = str(
            answers[
                question_id
            ]
        ).strip().upper()

        correct = str(
            question[
                "correct_option"
            ]
        ).strip().upper()

        is_correct = (
            submitted == correct
        )

        results.append({

            "question_id":
                question_id,

            "career":
                question["career"],

            "career_name":
                get_career_name(
                    assessment,
                    question["career"]
                ),

            "selected_option":
                submitted,

            "correct_option":
                correct,

            "is_correct":
                is_correct,

            "score":
                POINTS_PER_CORRECT_ANSWER
                if is_correct
                else 0,

            "primary_dimension":
                question[
                    "primary_dimension"
                ],

            "secondary_dimension":
                question[
                    "secondary_dimension"
                ],

            "behavior_signals":
                question[
                    "behavior_signals"
                ],
        })

    return results


# ============================================================
# CALCULATE ACTUAL BEHAVIORAL DIMENSIONS
# ============================================================

def calculate_dimensions(
    questions,
    answers
):
    """
    Calculate actual behavioral dimensions.

    The actual dimensions come from:

        primary_dimension
        secondary_dimension

    Each question contributes to BOTH dimensions.

    If the question is correct:

        primary_dimension   +1
        secondary_dimension +1

    If incorrect:

        primary_dimension   +0
        secondary_dimension +0

    This keeps dimensions separate from behavior_signals.
    """

    dimension_stats = defaultdict(
        lambda: {
            "correct": 0,
            "total": 0,
        }
    )

    for question in questions:

        question_id = question[
            "id"
        ]

        submitted = str(
            answers[
                question_id
            ]
        ).strip().upper()

        correct = str(
            question[
                "correct_option"
            ]
        ).strip().upper()

        is_correct = (
            submitted == correct
        )

        dimensions_for_question = [
            question[
                "primary_dimension"
            ].strip(),

            question[
                "secondary_dimension"
            ].strip(),
        ]

        # Avoid double counting if primary and secondary
        # dimensions happen to be identical.
        dimensions_for_question = list(
            dict.fromkeys(
                dimensions_for_question
            )
        )

        for dimension in (
            dimensions_for_question
        ):

            dimension_stats[
                dimension
            ]["total"] += 1

            if is_correct:

                dimension_stats[
                    dimension
                ]["correct"] += 1

    dimensions = []

    for dimension, stats in (
        dimension_stats.items()
    ):

        total = stats[
            "total"
        ]

        correct = stats[
            "correct"
        ]

        percentage = round(
            (
                correct
                / total
            ) * 100,
            2
        ) if total else 0.0

        dimensions.append({

            "dimension":
                dimension,

            "correct":
                correct,

            "total":
                total,

            "percentage":
                percentage,

            "level":
                get_performance_level(
                    percentage
                ),
        })

    dimensions.sort(
        key=lambda item: (
            -item["percentage"],
            item["dimension"]
        )
    )

    return dimensions


# ============================================================
# CALCULATE BEHAVIOR SIGNALS
# ============================================================

def calculate_behavior_signals(
    questions,
    answers
):
    """
    Calculate supporting behavioral signals.

    behavior_signals come directly from assessment.json.

    A signal receives credit when the question containing
    that signal is answered correctly.
    """

    signal_stats = defaultdict(
        lambda: {
            "correct": 0,
            "total": 0,
        }
    )

    for question in questions:

        question_id = question[
            "id"
        ]

        submitted = str(
            answers[
                question_id
            ]
        ).strip().upper()

        correct = str(
            question[
                "correct_option"
            ]
        ).strip().upper()

        is_correct = (
            submitted == correct
        )

        unique_signals = list(
            dict.fromkeys(
                question[
                    "behavior_signals"
                ]
            )
        )

        for signal in unique_signals:

            signal_stats[
                signal
            ]["total"] += 1

            if is_correct:

                signal_stats[
                    signal
                ]["correct"] += 1

    signals = []

    for signal, stats in (
        signal_stats.items()
    ):

        total = stats[
            "total"
        ]

        correct = stats[
            "correct"
        ]

        percentage = round(
            (
                correct
                / total
            ) * 100,
            2
        ) if total else 0.0

        signals.append({

            "signal":
                signal,

            "correct":
                correct,

            "total":
                total,

            "percentage":
                percentage,

            "level":
                get_performance_level(
                    percentage
                ),
        })

    signals.sort(
        key=lambda item: (
            -item["percentage"],
            item["signal"]
        )
    )

    return signals


# ============================================================
# STRENGTHS
# ============================================================

def calculate_strengths(
    dimensions
):
    """
    Identify strong behavioral dimensions.

    Strength threshold:

        >= 60%
    """

    strengths = []

    for dimension in dimensions:

        if (
            dimension["percentage"]
            >= STRENGTH_THRESHOLD
        ):

            strengths.append({

                "dimension":
                    dimension["dimension"],

                "percentage":
                    dimension["percentage"],

                "level":
                    dimension["level"],
            })

    return strengths


# ============================================================
# IMPROVEMENT AREAS
# ============================================================

def calculate_improvement_areas(
    dimensions,
    question_results
):
    """
    Identify:

    1. Weak dimensions
    2. Incorrect questions
    """

    weak_dimensions = []

    for dimension in dimensions:

        if (
            dimension["percentage"]
            < STRENGTH_THRESHOLD
        ):

            weak_dimensions.append({

                "dimension":
                    dimension["dimension"],

                "percentage":
                    dimension["percentage"],

                "level":
                    dimension["level"],
            })

    incorrect_questions = []

    for result in question_results:

        if not result[
            "is_correct"
        ]:

            incorrect_questions.append({

                "question_id":
                    result[
                        "question_id"
                    ],

                "career":
                    result[
                        "career"
                    ],

                "career_name":
                    result[
                        "career_name"
                    ],

                "primary_dimension":
                    result[
                        "primary_dimension"
                    ],

                "secondary_dimension":
                    result[
                        "secondary_dimension"
                    ],

                "behavior_signals":
                    result[
                        "behavior_signals"
                    ],
            })

    return {

        "dimensions":
            weak_dimensions,

        "questions":
            incorrect_questions,
    }


# ============================================================
# OVERALL SCORE
# ============================================================

def calculate_overall_score(
    question_results
):
    """
    Calculate overall Journey 1 score.
    """

    total = len(
        question_results
    )

    correct = sum(
        1
        for result in question_results
        if result[
            "is_correct"
        ]
    )

    percentage = round(
        (
            correct
            / total
        ) * 100,
        2
    ) if total else 0.0

    return {

        "correct":
            correct,

        "total":
            total,

        "percentage":
            percentage,

        "level":
            get_performance_level(
                percentage
            ),
    }


# ============================================================
# BUILD FINAL MESSAGE
# ============================================================

def build_final_message(
    top_career,
    second_career
):
    """
    Build deterministic final message.
    """

    if (
        top_career
        and second_career
    ):

        if (
            top_career["percentage"]
            == second_career["percentage"]
        ):

            return (
                f"Your strongest career match is "
                f"{top_career['career_name']} "
                f"with a score of "
                f"{top_career['percentage']}%. "
                f"Your second strongest match is "
                f"{second_career['career_name']} "
                f"with a score of "
                f"{second_career['percentage']}%. "
                f"The careers are tied, so the "
                f"deterministic career order was used "
                f"as the tie-breaker."
            )

        return (
            f"Your strongest career match is "
            f"{top_career['career_name']} "
            f"with a score of "
            f"{top_career['percentage']}%. "
            f"Your second strongest match is "
            f"{second_career['career_name']} "
            f"with a score of "
            f"{second_career['percentage']}%."
        )

    if top_career:

        return (
            f"Your strongest career match is "
            f"{top_career['career_name']} "
            f"with a score of "
            f"{top_career['percentage']}%."
        )

    return (
        "No career match could be determined."
    )


# ============================================================
# BUILD FINAL RESULT
# ============================================================

def evaluate_journey_1(
    assessment,
    answers
):
    """
    Main Journey 1 evaluation function.

    INPUT
    -----
    assessment:
        Loaded assessment.json object.

    answers:
        Dictionary containing the user's answers.

    OUTPUT
    ------
    Complete deterministic Exploring result.

    IMPORTANT
    ---------
    This function does NOT automatically save the result.

    Saving is handled by save_result().

    This makes the function reusable by a backend/API.
    """

    # --------------------------------------------------------
    # Validate assessment
    # --------------------------------------------------------

    validate_assessment(
        assessment
    )

    # --------------------------------------------------------
    # Get questions from assessment.json
    # --------------------------------------------------------

    questions = get_exploring_questions(
        assessment
    )

    # --------------------------------------------------------
    # Validate answers
    # --------------------------------------------------------

    validate_answers(
        questions,
        answers
    )

    # --------------------------------------------------------
    # Normalize answers
    # --------------------------------------------------------

    answers = normalize_answers(
        answers
    )

    # --------------------------------------------------------
    # Question-level scoring
    # --------------------------------------------------------

    question_results = (
        calculate_question_results(
            questions,
            answers,
            assessment
        )
    )

    # --------------------------------------------------------
    # Overall score
    # --------------------------------------------------------

    overall = calculate_overall_score(
        question_results
    )

    # --------------------------------------------------------
    # Career scores
    # --------------------------------------------------------

    career_scores = (
        calculate_career_scores(
            questions,
            answers,
            assessment
        )
    )

    # --------------------------------------------------------
    # Career ranking
    # --------------------------------------------------------

    ranked_careers = rank_careers(
        career_scores
    )

    # --------------------------------------------------------
    # Top career
    # --------------------------------------------------------

    top_career = (
        ranked_careers[0]
        if ranked_careers
        else None
    )

    # --------------------------------------------------------
    # Second career
    # --------------------------------------------------------

    second_career = (
        ranked_careers[1]
        if len(
            ranked_careers
        ) > 1
        else None
    )

    # --------------------------------------------------------
    # Actual behavioral dimensions
    # --------------------------------------------------------

    dimensions = calculate_dimensions(
        questions,
        answers
    )

    # --------------------------------------------------------
    # Supporting behavior signals
    # --------------------------------------------------------

    behavior_signals = (
        calculate_behavior_signals(
            questions,
            answers
        )
    )

    # --------------------------------------------------------
    # Strengths
    # --------------------------------------------------------

    strengths = calculate_strengths(
        dimensions
    )

    # --------------------------------------------------------
    # Improvement areas
    # --------------------------------------------------------

    improvement_areas = (
        calculate_improvement_areas(
            dimensions,
            question_results
        )
    )

    # --------------------------------------------------------
    # Final message
    # --------------------------------------------------------

    message = build_final_message(
        top_career,
        second_career
    )

    # --------------------------------------------------------
    # FINAL RESULT
    # --------------------------------------------------------

    return {

        "assessment_id":
            assessment[
                "assessment_id"
            ],

        "assessment_version":
            assessment[
                "version"
            ],

        "journey":
            1,

        "mode":
            "exploring",

        "total_questions":
            overall[
                "total"
            ],

        # Canonical fields consumed by exploring_ai.py
        "answered_questions":
            overall[
                "total"
            ],

        "total_correct":
            overall[
                "correct"
            ],

        # Backward-compatible field retained for existing consumers
        "correct_answers":
            overall[
                "correct"
            ],

        "overall_percentage":
            overall[
                "percentage"
            ],

        "overall_level":
            overall[
                "level"
            ],

        "career_scores":
            career_scores,

        "ranked_careers":
            ranked_careers,

        "top_career":
            top_career,

        "second_career":
            second_career,

        "dimensions":
            dimensions,

        "behavior_signals":
            behavior_signals,

        "strengths":
            strengths,

        "improvement_areas":
            improvement_areas,

        "question_results":
            question_results,

        "message":
            message,
    }


# ============================================================
# EVALUATE AND SAVE
# ============================================================

def evaluate_and_save_journey_1(
    assessment,
    answers,
    result_path
):
    """
    Convenience function for backend/local usage.

    Evaluates Journey 1 and immediately saves the result.

    Returns:

        result
        saved_path
    """

    result = evaluate_journey_1(
        assessment,
        answers
    )

    saved_path = save_result(
        result,
        result_path
    )

    return result, saved_path


# ============================================================
# TEST HELPER — ALL CORRECT
# ============================================================

def generate_all_correct_answers(
    questions
):
    """
    Generate answers where every question is answered
    correctly.

    Correct answers are read from assessment.json.

    Nothing is hard-coded.
    """

    return {

        question["id"]:
            str(
                question[
                    "correct_option"
                ]
            ).strip().upper()

        for question in questions
    }


# ============================================================
# TEST HELPER — ALL WRONG
# ============================================================

def generate_all_wrong_answers(
    questions
):
    """
    Generate intentionally incorrect answers.

    Correct answers come from assessment.json.
    """

    answers = {}

    for question in questions:

        correct = str(
            question[
                "correct_option"
            ]
        ).strip().upper()

        wrong_option = next(
            option
            for option in VALID_OPTIONS
            if option != correct
        )

        answers[
            question["id"]
        ] = wrong_option

    return answers


# ============================================================
# TEST HELPER — MIXED
# ============================================================

def generate_mixed_answers(
    questions
):
    """
    Generate deterministic 5 correct / 5 wrong
    answer set.

    First 5:
        correct

    Last 5:
        wrong
    """

    answers = {}

    for index, question in enumerate(
        questions
    ):

        correct = str(
            question[
                "correct_option"
            ]
        ).strip().upper()

        if index < 5:

            answers[
                question["id"]
            ] = correct

        else:

            wrong_option = next(
                option
                for option in VALID_OPTIONS
                if option != correct
            )

            answers[
                question["id"]
            ] = wrong_option

    return answers


# ============================================================
# PRINT RESULT
# ============================================================

def print_result(
    result
):
    """
    Print readable Journey 1 result.
    """

    print("\n")
    print("=" * 70)
    print(
        "MINERVA — JOURNEY 1: EXPLORING"
    )
    print("=" * 70)

    # --------------------------------------------------------
    # Overall
    # --------------------------------------------------------

    print("\nOVERALL RESULT")
    print("-" * 70)

    print(
        f"Score: "
        f"{result['correct_answers']}/"
        f"{result['total_questions']}"
    )

    print(
        f"Percentage: "
        f"{result['overall_percentage']}%"
    )

    print(
        f"Level: "
        f"{result['overall_level']}"
    )

    # --------------------------------------------------------
    # Career ranking
    # --------------------------------------------------------

    print("\nCAREER RANKING")
    print("-" * 70)

    for career in result[
        "ranked_careers"
    ]:

        print(
            f"{career['rank']}. "
            f"{career['career_name']} "
            f"-> "
            f"{career['score']}/"
            f"{career['max_score']} "
            f"({career['percentage']}%) "
            f"[{career['level']}]"
        )

    # --------------------------------------------------------
    # Top career
    # --------------------------------------------------------

    print("\nTOP CAREER")
    print("-" * 70)

    top = result[
        "top_career"
    ]

    if top:

        print(
            f"{top['career_name']} "
            f"-> "
            f"{top['percentage']}%"
        )

    else:

        print("None")

    # --------------------------------------------------------
    # Second career
    # --------------------------------------------------------

    print("\nSECOND CAREER")
    print("-" * 70)

    second = result[
        "second_career"
    ]

    if second:

        print(
            f"{second['career_name']} "
            f"-> "
            f"{second['percentage']}%"
        )

    else:

        print("None")

    # --------------------------------------------------------
    # Actual dimensions
    # --------------------------------------------------------

    print(
        "\nBEHAVIORAL DIMENSIONS / CAPABILITIES"
    )

    print("-" * 70)

    for dimension in result[
        "dimensions"
    ]:

        print(
            f"- {dimension['dimension']} "
            f"-> "
            f"{dimension['percentage']}% "
            f"({dimension['level']})"
        )

    # --------------------------------------------------------
    # Behavior signals
    # --------------------------------------------------------

    print(
        "\nBEHAVIOR SIGNALS"
    )

    print("-" * 70)

    for signal in result[
        "behavior_signals"
    ]:

        print(
            f"- {signal['signal']} "
            f"-> "
            f"{signal['percentage']}% "
            f"({signal['level']})"
        )

    # --------------------------------------------------------
    # Strengths
    # --------------------------------------------------------

    print("\nSTRENGTHS")
    print("-" * 70)

    if result[
        "strengths"
    ]:

        for strength in result[
            "strengths"
        ]:

            print(
                f"- {strength['dimension']} "
                f"-> "
                f"{strength['percentage']}% "
                f"({strength['level']})"
            )

    else:

        print(
            "- No strong dimensions yet."
        )

    # --------------------------------------------------------
    # Improvement areas
    # --------------------------------------------------------

    print(
        "\nIMPROVEMENT AREAS"
    )

    print("-" * 70)

    improvement = result[
        "improvement_areas"
    ]

    # --------------------------------------------------------
    # Weak dimensions
    # --------------------------------------------------------

    if improvement[
        "dimensions"
    ]:

        print(
            "Weak dimensions:"
        )

        for item in improvement[
            "dimensions"
        ]:

            print(
                f"- {item['dimension']} "
                f"-> "
                f"{item['percentage']}% "
                f"({item['level']})"
            )

    else:

        print(
            "Weak dimensions: None"
        )

    # --------------------------------------------------------
    # Incorrect questions
    # --------------------------------------------------------

    if improvement[
        "questions"
    ]:

        print(
            "\nIncorrect questions:"
        )

        for item in improvement[
            "questions"
        ]:

            print(
                f"- {item['question_id']} "
                f"({item['career_name']})"
            )

    else:

        print(
            "Incorrect questions: None"
        )

    # --------------------------------------------------------
    # Final message
    # --------------------------------------------------------

    print("\nMESSAGE")
    print("-" * 70)

    print(
        result[
            "message"
        ]
    )

    print("=" * 70)


# ============================================================
# AUTOMATED TEST SUITE
# ============================================================

def run_tests(
    assessment
):
    """
    Automated tests for Journey 1.

    Tests:

    1. Assessment validation
    2. Question structure
    3. All correct
    4. All wrong
    5. Mixed
    6. Invalid answer
    7. Missing answer
    8. Extra answer
    9. Invalid question ID
    10. Result structure
    11. Career ranking
    12. Dimension calculation
    13. Behavior signal calculation
    """

    print("\n")
    print("=" * 70)
    print(
        "MINERVA JOURNEY 1 — "
        "AUTOMATED TEST SUITE"
    )
    print("=" * 70)

    # ========================================================
    # TEST 1 — Assessment validation
    # ========================================================

    print(
        "\n[TEST 1] Assessment validation"
    )

    validate_assessment(
        assessment
    )

    print(
        "PASS - assessment structure is valid"
    )

    # ========================================================
    # TEST 2 — Question structure
    # ========================================================

    print(
        "\n[TEST 2] Exploring question structure"
    )

    questions = get_exploring_questions(
        assessment
    )

    assert len(
        questions
    ) == EXPECTED_TOTAL_QUESTIONS

    career_counts = defaultdict(int)

    for question in questions:

        career_counts[
            question["career"]
        ] += 1

    for career in CAREER_ORDER:

        assert (
            career_counts[career]
            == EXPECTED_QUESTIONS_PER_CAREER
        )

    print(
        "PASS - 10 questions, "
        "2 questions per career"
    )

    # ========================================================
    # TEST 3 — All correct
    # ========================================================

    print(
        "\n[TEST 3] All correct answers"
    )

    answers = generate_all_correct_answers(
        questions
    )

    result = evaluate_journey_1(
        assessment,
        answers
    )

    assert (
        result[
            "total_questions"
        ] == 10
    )

    assert (
        result[
            "answered_questions"
        ] == 10
    )

    assert (
        result[
            "total_correct"
        ] == 10
    )

    assert (
        result[
            "correct_answers"
        ] == 10
    )

    assert (
        result[
            "overall_percentage"
        ] == 100.0
    )

    for career in result[
        "career_scores"
    ]:

        assert (
            career["score"]
            == 2
        )

        assert (
            career["percentage"]
            == 100.0
        )

    for dimension in result[
        "dimensions"
    ]:

        assert (
            dimension["percentage"]
            == 100.0
        )

    for signal in result[
        "behavior_signals"
    ]:

        assert (
            signal["percentage"]
            == 100.0
        )

    print(
        "PASS - 10/10 = 100%"
    )

    # ========================================================
    # TEST 4 — All wrong
    # ========================================================

    print(
        "\n[TEST 4] All wrong answers"
    )

    answers = generate_all_wrong_answers(
        questions
    )

    result = evaluate_journey_1(
        assessment,
        answers
    )

    assert (
        result[
            "correct_answers"
        ] == 0
    )

    assert (
        result[
            "overall_percentage"
        ] == 0.0
    )

    for career in result[
        "career_scores"
    ]:

        assert (
            career["score"]
            == 0
        )

        assert (
            career["percentage"]
            == 0.0
        )

    for dimension in result[
        "dimensions"
    ]:

        assert (
            dimension["percentage"]
            == 0.0
        )

    for signal in result[
        "behavior_signals"
    ]:

        assert (
            signal["percentage"]
            == 0.0
        )

    print(
        "PASS - 0/10 = 0%"
    )

    # ========================================================
    # TEST 5 — Mixed answers
    # ========================================================

    print(
        "\n[TEST 5] Mixed answers"
    )

    answers = generate_mixed_answers(
        questions
    )

    result = evaluate_journey_1(
        assessment,
        answers
    )

    assert (
        result[
            "correct_answers"
        ] == 5
    )

    assert (
        result[
            "overall_percentage"
        ] == 50.0
    )

    print(
        "PASS - 5/10 = 50%"
    )

    # ========================================================
    # TEST 6 — Invalid answer
    # ========================================================

    print(
        "\n[TEST 6] Invalid answer"
    )

    answers = generate_all_correct_answers(
        questions
    )

    first_id = questions[
        0
    ]["id"]

    answers[
        first_id
    ] = "X"

    try:

        evaluate_journey_1(
            assessment,
            answers
        )

        raise AssertionError(
            "Invalid answer was accepted."
        )

    except ValueError:

        print(
            "PASS - invalid answer rejected"
        )

    # ========================================================
    # TEST 7 — Missing answer
    # ========================================================

    print(
        "\n[TEST 7] Missing answer"
    )

    answers = generate_all_correct_answers(
        questions
    )

    del answers[
        questions[0]["id"]
    ]

    try:

        evaluate_journey_1(
            assessment,
            answers
        )

        raise AssertionError(
            "Missing answer was accepted."
        )

    except ValueError:

        print(
            "PASS - missing answer rejected"
        )

    # ========================================================
    # TEST 8 — Extra answer
    # ========================================================

    print(
        "\n[TEST 8] Extra answer"
    )

    answers = generate_all_correct_answers(
        questions
    )

    answers[
        "UNKNOWN_QUESTION"
    ] = "A"

    try:

        evaluate_journey_1(
            assessment,
            answers
        )

        raise AssertionError(
            "Extra answer was accepted."
        )

    except ValueError:

        print(
            "PASS - extra answer rejected"
        )

    # ========================================================
    # TEST 9 — Invalid question ID
    # ========================================================

    print(
        "\n[TEST 9] Invalid question ID"
    )

    answers = generate_all_correct_answers(
        questions
    )

    answers[
        "INVALID_ID"
    ] = "A"

    try:

        evaluate_journey_1(
            assessment,
            answers
        )

        raise AssertionError(
            "Invalid question ID was accepted."
        )

    except ValueError:

        print(
            "PASS - invalid question ID rejected"
        )

    # ========================================================
    # TEST 10 — Result structure
    # ========================================================

    print(
        "\n[TEST 10] Result structure"
    )

    answers = generate_all_correct_answers(
        questions
    )

    result = evaluate_journey_1(
        assessment,
        answers
    )

    required_result_fields = [

        "assessment_id",

        "assessment_version",

        "journey",

        "mode",

        "total_questions",
        "answered_questions",
        "total_correct",
        "correct_answers",
        "overall_percentage",

        "overall_level",

        "career_scores",

        "ranked_careers",

        "top_career",

        "second_career",

        "dimensions",

        "behavior_signals",

        "strengths",

        "improvement_areas",

        "question_results",

        "message",
    ]

    for field in required_result_fields:

        assert field in result, (
            f"Missing result field: {field}"
        )

    assert (
        len(
            result[
                "career_scores"
            ]
        ) == 5
    )

    assert (
        len(
            result[
                "ranked_careers"
            ]
        ) == 5
    )

    assert (
        len(
            result[
                "question_results"
            ]
        ) == 10
    )

    assert (
        result["answered_questions"]
        == result["total_questions"]
    )

    assert (
        result["total_correct"]
        == result["correct_answers"]
    )


    print(
        "PASS - complete result structure exists"
    )

    # ========================================================
    # TEST 11 — Career ranking
    # ========================================================

    print(
        "\n[TEST 11] Career ranking"
    )

    ranked = result[
        "ranked_careers"
    ]

    assert len(
        ranked
    ) == 5

    for index, career in enumerate(
        ranked,
        start=1
    ):

        assert (
            career["rank"]
            == index
        )

    percentages = [
        career[
            "percentage"
        ]
        for career in ranked
    ]

    assert percentages == sorted(
        percentages,
        reverse=True
    )

    assert (
        result[
            "top_career"
        ] == ranked[0]
    )

    assert (
        result[
            "second_career"
        ] == ranked[1]
    )

    print(
        "PASS - ranking and top/second careers valid"
    )

    # ========================================================
    # TEST 12 — Dimensions
    # ========================================================

    print(
        "\n[TEST 12] Behavioral dimensions"
    )

    assert isinstance(
        result["dimensions"],
        list
    )

    assert len(
        result["dimensions"]
    ) > 0

    for dimension in result[
        "dimensions"
    ]:

        assert (
            "dimension"
            in dimension
        )

        assert (
            "correct"
            in dimension
        )

        assert (
            "total"
            in dimension
        )

        assert (
            "percentage"
            in dimension
        )

        assert (
            "level"
            in dimension
        )

    print(
        "PASS - behavioral dimensions calculated"
    )

    # ========================================================
    # TEST 13 — Behavior signals
    # ========================================================

    print(
        "\n[TEST 13] Behavior signals"
    )

    assert isinstance(
        result[
            "behavior_signals"
        ],
        list
    )

    assert len(
        result[
            "behavior_signals"
        ]
    ) > 0

    for signal in result[
        "behavior_signals"
    ]:

        assert (
            "signal"
            in signal
        )

        assert (
            "correct"
            in signal
        )

        assert (
            "total"
            in signal
        )

        assert (
            "percentage"
            in signal
        )

        assert (
            "level"
            in signal
        )

    print(
        "PASS - behavior signals calculated"
    )

    # ========================================================
    # FINAL
    # ========================================================

    print("\n" + "=" * 70)

    print(
        "ALL JOURNEY 1 TESTS PASSED"
    )

    print("=" * 70)


# ============================================================
# LOCAL EXECUTION
# ============================================================

if __name__ == "__main__":

    # --------------------------------------------------------
    # Locate files relative to this Python file
    # --------------------------------------------------------

    current_dir = Path(
        __file__
    ).resolve().parent

    assessment_path = (
        current_dir
        / ASSESSMENT_FILE
    )

    result_path = (
        current_dir
        / RESULT_FILE
    )

    print("\n")
    print("=" * 70)

    print(
        "MINERVA — JOURNEY 1 "
        "EXPLORING SCORING ENGINE"
    )

    print("=" * 70)

    try:

        # ====================================================
        # LOAD ASSESSMENT
        # ====================================================

        print(
            "\nLoading assessment..."
        )

        assessment = load_assessment(
            assessment_path
        )

        print(
            "Assessment loaded successfully."
        )

        print(
            f"Assessment ID: "
            f"{assessment['assessment_id']}"
        )

        print(
            f"Version: "
            f"{assessment['version']}"
        )

        print(
            "Journey 1 Questions: "
            f"{len(assessment['questions']['exploring'])}"
        )

        # ====================================================
        # VALIDATE ASSESSMENT
        # ====================================================

        validate_assessment(
            assessment
        )

        print(
            "Assessment structure validated."
        )

        # ====================================================
        # RUN AUTOMATED TESTS
        # ====================================================

        run_tests(
            assessment
        )

        # ====================================================
        # DEMO EVALUATION
        # ====================================================
        #
        # This is ONLY for local testing.
        #
        # It generates all-correct answers automatically
        # from assessment.json.
        #
        # In production:
        #
        #     frontend
        #          ↓
        #     backend/API
        #          ↓
        #     evaluate_journey_1()
        #
        # The real user's answers should be passed there.
        # ====================================================

        print(
            "\nRunning demo evaluation..."
        )

        questions = get_exploring_questions(
            assessment
        )

        demo_answers = (
            generate_all_correct_answers(
                questions
            )
        )

        result, saved_path = (
            evaluate_and_save_journey_1(
                assessment,
                demo_answers,
                result_path
            )
        )

        # ====================================================
        # PRINT RESULT
        # ====================================================

        print_result(
            result
        )

        # ====================================================
        # RESULT FILE INFORMATION
        # ====================================================

        print("\n")
        print("=" * 70)

        print(
            "RESULT FILE"
        )

        print("=" * 70)

        print(
            "Saved successfully to:"
        )

        print(
            saved_path
        )

        print(
            "\nThis file can now be read by:"
        )

        print(
            "exploring_ai.py"
        )

        print("=" * 70)

        # ====================================================
        # PRINT RAW JSON
        # ====================================================

        print("\n")
        print("=" * 70)

        print(
            "FINAL RESULT JSON"
        )

        print("=" * 70)

        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False
            )
        )

        print("\n")

        print(
            "Journey 1 evaluation "
            "completed successfully."
        )

        print(
            f"Result saved as: "
            f"{RESULT_FILE}"
        )

        print("=" * 70)

    except Exception as error:

        print("\n")
        print("=" * 70)

        print(
            "MINERVA JOURNEY 1 ERROR"
        )

        print("=" * 70)

        print(
            f"{type(error).__name__}: {error}"
        )

        print("=" * 70)

        raise