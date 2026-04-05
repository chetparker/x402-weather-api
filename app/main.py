"""
UK Weather Data API — Powered by x402
======================================
Free weather data from Open-Meteo, paid via x402 on Base mainnet.
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.middleware.payment import X402PaymentMiddleware

# Import routers
from app.routes.current import router as current_router
from app.routes.forecast import router as forecast_router
from app.routes.historical import router as historical_router
from app.routes.air_quality import router as air_quality_router


def setup_logging():
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title="Weather Data API",
    version="1.0.0",
    description=(
        "Global weather data — current conditions, forecasts, historical data, "
        "and air quality. Paid via x402 protocol on Base mainnet."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# x402 Payment
app.add_middleware(X402PaymentMiddleware)

# Routes
app.include_router(current_router)
app.include_router(forecast_router)
app.include_router(historical_router)
app.include_router(air_quality_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": "An unexpected error occurred."},
    )


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": "Weather Data API",
        "version": "1.0.0",
        "docs": "/docs",
        "discovery": "/.well-known/x402.json",
    }


@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/.well-known/x402.json", include_in_schema=False)
async def well_known_x402():
    return {
        "x402Version": 2,
        "service": {
            "name": "Weather Data API",
            "description": "Global weather: current conditions, forecasts, historical data, air quality",
            "version": "1.0.0",
            "homepage": "https://github.com/chetparker/x402-weather-api",
        },
        "payment": {
            "payTo": settings.payment_wallet_address,
            "network": "eip155:8453",
            "scheme": "exact",
            "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "facilitator": settings.x402_facilitator_url,
        },
        "endpoints": [
            {"method": "POST", "path": "/current", "price": "$0.001", "description": "Current weather conditions"},
            {"method": "POST", "path": "/forecast", "price": "$0.001", "description": "7-day weather forecast"},
            {"method": "POST", "path": "/historical", "price": "$0.002", "description": "Historical weather data"},
            {"method": "POST", "path": "/air-quality", "price": "$0.001", "description": "Air quality index"},
        ],
    }
