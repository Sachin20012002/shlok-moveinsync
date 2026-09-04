# Backend

FastAPI API for CSV ingestion, deterministic OTA calculation, SLA incident detection, and SQLite persistence.

## Local setup

From PowerShell inside `backend/`:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

## Run

```powershell
python -m uvicorn app.main:app --reload
```

API: `http://localhost:8000`  
Swagger: `http://localhost:8000/docs`

Run tests with `python -m pytest -q`.
