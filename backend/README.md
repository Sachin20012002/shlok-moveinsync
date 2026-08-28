# Backend

Minimal FastAPI application for the SHLOK MoveInSync infrastructure smoke test.

## Local setup

From inside `backend/`, create and activate a virtual environment, then install the dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`.
