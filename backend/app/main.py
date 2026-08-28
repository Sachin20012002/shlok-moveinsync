import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

default_allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
configured_origins = os.getenv("ALLOWED_ORIGINS")
allowed_origins = (
    [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
    if configured_origins
    else default_allowed_origins
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "SHLOK MoveInSync backend is running"}


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "shlok-moveinsync-backend",
    }
