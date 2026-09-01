"""
roadmap/roadmap/router.py

Exposes MINERVA's generate_roadmap() as REST endpoints, following the
same module pattern as the Assessment module (see
"Member 1 - Backend Handoff.md"):

    Frontend -> Backend (this router) -> roadmap_engine.py -> DB -> Frontend

Mount this in main.py with:

    from roadmap.roadmap.router import router as roadmap_router
    app.include_router(roadmap_router, prefix="/api/roadmap", tags=["roadmap"])

Endpoints:
    POST /api/roadmap/generate   -> run the engine, return + (optionally) persist
    GET  /api/roadmap/result/{id} -> fetch a previously generated roadmap
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional, Union, List
import uuid

from .roadmap_engine import generate_roadmap

router = APIRouter()

# --- Swap this for your real DB/session layer ---------------------------
# Placeholder in-memory store so the endpoint is testable immediately.
# Follow whatever persistence pattern assessment_results uses once you
# show me main.py / your DB models.
_ROADMAP_STORE: Dict[str, Union[Dict[str, Any], List[Dict[str, Any]]]] = {}
# --------------------------------------------------------------------------


class RoadmapGenerateRequest(BaseModel):
    journey: int                      # 1, 2, or 3
    journey_output: Dict[str, Any]    # raw Journey JSON (from assessment/career matching)
    weekly_hours: Optional[float] = None
    goal: Optional[str] = None
    target_role: Optional[str] = None
    preferred_days: Optional[int] = None
    use_model: bool = True            # False = deterministic, no Groq call
    user_id: Optional[str] = None     # so .NET can tag/track whose roadmap this is


class RoadmapGenerateResponse(BaseModel):
    roadmap_id: str
    result: Union[Dict[str, Any], List[Dict[str, Any]]]


@router.post("/generate", response_model=RoadmapGenerateResponse)
def generate(req: RoadmapGenerateRequest) -> RoadmapGenerateResponse:
    if req.journey not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="journey must be 1, 2, or 3")

    try:
        result = generate_roadmap(
            journey=req.journey,
            journey_output=req.journey_output,
            weekly_hours=req.weekly_hours,
            goal=req.goal,
            target_role=req.target_role,
            preferred_days=req.preferred_days,
            use_model=req.use_model,
        )
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        # Groq failures are already handled internally via fallback
        # (BACKEND_INTEGRATION_GUIDE.md §7) — this is an unexpected error.
        raise HTTPException(status_code=500, detail=f"roadmap generation failed: {e}")

    # persist — unique id per call, avoids the output/roadmap.json
    # filename-collision issue called out in the integration guide
    roadmap_id = str(uuid.uuid4())
    _ROADMAP_STORE[roadmap_id] = result

    return RoadmapGenerateResponse(roadmap_id=roadmap_id, result=result)


@router.get("/result/{roadmap_id}")
def get_result(roadmap_id: str):
    result = _ROADMAP_STORE.get(roadmap_id)
    if result is None:
        raise HTTPException(status_code=404, detail="roadmap not found")
    return result
