"""
test_payment.py — Send a real x402 paid request to x402-weather-api
"""

import os
import json
import base64
import time
import secrets
import httpx
from dotenv import load_dotenv
from eth_account import Account
from eth_account.messages import encode_typed_data

load_dotenv("/Users/chetp/Desktop/uk-property-api/.env")

BUYER_PRIVATE_KEY = os.getenv("BUYER_PRIVATE_KEY")
BUYER_ADDRESS = os.getenv("BUYER_ADDRESS")
SELLER_ADDRESS = os.getenv("SELLER_ADDRESS")

API_URL = "https://x402-weather-api-production-04c4.up.railway.app"
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
CHAIN_ID = 8453  # Base mainnet

ENDPOINT_PATH = "/current"
ENDPOINT_BODY = {"latitude": 51.5074, "longitude": -0.1278, "location": "London"}


def sign_payment(amount_atomic: int, valid_after: int, valid_before: int, nonce_hex: str):
    """Sign EIP-712 transferWithAuthorization for USDC on Base."""
    typed_data = {
        "domain": {
            "name": "USD Coin",
            "version": "2",
            "chainId": CHAIN_ID,
            "verifyingContract": USDC_BASE,
        },
        "primaryType": "TransferWithAuthorization",
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "TransferWithAuthorization": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "validAfter", "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce", "type": "bytes32"},
            ],
        },
        "message": {
            "from": BUYER_ADDRESS,
            "to": SELLER_ADDRESS,
            "value": amount_atomic,
            "validAfter": valid_after,
            "validBefore": valid_before,
            "nonce": nonce_hex,
        },
    }

    signable = encode_typed_data(full_message=typed_data)
    signed = Account.sign_message(signable, private_key=BUYER_PRIVATE_KEY)

    return {
        "from": BUYER_ADDRESS,
        "to": SELLER_ADDRESS,
        "value": str(amount_atomic),
        "validAfter": str(valid_after),
        "validBefore": str(valid_before),
        "nonce": nonce_hex,
        "signature": signed.signature.hex(),
    }


def main():
    url = f"{API_URL}{ENDPOINT_PATH}"

    print(f"\n=== Step 1: Initial request (expecting 402) ===")
    print(f"POST {url}")

    with httpx.Client(timeout=30.0) as client:
        r1 = client.post(url, json=ENDPOINT_BODY)

    print(f"Status: {r1.status_code}")
    if r1.status_code != 402:
        print(f"Unexpected response: {r1.text[:500]}")
        return

    challenge = r1.json()
    print(f"Got 402 challenge: {json.dumps(challenge, indent=2)[:500]}")

    accept = challenge["accepts"][0]
    amount_atomic = int(accept["amount"])
    pay_to = accept["payTo"]

    print(f"\n=== Step 2: Sign payment ===")
    print(f"Amount: {amount_atomic} atomic units (= ${amount_atomic / 1_000_000} USDC)")
    print(f"Pay to: {pay_to}")

    valid_after = 0
    valid_before = int(time.time()) + accept.get("maxTimeoutSeconds", 300)
    nonce_hex = "0x" + secrets.token_hex(32)

    auth = sign_payment(amount_atomic, valid_after, valid_before, nonce_hex)

    sig = auth["signature"] if auth["signature"].startswith("0x") else "0x" + auth["signature"]

    # Per x402 v2 PaymentPayload schema, the buyer copies `extensions` and
    # `resource` from the 402 PaymentRequired body into the X-PAYMENT body.
    # CDP reads paymentPayload.extensions.bazaar at verify/settle time to
    # catalog the resource — without these copies, the resource never gets
    # indexed in agentic.market discovery.
    payment_payload = {
        "x402Version": 2,
        "accepted": accept,
        "payload": {
            "signature": sig,
            "authorization": {
                "from": auth["from"],
                "to": auth["to"],
                "value": auth["value"],
                "validAfter": auth["validAfter"],
                "validBefore": auth["validBefore"],
                "nonce": auth["nonce"],
            },
        },
    }
    if "resource" in challenge:
        payment_payload["resource"] = challenge["resource"]
    if "extensions" in challenge:
        payment_payload["extensions"] = challenge["extensions"]

    encoded = base64.b64encode(json.dumps(payment_payload).encode()).decode()

    print(f"\n=== Step 3: Retry with X-PAYMENT header ===")
    with httpx.Client(timeout=60.0) as client:
        r2 = client.post(url, json=ENDPOINT_BODY, headers={"X-PAYMENT": encoded})

    print(f"Status: {r2.status_code}")
    print(f"Response (first 1000 chars):")
    print(r2.text[:1000])

    if r2.status_code == 200:
        print(f"\n🎉 PAYMENT SUCCEEDED. Weather API now CDP-indexed. 5 OUT OF 5.")
    else:
        print(f"\n⚠️  Non-200 response — payment may still have settled (which is what triggers indexing). Check Railway logs.")


if __name__ == "__main__":
    main()
