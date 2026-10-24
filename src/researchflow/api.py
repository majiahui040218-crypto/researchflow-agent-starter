"""Run with: uvicorn researchflow.api:app --reload."""

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .service import load_research, run_research

logger = logging.getLogger(__name__)
app = FastAPI(title="ResearchFlow Agent", version="0.2.0")


class ResearchRequest(BaseModel):
    question: str = Field(min_length=5, max_length=500)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/research")
def research(body: ResearchRequest) -> dict:
    try:
        result = run_research(body.question)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unable to persist research task")
        raise HTTPException(status_code=503, detail="Unable to save or start task") from exc

    if result.status == "failed":
        transient = {"MODEL_BUSY", "MODEL_TIMEOUT", "MODEL_CONNECTION_FAILED", "MODEL_SERVICE_UNAVAILABLE", "ACCOUNT_RATE_LIMIT"}
        status_code = 503 if result.error_code in transient else 502
        # The task_id in this response can be queried using GET /research/{task_id}.
        raise HTTPException(status_code=status_code, detail=result.as_dict())
    return result.as_dict()


@app.get("/research/{task_id}")
def get_research(task_id: str) -> dict:
    try:
        result = load_research(task_id)
    except Exception as exc:
        logger.exception("Failed to read task")
        raise HTTPException(status_code=503, detail="Unable to load task") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return result.as_dict()
