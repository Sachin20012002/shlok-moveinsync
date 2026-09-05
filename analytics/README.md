# Local analytics database

This directory contains the PostgreSQL schema and repeatable CSV importer for the hackathon analytics data layer. It loads trips, employee trip legs, alerts, bills, feedback, and two demo SLA settings.

## Docker setup (recommended)

The Docker database runs on port `5433`, so it does not conflict with an installed PostgreSQL service on `5432`. Its credentials live in the Git-ignored `.env.local` file.

Create the local environment file and replace `CHOOSE_A_LOCAL_PASSWORD` in both places with the same password:

```powershell
Copy-Item .\analytics\.env.example .\analytics\.env.local
notepad .\analytics\.env.local
```

Start PostgreSQL and wait for it to become healthy:

```powershell
docker compose -f .\analytics\docker-compose.yml up -d --wait
```

Run the migration:

```powershell
docker compose -f .\analytics\docker-compose.yml exec -T postgres psql -U shlok -d shlok_analytics -v ON_ERROR_STOP=1 -f /migrations/001_analytics_schema.sql
docker compose -f .\analytics\docker-compose.yml exec -T postgres psql -U shlok -d shlok_analytics -v ON_ERROR_STOP=1 -f /migrations/002_employee_feedback.sql
docker compose -f .\analytics\docker-compose.yml exec -T postgres psql -U shlok -d shlok_analytics -v ON_ERROR_STOP=1 -f /migrations/003_trip_quality.sql
```

Load the environment and import the CSVs:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r .\analytics\requirements.txt
Get-Content .\analytics\.env.local | ForEach-Object {
    if ($_ -match '^([^#][^=]*)=(.*)$') { Set-Item -Path "Env:$($matches[1])" -Value $matches[2] }
}
.\backend\.venv\Scripts\python.exe .\analytics\import_data.py --data-dir 'C:\path\to\dataset' --datasets all
```

Stop PostgreSQL without deleting the database:

```powershell
docker compose -f .\analytics\docker-compose.yml stop
```

## Installed PostgreSQL alternative

Use this only if you prefer the PostgreSQL 17 Windows service on port `5432`.

### Prerequisites

- PostgreSQL 17 running on `localhost:5432`
- Python virtual environment with `analytics/requirements.txt` installed
- The supplied MoveInSync dataset directory

Keep credentials outside Git. In PowerShell, set them only for the current terminal session:

```powershell
$env:PGPASSWORD = '<your local postgres password>'
$env:ANALYTICS_DATABASE_URL = 'postgresql://postgres:<url-encoded-password>@localhost:5432/shlok_analytics'
```

## Create the database

```powershell
& 'C:\Program Files\PostgreSQL\17\bin\createdb.exe' -h localhost -U postgres shlok_analytics
```

## Run the migration

```powershell
& 'C:\Program Files\PostgreSQL\17\bin\psql.exe' -h localhost -U postgres -d shlok_analytics -v ON_ERROR_STOP=1 -f .\analytics\migrations\001_analytics_schema.sql
& 'C:\Program Files\PostgreSQL\17\bin\psql.exe' -h localhost -U postgres -d shlok_analytics -v ON_ERROR_STOP=1 -f .\analytics\migrations\002_employee_feedback.sql
& 'C:\Program Files\PostgreSQL\17\bin\psql.exe' -h localhost -U postgres -d shlok_analytics -v ON_ERROR_STOP=1 -f .\analytics\migrations\003_trip_quality.sql
```

## Install and run the importer

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r .\analytics\requirements.txt
.\backend\.venv\Scripts\python.exe .\analytics\import_data.py --data-dir 'C:\path\to\dataset' --datasets all
```

The importer uses PostgreSQL `COPY` and replaces only the selected tables in one transaction. It retains the SLA configuration, skips rows without valid primary identifiers, and prints validation and join-coverage results. The trip primary key is `(trip_id, trip_date)` because 6,753 identifiers are reused across different months in the supplied data; this preserves every valid trip row.

To replace selected datasets without touching the others:

```powershell
.\backend\.venv\Scripts\python.exe .\analytics\import_data.py --data-dir 'C:\path\to\dataset' --datasets employees feedback
```

Valid dataset names are `trips`, `alerts`, `bills`, `employees`, and `feedback`.

To validate source identifiers and row counts without connecting to PostgreSQL:

```powershell
.\backend\.venv\Scripts\python.exe .\analytics\import_data.py --data-dir 'C:\path\to\dataset' --source-check
```

## Size-limited Neon demo database

`import_demo_subset.py` replaces the legacy backend tables and loads a coherent
two-week analytics subset into the `public` schema. The default window is
2026-07-18 through 2026-07-31. Child datasets are retained only when they match
a selected trip, so joins remain useful and the result stays below Neon's 500 MB
allowance.

Load `ANALYTICS_DATABASE_URL` from a Git-ignored environment file, then run:

```powershell
.\backend\.venv\Scripts\python.exe .\analytics\import_demo_subset.py `
    --data-dir 'C:\path\to\dataset' `
    --reset-existing
```

The reset flag is mandatory because this command drops `dataset_uploads`,
`metric_snapshots`, `incidents`, `incident_events`, and any existing versions of
the six analytics tables. PostgreSQL performs the reset, schema creation, data
load, and validation in one transaction; a failure rolls back the replacement.
