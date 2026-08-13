from typing import Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from assessment.scoring import process_assessment
from career.career_matching import generate_career_matches
from career.top_careers import generate_top_career_result
from career.career_comparison import generate_comparison_result


app = FastAPI(
    title="Minerva Assessment Scoring Service",
    version="1.0.0"
)


class AssessmentRequest(BaseModel):
    answers: Dict[str, str] = Field(
        ...,
        description="Dictionary containing question IDs and selected answer IDs."
    )


class CareerMatchRequest(BaseModel):
    student_skills: Dict[str, float] = Field(
        ...,
        description="Dictionary containing category names and percentage scores."
    )


class SelectedCareer(BaseModel):
    career: str
    match_percentage: float


class CareerCompareRequest(BaseModel):
    selected_careers: List[SelectedCareer] = Field(
        ...,
        description="List of careers selected for comparison."
    )
    student_skills: Dict[str, float] = Field(
        ...,
        description="Dictionary containing category names and percentage scores."
    )


@app.get("/")
def root():
    return {
        "message": "Minerva Assessment Scoring Service is running",
        "version": "1.0.0"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.post("/score")
def score_assessment(request: AssessmentRequest):

    try:
        result = process_assessment(request.answers)

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Scoring failed: {str(e)}"
        )


@app.post("/career/match")
def match_careers(request: CareerMatchRequest):

    try:
        career_matches = generate_career_matches(request.student_skills)

        top_careers_result = generate_top_career_result(
            career_matches,
            top_n=10
        )

        return top_careers_result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Career matching failed: {str(e)}"
        )


# @app.post("/career/compare")
# def compare_careers(request: CareerCompareRequest):

#     try:
#         selected_careers = [
#             {"career": c.career, "match_percentage": c.match_percentage}
#             for c in request.selected_careers
#         ]

#         result = generate_comparison_result(
#             selected_careers,
#             request.student_skills
#         )

#         return result

#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Career comparison failed: {str(e)}"
#         )
@app.post("/career/compare")
def compare_careers(request: CareerCompareRequest):
    try:
        selected_careers = [
            {
                "career": c.career,
                "match_percentage": c.match_percentage
            }
            for c in request.selected_careers
        ]

        print("Selected careers:", selected_careers)
        print("Student skills:", request.student_skills)

        result = generate_comparison_result(
            selected_careers,
            request.student_skills
        )

        print("Comparison result:", result)

        return result

    except Exception as e:
        import traceback
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Career comparison failed: {str(e)}"
        )