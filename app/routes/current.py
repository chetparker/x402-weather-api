"""Current weather conditions endpoint."""
import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Request
from app.services.weather import fetch_current_weather, geocode_location

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Weather"])


class CurrentRequest(BaseModel):
    location: str = Field(..., description="City or place name", examples=["London"])
    latitude: float | None = Field(default=None, description="Override latitude")
    longitude: float | None = Field(default=None, description="Override longitude")


@router.post("/current", summary="Current weather conditions")
async def get_current_weather(body: CurrentRequest, request: Request):
    try:
        if body.latitude is not None and body.longitude is not None:
            lat, lon = body.latitude, body.longitude
            geo = {"name": body.location, "country": "", "latitude": lat, "longitude": lon}
        else:
            geo = await geocode_location(body.location)
            lat, lon = geo["latitude"], geo["longitude"]

        weather = await fetch_current_weather(lat, lon)
        return {
            "location": geo,
            "current": weather,
            "cached": False,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": str(e)})
    except Exception as e:
        logger.error(f"Weather fetch failed: {e}")
        raise HTTPException(status_code=500, detail={"error": "weather_error", "detail": str(e)})
