"""
bazaar.py — Discovery metadata for Coinbase Agentic.Market (Bazaar)
====================================================================
Per Coinbase x402 spec v2, the CDP facilitator extracts
`extensions.bazaar` from accepted-payment metadata at settle time and
indexes it on agentic.market.

Each entry below uses the v2 shape:

    {
      "info":   { "input": {...realistic example...}, "output": {...} },
      "schema": { JSON Schema (draft 2020-12) for input + output },
    }

The CDP facilitator validates `info.input` against
`schema.properties.input`. If validation fails, the resource is dropped
from the index and the EXTENSION-RESPONSES header carries
`status: rejected`.

Single source of truth: imported by main.py (well-known) and
middleware/payment.py (402 challenge response).
"""

_JSON_SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _v2(
    *,
    body_example: dict,
    body_properties: dict,
    body_required: list,
    output_example: dict,
    output_properties: dict,
    # tags/category retained on the call sites but currently dropped — the
    # x402 SDK's declareDiscoveryExtension does NOT emit these fields and
    # CDP rejects extensions that include them at the top level under
    # `discovery request validation failed`. Kept as kwargs so the data
    # is still recorded if/when CDP supports it.
    tags: list | None = None,
    category: str | None = None,
) -> dict:
    """Build a v2 Bazaar metadata entry from compact inputs."""
    missing = [k for k in body_required if k not in body_example]
    if missing:
        raise ValueError(
            f"body_example is missing required keys {missing}; "
            "CDP would reject this entry."
        )

    body_input_schema = {
        "type": "object",
        "properties": body_properties,
        "required": body_required,
    }

    output_example_schema: dict = {"type": "object"}
    if output_properties:
        output_example_schema["properties"] = output_properties

    return {
        "info": {
            "input": {
                "type": "http",
                "method": "POST",
                "bodyType": "json",
                "body": body_example,
            },
            "output": {
                "type": "json",
                "example": output_example,
            },
        },
        "schema": {
            "$schema": _JSON_SCHEMA_DRAFT,
            "type": "object",
            "properties": {
                "input": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "const": "http"},
                        "method": {"type": "string", "enum": ["POST", "PUT", "PATCH"]},
                        "bodyType": {"type": "string", "enum": ["json", "form-data", "text"]},
                        "body": body_input_schema,
                    },
                    "required": ["type", "method", "bodyType", "body"],
                    "additionalProperties": False,
                },
                "output": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "example": output_example_schema,
                    },
                    "required": ["type"],
                },
            },
            "required": ["input"],
        },
    }


# ---------------------------------------------------------------------------
# Route → v2 metadata. Keys are FastAPI route paths.
# ---------------------------------------------------------------------------

BAZAAR_METADATA: dict = {
    "/current": _v2(
        body_example={"location": "London"},
        body_properties={
            "location": {
                "type": "string",
                "description": "City or place name to fetch weather for (e.g. 'London', 'New York').",
            },
            "latitude": {
                "type": ["number", "null"],
                "description": "Optional latitude override (decimal degrees, -90 to 90).",
            },
            "longitude": {
                "type": ["number", "null"],
                "description": "Optional longitude override (decimal degrees, -180 to 180).",
            },
        },
        body_required=["location"],
        output_example={
            "location": {
                "name": "London",
                "country": "United Kingdom",
                "latitude": 51.50853,
                "longitude": -0.12574,
            },
            "current": {
                "temperature_c": 12.4,
                "feels_like_c": 10.1,
                "humidity_pct": 78,
                "precipitation_mm": 0.0,
                "rain_mm": 0.0,
                "wind_speed_kmh": 14.3,
                "wind_direction_deg": 230,
                "weather_code": 2,
                "weather_description": "Partly cloudy",
                "time": "2026-05-02T10:00",
                "timezone": "Europe/London",
            },
            "cached": False,
        },
        output_properties={
            "location": {"type": "object"},
            "current": {"type": "object", "description": "Temperature, feels-like, humidity, precipitation, wind, weather code/description."},
            "cached": {"type": "boolean"},
        },
        tags=["weather", "current-conditions", "global", "open-meteo"],
    ),
    "/forecast": _v2(
        body_example={"location": "London", "days": 7},
        body_properties={
            "location": {
                "type": "string",
                "description": "City or place name to forecast weather for.",
            },
            "days": {
                "type": "integer",
                "minimum": 1,
                "maximum": 16,
                "description": "Number of forecast days to return (1-16). Defaults to 7.",
            },
        },
        body_required=["location"],
        output_example={
            "location": {
                "name": "London",
                "country": "United Kingdom",
                "latitude": 51.50853,
                "longitude": -0.12574,
            },
            "days": 7,
            "forecast": [
                {
                    "date": "2026-05-02",
                    "temp_max_c": 17.2,
                    "temp_min_c": 9.4,
                    "precipitation_mm": 0.4,
                    "rain_mm": 0.4,
                    "wind_max_kmh": 22.7,
                    "weather_code": 61,
                    "weather_description": "Slight rain",
                    "sunrise": "2026-05-02T05:24",
                    "sunset": "2026-05-02T20:31",
                },
            ],
            "cached": False,
        },
        output_properties={
            "location": {"type": "object"},
            "days": {"type": "integer"},
            "forecast": {"type": "array", "description": "Daily forecast entries with min/max temp, precipitation, wind, weather code, sunrise/sunset."},
            "cached": {"type": "boolean"},
        },
        tags=["weather", "forecast", "global", "open-meteo"],
    ),
    "/historical": _v2(
        body_example={
            "location": "London",
            "start_date": "2024-01-01",
            "end_date": "2024-01-07",
        },
        body_properties={
            "location": {
                "type": "string",
                "description": "City or place name to fetch historical weather for.",
            },
            "start_date": {
                "type": "string",
                "description": "Start date in YYYY-MM-DD format.",
            },
            "end_date": {
                "type": "string",
                "description": "End date in YYYY-MM-DD format.",
            },
        },
        body_required=["location", "start_date", "end_date"],
        output_example={
            "location": {
                "name": "London",
                "country": "United Kingdom",
                "latitude": 51.50853,
                "longitude": -0.12574,
            },
            "days": 7,
            "history": [
                {
                    "date": "2024-01-01",
                    "temp_max_c": 9.8,
                    "temp_min_c": 4.2,
                    "precipitation_mm": 1.6,
                    "rain_mm": 1.6,
                    "wind_max_kmh": 19.8,
                    "weather_code": 61,
                    "weather_description": "Slight rain",
                },
            ],
            "cached": False,
        },
        output_properties={
            "location": {"type": "object"},
            "days": {"type": "integer"},
            "history": {"type": "array", "description": "Daily historical weather records with temp, precipitation, wind, weather code."},
            "cached": {"type": "boolean"},
        },
        tags=["weather", "historical", "archive", "global", "open-meteo"],
    ),
    "/air-quality": _v2(
        body_example={"location": "London"},
        body_properties={
            "location": {
                "type": "string",
                "description": "City or place name to fetch air quality for.",
            },
        },
        body_required=["location"],
        output_example={
            "location": {
                "name": "London",
                "country": "United Kingdom",
                "latitude": 51.50853,
                "longitude": -0.12574,
            },
            "air_quality": {
                "european_aqi": 38,
                "us_aqi": 47,
                "aqi_category": "Good",
                "pm10": 14.2,
                "pm2_5": 8.7,
                "carbon_monoxide": 210.0,
                "nitrogen_dioxide": 22.4,
                "sulphur_dioxide": 1.6,
                "ozone": 64.1,
                "time": "2026-05-02T10:00",
            },
            "cached": False,
        },
        output_properties={
            "location": {"type": "object"},
            "air_quality": {"type": "object", "description": "European/US AQI, category, PM10, PM2.5, CO, NO2, SO2, O3 readings."},
            "cached": {"type": "boolean"},
        },
        tags=["weather", "air-quality", "aqi", "pollution", "global", "open-meteo"],
    ),
}


ENDPOINT_DESCRIPTIONS: dict = {
    "/current": "Current weather conditions for any global location — temperature, feels-like, humidity, precipitation, wind, and human-readable weather description.",
    "/forecast": "Multi-day weather forecast (1-16 days) for any global location — daily min/max temperatures, precipitation, wind, weather codes, sunrise and sunset.",
    "/historical": "Historical daily weather data for any global location and date range — min/max temperature, precipitation, wind, and weather codes from the Open-Meteo archive.",
    "/air-quality": "Current air quality for any global location — European and US AQI, category, PM10, PM2.5, CO, NO2, SO2, O3 concentrations.",
}


def get_metadata(path: str) -> dict | None:
    """Return v2 bazaar metadata for the given path, or None if not registered."""
    return BAZAAR_METADATA.get(path.rstrip("/") or "/")


def get_description(path: str) -> str | None:
    """Return short description for resource cataloging, or None if not registered."""
    return ENDPOINT_DESCRIPTIONS.get(path.rstrip("/") or "/")
