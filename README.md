# Weather Data API — x402 Paid

Global weather data paid via x402 protocol on Base mainnet.

## Endpoints

| Endpoint | What It Does | Price |
|---|---|---|
| `/current` | Current weather conditions | $0.001 |
| `/forecast` | 7-day weather forecast | $0.001 |
| `/historical` | Historical weather data | $0.002 |
| `/air-quality` | Air quality index | $0.001 |

## Data Source

[Open-Meteo](https://open-meteo.com/) — free, no API key required, global coverage.

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your wallet address + CDP keys
uvicorn app.main:app --reload
```

## Deploy to Railway

```bash
railway login
railway link
railway up
```

Set environment variables in Railway dashboard:
- `PAYMENT_WALLET_ADDRESS`
- `X402_FACILITATOR_URL`
- `CDP_API_KEY_ID`
- `CDP_API_KEY_SECRET`

## Built with

- [x402-fastapi-kit](https://github.com/chetparker/x402-fastapi-kit)
- [Open-Meteo API](https://open-meteo.com/)
