# Backend

FastAPI API for CSV ingestion, deterministic OTA calculation, SLA incident detection, and SQLAlchemy persistence using SQLite locally or PostgreSQL in cloud environments.

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

## Cloud PostgreSQL

Set the private connection string in `backend/.env` or in the cloud service's environment variables:

```dotenv
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require
```

Provider URLs beginning with `postgres://` or `postgresql://` are normalized automatically to the Psycopg 3 SQLAlchemy driver. Percent-encode special characters in usernames and passwords. Keep the real URL out of Git.

Restart the API after changing the variable. Application startup creates missing tables in an empty PostgreSQL database. This does not copy records from `mobility.db`; either upload the source datasets into the new database or migrate the existing rows separately. Set `REFERENCE_DATA_DIR` only where the MoveInSync reference CSVs are available so matching safety alerts and feedback can be synchronized.
