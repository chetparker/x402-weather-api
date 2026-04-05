"""
weather.py — Open-Meteo API Client
====================================
Fetches weather data from Open-Meteo's free API.
No API key required. Covers the entire globe.
Docs: https://open-meteo.com/en/docs
"""

import httpx
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://api.open-meteo.com/v1"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


async def geocode_location(location: str) -> dict:
    """Convert a place name to lat/lon coordinates."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(GEOCODE_URL, params={"name": location, "count": 1})
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            raise ValueError(f"Location '{location}' not found")
        r = results[0]
        return {
            "name": r.get("name", location),
            "country": r.get("country", ""),
            "latitude": r["latitude"],
            "longitude": r["longitude"],
        }


async def fetch_current_weather(latitude: float, longitude: float) -> dict:
    """Fetch current weather conditions."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,wind_speed_10m,wind_direction_10m,weather_code",
        "timezone": "auto",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{BASE_URL}/forecast", params=params)
        resp.raise_for_status()
        data = resp.json()

    current = data.get("current", {})
    return {
        "temperature_c": current.get("temperature_2m"),
        "feels_like_c": current.get("apparent_temperature"),
        "humidity_pct": current.get("relative_humidity_2m"),
        "precipitation_mm": current.get("precipitation"),
        "rain_mm": current.get("rain"),
        "wind_speed_kmh": current.get("wind_speed_10m"),
        "wind_direction_deg": current.get("wind_direction_10m"),
        "weather_code": current.get("weather_code"),
        "weather_description": _weather_code_to_text(current.get("weather_code", 0)),
        "time": current.get("time"),
        "timezone": data.get("timezone"),
    }


async def fetch_forecast(latitude: float, longitude: float, days: int = 7) -> list:
    """Fetch multi-day weather forecast."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,rain_sum,wind_speed_10m_max,weather_code,sunrise,sunset",
        "timezone": "auto",
        "forecast_days": min(days, 16),
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{BASE_URL}/forecast", params=params)
        resp.raise_for_status()
        data = resp.json()

    daily = data.get("daily", {})
    dates = daily.get("time", [])
    forecast = []
    for i, date in enumerate(dates):
        forecast.append({
            "date": date,
            "temp_max_c": daily.get("temperature_2m_max", [None])[i],
            "temp_min_c": daily.get("temperature_2m_min", [None])[i],
            "precipitation_mm": daily.get("precipitation_sum", [None])[i],
            "rain_mm": daily.get("rain_sum", [None])[i],
            "wind_max_kmh": daily.get("wind_speed_10m_max", [None])[i],
            "weather_code": daily.get("weather_code", [None])[i],
            "weather_description": _weather_code_to_text(daily.get("weather_code", [0])[i]),
            "sunrise": daily.get("sunrise", [None])[i],
            "sunset": daily.get("sunset", [None])[i],
        })
    return forecast


async def fetch_historical(latitude: float, longitude: float, start_date: str, end_date: str) -> list:
    """Fetch historical weather data for a date range."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,rain_sum,wind_speed_10m_max,weather_code",
        "timezone": "auto",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"https://archive-api.open-meteo.com/v1/archive", params=params)
        resp.raise_for_status()
        data = resp.json()

    daily = data.get("daily", {})
    dates = daily.get("time", [])
    history = []
    for i, date in enumerate(dates):
        history.append({
            "date": date,
            "temp_max_c": daily.get("temperature_2m_max", [None])[i],
            "temp_min_c": daily.get("temperature_2m_min", [None])[i],
            "precipitation_mm": daily.get("precipitation_sum", [None])[i],
            "rain_mm": daily.get("rain_sum", [None])[i],
            "wind_max_kmh": daily.get("wind_speed_10m_max", [None])[i],
            "weather_code": daily.get("weather_code", [None])[i],
            "weather_description": _weather_code_to_text(daily.get("weather_code", [0])[i]),
        })
    return history


async def fetch_air_quality(latitude: float, longitude: float) -> dict:
    """Fetch current air quality data."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "european_aqi,us_aqi,pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(AIR_QUALITY_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    current = data.get("current", {})
    us_aqi = current.get("us_aqi", 0)
    return {
        "european_aqi": current.get("european_aqi"),
        "us_aqi": us_aqi,
        "aqi_category": _aqi_category(us_aqi),
        "pm10": current.get("pm10"),
        "pm2_5": current.get("pm2_5"),
        "carbon_monoxide": current.get("carbon_monoxide"),
        "nitrogen_dioxide": current.get("nitrogen_dioxide"),
        "sulphur_dioxide": current.get("sulphur_dioxide"),
        "ozone": current.get("ozone"),
        "time": current.get("time"),
    }


def _weather_code_to_text(code: int) -> str:
    """Convert WMO weather code to human-readable text."""
    codes = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Foggy", 48: "Depositing rime fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
        77: "Snow grains", 80: "Slight rain showers", 81: "Moderate rain showers",
        82: "Violent rain showers", 85: "Slight snow showers", 86: "Heavy snow showers",
        95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
    }
    return codes.get(code, f"Unknown ({code})")


def _aqi_category(aqi: int) -> str:
    """Convert US AQI to category."""
    if aqi <= 50: return "Good"
    if aqi <= 100: return "Moderate"
    if aqi <= 150: return "Unhealthy for Sensitive Groups"
    if aqi <= 200: return "Unhealthy"
    if aqi <= 300: return "Very Unhealthy"
    return "Hazardous"
