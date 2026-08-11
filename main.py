from typing import Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from assessment.scoring import process_assessment


app = FastAPI(
    title="Minerva Assessment Scoring Service",
    version="1.0.0"
)


class AssessmentRequest(BaseModel):
    answers: Dict[str, str] = Field(
        ...,
        description="Dictionary containing question IDs and selected answer IDs."
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