"""7-day weather forecast endpoint."""
import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Request
from app.services.weather import fetch_forecast, geocode_location

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Weather"])


class ForecastRequest(BaseModel):
    location: str = Field(..., description="City or place name", examples=["London"])
    days: int = Field(default=7, ge=1, le=16, description="Forecast days (1-16)")


@router.post("/forecast", summary="Multi-day weather forecast")
async def get_forecast(body: ForecastRequest, request: Request):
    try:
        geo = await geocode_location(body.location)
        forecast = await fetch_forecast(geo["latitude"], geo["longitude"], body.days)
        return {"location": geo, "days": len(forecast), "forecast": forecast, "cached": False}
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": str(e)})
    except Exception as e:
        logger.error(f"Forecast fetch failed: {e}")
        raise HTTPException(status_code=500, detail={"error": "forecast_error", "detail": str(e)})
