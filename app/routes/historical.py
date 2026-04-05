"""Historical weather data endpoint."""
import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Request
from app.services.weather import fetch_historical, geocode_location

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Weather"])


class HistoricalRequest(BaseModel):
    location: str = Field(..., description="City or place name", examples=["London"])
    start_date: str = Field(..., description="Start date YYYY-MM-DD", examples=["2024-01-01"])
    end_date: str = Field(..., description="End date YYYY-MM-DD", examples=["2024-01-31"])


@router.post("/historical", summary="Historical weather data")
async def get_historical(body: HistoricalRequest, request: Request):
    try:
        geo = await geocode_location(body.location)
        history = await fetch_historical(geo["latitude"], geo["longitude"], body.start_date, body.end_date)
        return {"location": geo, "days": len(history), "history": history, "cached": False}
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": str(e)})
    except Exception as e:
        logger.error(f"Historical fetch failed: {e}")
        raise HTTPException(status_code=500, detail={"error": "historical_error", "detail": str(e)})
