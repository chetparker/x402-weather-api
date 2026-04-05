"""
payment.py — x402 Payment Protocol Middleware (v2 + CDP Settlement)
"""

import httpx
import logging
import json
import base64
import time
import secrets
import os

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import get_settings

logger = logging.getLogger(__name__)

USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

FREE_ENDPOINTS = {
    "/", "/health", "/docs", "/openapi.json", "/redoc", "/favicon.ico", "/.well-known/x402.json",
}


def _build_cdp_jwt(method, path):
    """Build a JWT for authenticating with the CDP facilitator."""
    key_id = os.environ.get("CDP_API_KEY_ID", "")
    key_raw = os.environ.get("CDP_API_KEY_SECRET", "")

    if not key_id or not key_raw:
        return None

    key_bytes = base64.b64decode(key_raw)
    private_key = Ed25519PrivateKey.from_private_bytes(key_bytes[:32])
    uri = f"{method} api.cdp.coinbase.com{path}"

    payload = {
        "sub": key_id,
        "iss": "cdp",
        "nbf": int(time.time()),
        "exp": int(time.time()) + 120,
        "uri": uri,
    }

    return jwt.encode(
        payload,
        private_key,
        algorithm="EdDSA",
        headers={"kid": key_id, "nonce": secrets.token_hex()},
    )


def _decode_payload(payment_header):
    """Decode base64 payment payload to dict for facilitator."""
    try:
        return json.loads(base64.b64decode(payment_header))
    except Exception:
        return {"raw": payment_header}


class X402PaymentMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()
        path = request.url.path.rstrip("/") or "/"

        if path in FREE_ENDPOINTS:
            return await call_next(request)

        payment_header = (
            request.headers.get("X-PAYMENT")
            or request.headers.get("PAYMENT-SIGNATURE")
        )

        if not payment_header:
            logger.info(f"402 Payment Required for {request.method} {path}")
            return _build_402_response(settings, request)

        is_valid = await _verify_and_settle(
            payment_header=payment_header,
            settings=settings,
            request=request,
        )

        if not is_valid:
            logger.warning(f"Invalid payment for {request.method} {path}")
            return JSONResponse(
                status_code=402,
                content={"error": "payment_invalid", "detail": "Payment verification failed."},
            )

        logger.info(f"Payment verified for {request.method} {path}")
        return await call_next(request)


def _build_402_response(settings, request: Request) -> JSONResponse:
    price_usd = float(settings.price_per_request)
    amount = str(int(price_usd * 1_000_000))

    body = {
        "x402Version": 2,
        "error": "Payment required",
        "resource": {"url": str(request.url)},
        "accepts": [
            {
                "scheme": "exact",
                "network": "eip155:8453",
                "asset": USDC_BASE,
                "amount": amount,
                "payTo": settings.payment_wallet_address,
                "maxTimeoutSeconds": 300,
                "extra": {
                    "name": "USD Coin",
                    "version": "2",
                },
            }
        ],
    }

    encoded = base64.b64encode(json.dumps(body).encode()).decode()

    return JSONResponse(
        status_code=402,
        content=body,
        headers={"PAYMENT-REQUIRED": encoded},
    )


async def _verify_and_settle(payment_header: str, settings, request: Request) -> bool:
    """Verify payment and settle on-chain via CDP facilitator."""
    facilitator_url = settings.x402_facilitator_url

    if not facilitator_url:
        logger.warning("No facilitator URL — accepting all payments (dev mode)")
        return True

    price_usd = float(settings.price_per_request)
    amount = str(int(price_usd * 1_000_000))

    payment_requirements = {
        "scheme": "exact",
        "network": "eip155:8453",
        "asset": USDC_BASE,
        "amount": amount,
        "payTo": settings.payment_wallet_address,
        "maxTimeoutSeconds": 300,
        "extra": {"name": "USD Coin", "version": "2"},
    }

    decoded_payload = _decode_payload(payment_header)

    verify_body = {
        "x402Version": 2,
        "paymentPayload": decoded_payload,
        "paymentRequirements": payment_requirements,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            # Build auth headers
            headers = {}
            verify_jwt = _build_cdp_jwt("POST", "/platform/v2/x402/verify")
            if verify_jwt:
                headers["Authorization"] = f"Bearer {verify_jwt}"

            # Step 1: Verify
            response = await client.post(
                f"{facilitator_url}/verify",
                json=verify_body,
                headers=headers,
            )

            if response.status_code != 200:
                logger.error(f"Facilitator verify returned {response.status_code}: {response.text}")
                return False

            result = response.json()
            is_valid = result.get("isValid", False)

            if not is_valid:
                logger.warning(f"Payment invalid: {result}")
                return False

            logger.info(f"Payment verified: payer={result.get('payer')}")

            # Step 2: Settle (move money on-chain)
            settle_headers = {}
            settle_jwt = _build_cdp_jwt("POST", "/platform/v2/x402/settle")
            if settle_jwt:
                settle_headers["Authorization"] = f"Bearer {settle_jwt}"

            settle_resp = await client.post(
                f"{facilitator_url}/settle",
                json=verify_body,
                headers=settle_headers,
            )

            settle_data = settle_resp.json()

            if settle_data.get("success"):
                tx_hash = settle_data.get("transaction", "")
                logger.info(f"Payment settled on-chain: {tx_hash}")
            else:
                logger.warning(f"Settlement failed: {settle_data}")
                # Still return True — payment was verified even if settle failed

            return True

    except httpx.TimeoutException:
        logger.error("Payment verification timed out")
        return False
    except Exception as e:
        logger.error(f"Payment verification failed: {e}")
        return False
