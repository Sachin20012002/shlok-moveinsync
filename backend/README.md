# SHLOK Backend

The backend is a **FastAPI modular monolith** that owns CSV ingestion, deterministic operational metrics, proactive incident detection, incident lifecycle state, analytical dashboards, persistence, and the optional model-backed mobility agent.

Python services and database records are the source of truth. The conversational layer is advisory and uses read-only analytical tools.

## Technology

- Python 3.11+
- FastAPI and Uvicorn
- Pydantic settings and request/response schemas
- SQLAlchemy 2
- SQLite for local development
- PostgreSQL through Psycopg 3 for cloud environments
- HTTPX for optional AI-provider calls
- Pytest

## Setup

```powershell
Set-Location .\backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
python -m uvicorn app.main:app --reload
```

For Bash-compatible shells:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --reload
```

Useful local URLs:

- API: <http://localhost:8000>
- Health: <http://localhost:8000/health>
- OpenAPI/Swagger: <http://localhost:8000/docs>

## Configuration

Settings are loaded from `backend/.env`.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | Neon PostgreSQL in the active environment; SQLite fallback in code | SQLAlchemy database URL |
| `REFERENCE_DATA_DIR` | `../MoveInSync - Anonymised Trip-Log Dataset` | Optional directory containing MoveInSync reference exports |
| `ALLOWED_ORIGINS` | Local port 3000 origins | Comma-separated CORS allowlist |
| `OTA_SLA` | `90` | Overall and vendor OTA target percentage |
| `OTA_GRACE_MINUTES` | `5` | Maximum lateness still counted as on time |
| `MINIMUM_COMPLETED_TRIPS` | `10` | Minimum volume for overall OTA evaluation |
| `VENDOR_MINIMUM_COMPLETED_TRIPS` | `3` | Minimum volume for vendor OTA evaluation |
| `GPS_AVAILABILITY_SLA` | `95` | GPS availability target percentage |
| `INCIDENT_REOPEN_DROP_POINTS` | `5` | Deterioration needed to reopen an acknowledged incident |
| `AI_PROVIDER` | `sarvam` | Active AI-provider adapter |
| `AI_API_KEY` | empty | Optional provider credential; empty selects grounded-local mode |
| `AI_BASE_URL` | `https://api.sarvam.ai` | Sarvam API base URL |
| `AI_MODEL` | `sarvam-105b` | Active Sarvam model name |

The active database is a Neon PostgreSQL instance in AWS Asia Pacific (Singapore). Keep its full connection string, password, and the Sarvam API key out of version control. `backend/.env.example` uses placeholders and contains no credentials.

## Internal architecture

```text
app/main.py                       FastAPI lifecycle and HTTP controllers
app/core/config.py                Environment-backed settings
app/database/
  connection.py                  Engine and session factory
  migrations.py                  Startup table/index compatibility migration
  models.py                      SQLAlchemy entities
app/schemas/
  api.py                         API contracts
  trip.py                        Normalized upload row validation
app/services/
  ingestion.py                   CSV normalization and persistence
  metrics.py                     Deterministic OTA calculation
  detection.py                   Incident rules and lifecycle transitions
  operations.py                  Operational workspace aggregation
  operations_analytics.py        Date-scoped trends and incident evidence
  data_dashboards.py             Filtered queries, facets, paging, and export
  reference_data.py              Startup import/enrichment from source exports
  agent.py                       Grounding and SSE/provider orchestration
  agent_tools.py                 Read-only analytical tool catalog
tests/                            Unit and end-to-end API tests
```

The request flow for a CSV upload is:

```mermaid
sequenceDiagram
    participant UI as Frontend
    participant API as FastAPI
    participant ING as Ingestion
    participant DET as Detection
    participant DB as Database
    UI->>API: POST /api/datasets/upload
    API->>ING: Validate and normalize CSV
    ING->>DB: Insert upload and unique trips
    ING->>DET: Evaluate current operation
    DET->>DB: Store metric snapshot
    DET->>DB: Open/update/resolve incidents and events
    API-->>UI: Upload counts and incident-created flag
```

## Data model

| Entity | Responsibility |
|---|---|
| `DatasetUpload` | File-level import counts and timestamp |
| `Trip` | Normalized operational trip record |
| `SafetyAlert` | Alert/reference events linked logically by `trip_id` |
| `TripFeedback` | Route, driver, cab, safety, and marshal ratings |
| `MetricSnapshot` | Official aggregate metrics after an evaluated upload |
| `Incident` | Current lifecycle state and operational evidence |
| `IncidentEvent` | Append-only incident history |

Uploads append to the database and `Trip.trip_id` is globally unique. The current snapshot covers all loaded completed trips; incident history is retained across uploads.

At startup the application creates missing tables, applies its compatibility migration, imports matching source records when reference exports are available, and computes a missing snapshot for the latest upload. The repository currently includes the source dictionaries and problem statement; place the actual exports under `REFERENCE_DATA_DIR` to enable the optional synchronization.

## Ingestion

`POST /api/datasets/upload` accepts UTF-8 CSV files in either format:

1. The normalized SHLOK schema used by `sample-data/*.csv`.
2. A MoveInSync ride export containing the required export columns such as `trip_id`, `vendor_id`, `product_type`, `shift_type`, planned/actual end epochs, distance, and employee count.

The service strips comma formatting from MoveInSync trip IDs and numeric values, converts epochs, distinguishes invalid and skipped rows, batches inserts, and rejects trip IDs already stored in the database.

## Incident engine

- Overall OTA, per-vendor OTA, and GPS availability are evaluated automatically after ingestion.
- A trip is on time when it arrives within the configured grace window.
- Low-volume OTA results are marked as insufficient rather than generating misleading incidents.
- Severity derives from the gap to the applicable SLA.
- One unresolved incident is maintained per operational rule, avoiding duplicate open alerts.
- Acknowledged incidents reopen when performance drops by the configured number of points or severity increases.
- Meeting the target resolves the current incident.
- Every meaningful transition is recorded as an `IncidentEvent`.

## API overview

| Method and path | Purpose |
|---|---|
| `GET /health` | Service health |
| `POST /api/datasets/upload` | Import trips and evaluate signals |
| `GET /api/dashboard` | Compact latest snapshot |
| `GET /api/operations` | Operational workspace aggregation |
| `GET /api/operations/analytics` | Date-scoped summary, weekly trend, vendors, and shifts |
| `GET /api/dashboards/{trips|feedback|safety-alerts}` | Filtered data dashboards |
| `GET /api/dashboards/{name}/export` | Export the active filters as CSV |
| `GET /api/incidents` | List incidents by attention and recency |
| `GET /api/incidents/{id}` | Incident details |
| `GET /api/incidents/{id}/events` | Lifecycle history |
| `GET /api/incidents/{id}/related-trips` | Paginated incident evidence |
| `POST /api/incidents/{id}/acknowledge` | Record manager acknowledgment |
| `GET /api/incidents/{id}/email-draft` | Create a draft after acknowledgment |
| `POST /api/incidents/{id}/email-sent` | Record that the manager sent the draft |
| `GET /api/agent/status` | Current agent mode |
| `POST /api/agent/chat` | Stream grounded responses over SSE |
| `POST /api/tools/{tool_name}` | Execute a registered read-only analytics tool |

The communication workflow generates and records a draft; it does not call an external email provider.

## Mobility agent

Without `AI_API_KEY`, the backend uses fast deterministic `grounded-local` answers. With the active Sarvam configuration, `sarvam-105b` can call the same read-only analytics used by the API. Tools cover:

- trip details, delays, statistics, dates, and dimension rankings;
- vendor comparisons and issue summaries;
- safety alerts and grouped safety performance;
- employee impact and no-shows;
- feedback summaries;
- historical and explicit period comparisons.

Peer comparison explicitly reports unavailable until an external benchmark is configured. The chat endpoint emits `context`, `token`, `done`, or `error` server-sent events and never changes incident state.

## Tests

```powershell
Set-Location .\backend
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

The suite covers calculation boundaries, ingestion and duplicate protection, incident creation/acknowledgment/reopening, reference-format uploads, dashboard filtering and pagination, date-scoped analytics, database URL normalization, SSE behavior, and provider tool calling.

## PostgreSQL deployment

The active deployment uses Neon. Set its private Psycopg 3 SQLAlchemy URL with placeholders replaced only inside `.env` or a secret manager:

```dotenv
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@NEON_HOST/DATABASE?sslmode=require&channel_binding=require
```

URLs beginning with `postgres://` or `postgresql://` are normalized automatically. Percent-encode special characters in credentials.

Startup creates missing tables in an empty PostgreSQL database, but it does not copy records from local `mobility.db`. Upload or migrate data separately. For production evolution, replace the startup compatibility migration with a managed migration tool and add tenant scoping, authentication, background ingestion, and durable notification delivery.

## Related documentation

- [Project overview and demo](../README.md)
- [Frontend setup](../frontend/README.md)
- [MoveInSync dataset guide](../MoveInSync%20-%20Anonymised%20Trip-Log%20Dataset/Dictionary/README.md)
- [MoveInSync problem statement](../MoveInSync%20-%20Anonymised%20Trip-Log%20Dataset/Dictionary/problem_explanation_7qdzf3jxklt.pdf)
