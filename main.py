from typing import Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from journey1.skill_gap import build_final_result

import traceback
import json
import tempfile
from assessment.scoring import process_assessment
from career.career_matching import generate_career_matches
from career.top_careers import generate_top_career_result
from career.career_comparison import generate_comparison_result

from pathlib import Path

from journey1.exploring_scoring import load_assessment, evaluate_journey_1
from journey1.exploring_ai import build_ai_context, generate_local_interpretation
from journey1.exploring_recommendation import generate_recommendation

from journey2.journey_2_engine import (
    build_engine,
    InvalidCareerError,
    InvalidAnswersError,
)

app = FastAPI(
    title="Minerva Assessment Scoring Service",
    version="1.0.0"
)

BASE_DIR = Path(__file__).resolve().parent

J1_ASSESSMENT = load_assessment(
    BASE_DIR / "journey1" / "minerva_career_discovery_v4.json"
)

J2_ENGINE = build_engine(
    assessment_path=BASE_DIR / "journey2" / "assessment.json",
    skills_path=BASE_DIR / "journey2" / "journey_2_skills.json",
    matrix_path=BASE_DIR / "journey2" / "career_skill_matrix.json",
    normalization_path=BASE_DIR / "journey2" / "skill_normalization.json",
)

class Journey1Answer(BaseModel):
    question_id: str
    selected_option: str


class Journey1Request(BaseModel):
    assessment_id: str
    answers: List[Journey1Answer]

class Journey2SubmitRequest(BaseModel):
    career: str
    answers: Dict[str, str]


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
@app.head("/")
def root():
    return {
        "message": "Minerva Assessment Scoring Service is running",
        "version": "1.0.0"
    }


@app.get("/health")
@app.head("/health")
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

        result = generate_comparison_result(
            selected_careers,
            request.student_skills
        )

        return result

    except Exception as e:
        import traceback
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Career comparison failed: {str(e)}"
        )

@app.post("/journey1/exploring/complete")
def journey1_complete(request: Journey1Request):

    if request.assessment_id != "minerva_career_discovery_v4":
        raise HTTPException(status_code=404, detail="Assessment not found.")

    answers_dict = {a.question_id: a.selected_option for a in request.answers}

    try:
        deterministic_result = evaluate_journey_1(J1_ASSESSMENT, answers_dict)
        context = build_ai_context(J1_ASSESSMENT, deterministic_result)
        ai_result = generate_local_interpretation(context)

        ai_result_for_recommendation = {"ai_evaluation": ai_result}

        recommendation = generate_recommendation(
            J1_ASSESSMENT,
            deterministic_result,
            ai_result_for_recommendation
        )

        # --- NEW: skill_gap.py needs deterministic_result and
        # recommendation written to temp files, since it reads
        # from disk paths rather than accepting dicts directly.
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            exploring_result_path = tmp_path / "exploring_result.json"
            recommendation_path = tmp_path / "exploring_recommendation.json"
            output_path = tmp_path / "journey1_final_result.json"

            with exploring_result_path.open("w", encoding="utf-8") as f:
                json.dump(deterministic_result, f)

            with recommendation_path.open("w", encoding="utf-8") as f:
                json.dump(recommendation, f)

            final_result = build_final_result(
                exploring_result_path=exploring_result_path,
                recommendation_path=recommendation_path,
                matrix_path=BASE_DIR / "journey1" / "career_skill_matrix.json",
                normalization_path=BASE_DIR / "journey1" / "skill_normalization.json",
                output_path=output_path,
            )

        return final_result

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=400,
            detail=f"Journey 1 processing error: {str(e)}"
        )

    
@app.get("/journey2/questions")
def journey2_questions(career: str):
    try:
        return J2_ENGINE.get_career_questions(career)
    except InvalidCareerError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/journey2/submit")
def journey2_submit(request: Journey2SubmitRequest):
    try:
        return J2_ENGINE.score_assessment(career=request.career, answers=request.answers)
    except (InvalidCareerError, InvalidAnswersError) as e:
        raise HTTPException(status_code=400, detail=str(e))
