"""Air quality index endpoint."""
import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Request
from app.services.weather import fetch_air_quality, geocode_location

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Weather"])


class AirQualityRequest(BaseModel):
    location: str = Field(..., description="City or place name", examples=["London"])


@router.post("/air-quality", summary="Air quality index")
async def get_air_quality(body: AirQualityRequest, request: Request):
    try:
        geo = await geocode_location(body.location)
        aq = await fetch_air_quality(geo["latitude"], geo["longitude"])
        return {"location": geo, "air_quality": aq, "cached": False}
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": str(e)})
    except Exception as e:
        logger.error(f"Air quality fetch failed: {e}")
        raise HTTPException(status_code=500, detail={"error": "air_quality_error", "detail": str(e)})
