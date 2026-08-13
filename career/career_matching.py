import json
import os


# ============================================================
# FILE PATH
# ============================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CAREERS_FILE = os.path.join(
    BASE_DIR,
    "data",
    "career_requirements.json"
)


# ============================================================
# LOAD CAREER REQUIREMENTS
# ============================================================

def load_career_requirements():
    """
    Load career requirements from JSON file.

    Returns:
        List of career dictionaries.
    """

    with open(
        CAREERS_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    return data["careers"]


# ============================================================
# CALCULATE CAREER MATCH
# ============================================================

def calculate_career_match(
    student_skills,
    career
):
    """
    Calculate how well a student's skills
    match a particular career.

    Parameters:
        student_skills:
            Dictionary containing category percentages.

        career:
            Career dictionary from career_requirements.json.

    Returns:
        Career match result.
    """

    requirements = career["required_skills"]

    weighted_score = 0
    total_weight = 0

    skill_details = []

    for skill, weight in requirements.items():

        student_score = student_skills.get(
            skill,
            0
        )

        weighted_score += (
            student_score * weight
        )

        total_weight += weight

        skill_details.append({
            "skill": skill,
            "student_score": student_score,
            "required_weight": weight
        })

    if total_weight > 0:

        match_percentage = (
            weighted_score / total_weight
        )

    else:

        match_percentage = 0

    return {
        "career_id": career["career_id"],
        "career": career["career"],
        "match_percentage": round(
            match_percentage,
            2
        ),
        "skill_details": skill_details
    }


# ============================================================
# MATCH STUDENT WITH ALL CAREERS
# ============================================================

def match_student_to_careers(
    student_skills
):
    """
    Compare student's skill profile
    against all available careers.

    Returns:
        List of career matches.
    """

    careers = load_career_requirements()

    career_matches = []

    for career in careers:

        match = calculate_career_match(
            student_skills,
            career
        )

        career_matches.append(match)

    return career_matches


# ============================================================
# SORT CAREER MATCHES
# ============================================================

def rank_career_matches(
    career_matches
):
    """
    Sort careers from highest match
    percentage to lowest.
    """

    return sorted(
        career_matches,
        key=lambda career:
            career["match_percentage"],
        reverse=True
    )


# ============================================================
# MAIN CAREER MATCHING FUNCTION
# ============================================================

def generate_career_matches(
    student_skills
):
    """
    Main production function.

    Student Skill Profile
            ↓
    Compare with Careers
            ↓
    Calculate Match %
            ↓
    Rank Careers
    """

    career_matches = match_student_to_careers(
        student_skills
    )

    ranked_matches = rank_career_matches(
        career_matches
    )

    return ranked_matches


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    sample_student = {

        "problem_solving": 85,

        "analytical_thinking": 82,

        "logical_reasoning": 78,

        "technical_aptitude": 90,

        "creativity": 70,

        "communication": 65,

        "attention_to_detail": 80,

        "learning_ability": 88
    }


    print("\n========================================")
    print("MINERVA CAREER MATCHING TEST")
    print("========================================")


    matches = generate_career_matches(
        sample_student
    )


    print("\nCareer Matches:")


    for index, career in enumerate(
        matches,
        start=1
    ):

        print(
            f"{index}. "
            f"{career['career']} "
            f"→ "
            f"{career['match_percentage']}%"
        )