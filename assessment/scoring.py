import json
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
QUESTIONS_FILE = BASE_DIR / "data" / "assessment_questions.json"


# ============================================================
# 3.1 — LOAD QUESTIONS
# ============================================================

def load_questions():
    """
    Load standardized assessment questions from JSON file.

    Returns:
        List of assessment questions.
    """

    with open(QUESTIONS_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    return data["questions"]


# ============================================================
# 3.2 — SCORE INDIVIDUAL QUESTIONS
# ============================================================

def score_question(question, student_answer):
    """
    Score one individual question.

    Parameters:
        question: Question dictionary from assessment JSON.
        student_answer: Student's selected option ID (A/B/C/D).

    Returns:
        Dictionary containing question-level scoring result.
    """

    correct_answer = question["correct_answer"]

    # Normalize answer
    student_answer = student_answer.strip().upper()

    # Check answer
    is_correct = student_answer == correct_answer

    # Assign score
    earned_score = question.get("score", 1) if is_correct else 0

    return {
        "question_id": question["question_id"],
        "category": question["category"],
        "difficulty": question["difficulty"],
        "student_answer": student_answer,
        "correct_answer": correct_answer,
        "is_correct": is_correct,
        "score": earned_score,
        "max_score": question.get("score", 1)
    }


def score_assessment(student_answers):
    """
    Score all assessment questions.

    Parameters:
        student_answers:
            Dictionary containing question_id and selected answer.

        Example:
            {
                "PS-01": "A",
                "PS-02": "B",
                "PS-03": "B"
            }

    Returns:
        List of individual question scoring results.
    """

    questions = load_questions()

    results = []

    for question in questions:

        question_id = question["question_id"]

        # Get student's answer
        student_answer = student_answers.get(question_id)

        # If student did not answer the question
        if student_answer is None:

            result = {
                "question_id": question_id,
                "category": question["category"],
                "difficulty": question["difficulty"],
                "student_answer": None,
                "correct_answer": question["correct_answer"],
                "is_correct": False,
                "score": 0,
                "max_score": question.get("score", 1)
            }

        else:

            result = score_question(
                question,
                student_answer
            )

        results.append(result)

    return results


# ============================================================
# 3.3 — CATEGORY-WISE SCORES
# ============================================================

def calculate_category_scores(results):
    """
    Calculate scores for each assessment category.

    Parameters:
        results: List of individual question scoring results.

    Returns:
        Dictionary containing category-wise scores.
    """

    category_scores = {}

    for result in results:

        category = result["category"]

        # Create category if it doesn't exist
        if category not in category_scores:

            category_scores[category] = {
                "score": 0,
                "max_score": 0,
                "questions": 0,
                "correct": 0,
                "incorrect": 0
            }

        # Add score
        category_scores[category]["score"] += result["score"]

        # Add maximum possible score
        category_scores[category]["max_score"] += result["max_score"]

        # Count question
        category_scores[category]["questions"] += 1

        # Count correct / incorrect
        if result["is_correct"]:
            category_scores[category]["correct"] += 1
        else:
            category_scores[category]["incorrect"] += 1

    # Calculate percentages
    for category in category_scores:

        score = category_scores[category]["score"]
        max_score = category_scores[category]["max_score"]

        if max_score > 0:
            percentage = (score / max_score) * 100
        else:
            percentage = 0

        category_scores[category]["percentage"] = round(
            percentage,
            2
        )

    return category_scores


# ============================================================
# 3.4 — OVERALL SCORE
# ============================================================

def calculate_overall_score(results):
    """
    Calculate the overall assessment score.

    Parameters:
        results: List of individual question scoring results.

    Returns:
        Dictionary containing overall score information.
    """

    total_score = 0
    max_score = 0

    for result in results:

        total_score += result["score"]
        max_score += result["max_score"]

    if max_score > 0:
        percentage = (total_score / max_score) * 100
    else:
        percentage = 0

    return {
        "score": total_score,
        "max_score": max_score,
        "percentage": round(percentage, 2)
    }


# ============================================================
# 3.5 — SCORE CLASSIFICATION
# ============================================================

def classify_score(percentage):
    """
    Classify the student's overall performance.

    Classification:
        >= 90% → Excellent
        >= 75% → Strong
        >= 60% → Moderate
        >= 40% → Developing
        < 40%  → Needs Improvement

    Parameters:
        percentage: Overall assessment percentage.

    Returns:
        Performance classification.
    """

    if percentage >= 90:
        return "Excellent"

    elif percentage >= 75:
        return "Strong"

    elif percentage >= 60:
        return "Moderate"

    elif percentage >= 40:
        return "Developing"

    else:
        return "Needs Improvement"


# ============================================================
# 3.6 — STRENGTH / WEAKNESS DETECTION
# ============================================================

def identify_strengths_weaknesses(category_scores):
    """
    Identify strengths, moderate areas, and weaknesses
    based on category-wise percentages.

    Thresholds:
        >= 80% → Strength
        >= 60% → Moderate
        < 60%  → Weakness

    Parameters:
        category_scores:
            Dictionary containing category-wise scores.

    Returns:
        Dictionary containing:
            - strengths
            - moderate_areas
            - weaknesses
    """

    strengths = []
    moderate_areas = []
    weaknesses = []

    for category, data in category_scores.items():

        percentage = data["percentage"]

        if percentage >= 80:

            strengths.append({
                "category": category,
                "percentage": percentage
            })

        elif percentage >= 60:

            moderate_areas.append({
                "category": category,
                "percentage": percentage
            })

        else:

            weaknesses.append({
                "category": category,
                "percentage": percentage
            })

    return {
        "strengths": strengths,
        "moderate_areas": moderate_areas,
        "weaknesses": weaknesses
    }


# ============================================================
# 3.7 — FINAL JSON RESULT
# ============================================================

def generate_final_result(
    results,
    category_scores,
    overall_score,
    classification,
    strength_analysis
):
    """
    Generate the final structured assessment result.

    Combines:
        - Individual question results
        - Category-wise scores
        - Overall score
        - Performance classification
        - Strengths
        - Moderate areas
        - Weaknesses
    """

    return {

        "assessment": {
            "name": "Minerva Career Assessment",
            "version": "1.0",
            "total_questions": len(results)
        },

        "results": {

            "overall": {
                "score": overall_score["score"],
                "max_score": overall_score["max_score"],
                "percentage": overall_score["percentage"],
                "classification": classification
            },

            "categories": category_scores,

            "strengths": strength_analysis["strengths"],

            "moderate_areas": strength_analysis["moderate_areas"],

            "weaknesses": strength_analysis["weaknesses"],

            "questions": results
        }
    }


# ============================================================
# 3.9 — BACKEND HANDOFF FUNCTION
# ============================================================

def process_assessment(student_answers):
    """
    Main production function for the backend.

    Receives student answers and returns
    the complete assessment result.

    Parameters:
        student_answers:
            Dictionary containing question IDs
            and selected option IDs.

    Example:
        {
            "PS-01": "A",
            "PS-02": "B",
            "PS-03": "B"
        }

    Returns:
        Complete structured assessment result.
    """

    # 3.2 — Score individual questions
    results = score_assessment(student_answers)

    # 3.3 — Category-wise scores
    category_scores = calculate_category_scores(results)

    # 3.4 — Overall score
    overall_score = calculate_overall_score(results)

    # 3.5 — Classification
    classification = classify_score(
        overall_score["percentage"]
    )

    # 3.6 — Strengths / Weaknesses
    strength_analysis = identify_strengths_weaknesses(
        category_scores
    )

    # 3.7 — Final JSON
    final_result = generate_final_result(
        results,
        category_scores,
        overall_score,
        classification,
        strength_analysis
    )

    return final_result


# ============================================================
# TESTING
# ============================================================

if __name__ == "__main__":

    sample_students = {

        # ----------------------------------------------------
        # HIGH PERFORMER
        # ----------------------------------------------------

        "high_performer": {

            "PS-01": "A",
            "PS-02": "B",
            "PS-03": "B",
            "PS-04": "B",
            "PS-05": "C",

            "AT-01": "B",
            "AT-02": "C",
            "AT-03": "C",
            "AT-04": "B",
            "AT-05": "B",

            "LR-01": "B",
            "LR-02": "A",
            "LR-03": "B",
            "LR-04": "D",
            "LR-05": "A",

            "TA-01": "B",
            "TA-02": "C",
            "TA-03": "A",
            "TA-04": "B",
            "TA-05": "B",
            "TA-06": "C",
            "TA-07": "A",

            "CR-01": "B",
            "CR-02": "B",
            "CR-03": "C",
            "CR-04": "B",
            "CR-05": "B",

            "CM-01": "B",
            "CM-02": "C",
            "CM-03": "B",
            "CM-04": "C",

            "AD-01": "D",
            "AD-02": "D",
            "AD-03": "B",
            "AD-04": "D",
            "AD-05": "C",

            "LA-01": "B",
            "LA-02": "C",
            "LA-03": "B",
            "LA-04": "A"
        },


        # ----------------------------------------------------
        # AVERAGE PERFORMER
        # ----------------------------------------------------

        "average_performer": {

            "PS-01": "A",
            "PS-02": "B",
            "PS-03": "A",
            "PS-04": "B",
            "PS-05": "A",

            "AT-01": "B",
            "AT-02": "C",
            "AT-03": "A",
            "AT-04": "B",
            "AT-05": "C",

            "LR-01": "B",
            "LR-02": "A",
            "LR-03": "A",
            "LR-04": "D",
            "LR-05": "D",

            "TA-01": "B",
            "TA-02": "C",
            "TA-03": "B",
            "TA-04": "B",
            "TA-05": "A",
            "TA-06": "C",
            "TA-07": "B",

            "CR-01": "B",
            "CR-02": "A",
            "CR-03": "C",
            "CR-04": "A",
            "CR-05": "C",

            "CM-01": "B",
            "CM-02": "C",
            "CM-03": "A",
            "CM-04": "C",

            "AD-01": "D",
            "AD-02": "A",
            "AD-03": "B",
            "AD-04": "A",
            "AD-05": "C",

            "LA-01": "B",
            "LA-02": "A",
            "LA-03": "B",
            "LA-04": "C"
        },


        # ----------------------------------------------------
        # WEAK PERFORMER
        # ----------------------------------------------------

        "weak_performer": {

            "PS-01": "B",
            "PS-02": "A",
            "PS-03": "A",
            "PS-04": "C",
            "PS-05": "D",

            "AT-01": "A",
            "AT-02": "A",
            "AT-03": "B",
            "AT-04": "A",
            "AT-05": "C",

            "LR-01": "A",
            "LR-02": "B",
            "LR-03": "A",
            "LR-04": "A",
            "LR-05": "D",

            "TA-01": "A",
            "TA-02": "A",
            "TA-03": "B",
            "TA-04": "A",
            "TA-05": "C",
            "TA-06": "A",
            "TA-07": "B",

            "CR-01": "A",
            "CR-02": "A",
            "CR-03": "A",
            "CR-04": "A",
            "CR-05": "C",

            "CM-01": "A",
            "CM-02": "A",
            "CM-03": "A",
            "CM-04": "A",

            "AD-01": "A",
            "AD-02": "A",
            "AD-03": "A",
            "AD-04": "A",
            "AD-05": "A",

            "LA-01": "A",
            "LA-02": "A",
            "LA-03": "A",
            "LA-04": "B"
        },


        # ----------------------------------------------------
        # MIXED PERFORMER
        # ----------------------------------------------------

        "mixed_performer": {

            "PS-01": "A",
            "PS-02": "B",
            "PS-03": "B",
            "PS-04": "A",
            "PS-05": "D",

            "AT-01": "B",
            "AT-02": "C",
            "AT-03": "C",
            "AT-04": "A",
            "AT-05": "C",

            "LR-01": "B",
            "LR-02": "A",
            "LR-03": "B",
            "LR-04": "A",
            "LR-05": "D",

            "TA-01": "B",
            "TA-02": "C",
            "TA-03": "A",
            "TA-04": "A",
            "TA-05": "C",
            "TA-06": "C",
            "TA-07": "B",

            "CR-01": "B",
            "CR-02": "B",
            "CR-03": "C",
            "CR-04": "A",
            "CR-05": "C",

            "CM-01": "B",
            "CM-02": "A",
            "CM-03": "B",
            "CM-04": "A",

            "AD-01": "D",
            "AD-02": "A",
            "AD-03": "B",
            "AD-04": "D",
            "AD-05": "A",

            "LA-01": "B",
            "LA-02": "C",
            "LA-03": "A",
            "LA-04": "C"
        }
    }


    # ========================================================
    # RUN TEST STUDENTS
    # ========================================================

    for student_name, student_answers in sample_students.items():

        print("\n")
        print("========================================")
        print(f"TEST STUDENT: {student_name.upper()}")
        print("========================================")

        # 3.9 production function
        final_result = process_assessment(
            student_answers
        )

        overall = final_result["results"]["overall"]

        strength_analysis = {
            "strengths": final_result["results"]["strengths"],
            "moderate_areas": final_result["results"]["moderate_areas"],
            "weaknesses": final_result["results"]["weaknesses"]
        }

        # Print summary
        print(
            f"Overall Score: "
            f"{overall['score']}/"
            f"{overall['max_score']}"
        )

        print(
            f"Percentage: "
            f"{overall['percentage']}%"
        )

        print(
            f"Classification: "
            f"{overall['classification']}"
        )

        print("\nStrengths:")

        for item in strength_analysis["strengths"]:
            print(
                f"- {item['category']}: "
                f"{item['percentage']}%"
            )

        print("\nModerate Areas:")

        for item in strength_analysis["moderate_areas"]:
            print(
                f"- {item['category']}: "
                f"{item['percentage']}%"
            )

        print("\nWeaknesses:")

        for item in strength_analysis["weaknesses"]:
            print(
                f"- {item['category']}: "
                f"{item['percentage']}%"
            )

        # Save individual student result
        output_file = (
    BASE_DIR / "data" / f"{student_name}_assessment_result.json"
)

        with open(
            output_file,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                final_result,
                file,
                indent=2,
                ensure_ascii=False
            )

        print(
            f"\nResult saved: {output_file}"
        )