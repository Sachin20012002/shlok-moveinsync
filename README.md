# SHLOK - MoveInSync Hackathon

**Bessemer Tech Catalyst 2026**

**Track:** MoveInSync

## Overview

Working first milestone for an agentic enterprise mobility layer. A transport manager can upload normalized trip data, inspect deterministic OTA metrics against a 90% SLA, review an automatically created incident, and acknowledge it.

## Run Locally

Prerequisites: Python 3.11+ and Node.js 20+.

Open two PowerShell terminals from the repository root.

Terminal 1, backend:

```powershell
Set-Location .\backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env -ErrorAction SilentlyContinue
python -m uvicorn app.main:app --reload
```

Terminal 2, frontend:

```powershell
Set-Location .\frontend
npm install
Copy-Item .env.example .env.local -ErrorAction SilentlyContinue
npm run dev
```

Open `http://localhost:3000`. Select **Upload trip CSV** and choose `sample-data/ota-breach-demo.csv`. The upload produces 75% OTA against the 90% SLA, creates one critical incident, and exposes the acknowledgment action.

Useful URLs:

- Frontend: `http://localhost:3000`
- Backend health: `http://localhost:8000/health`
- Swagger API: `http://localhost:8000/docs`

SQLite data is stored locally in `backend/mobility.db`. Each new upload replaces the previous demo dataset so metrics remain deterministic.

## Implemented API

- `GET /health`
- `POST /api/datasets/upload`
- `GET /api/dashboard`
- `GET /api/incidents`
- `GET /api/incidents/{id}`
- `POST /api/incidents/{id}/acknowledge`

## Calculation Rules

- The OTA SLA is 90%.
- Arrival up to and including five minutes late is on time.
- OTA is evaluated only after at least 10 completed trips.
- Duplicate open OTA incidents are prevented.
- Python calculates official metrics; AI is intentionally deferred until this core flow is stable.

## Team SHLOK

- **S**achin
- **H**arsh
- **L**akshmi
- **O**viya
- **K**rithika

## Development

The `main` branch should contain integrated, working code.

Development should happen on feature branches and changes should be merged into `main` through pull requests.
