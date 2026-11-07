import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.generated.models import HealthResponse

app = FastAPI(title="Календарь звонков")


@app.get("/health", response_model=HealthResponse, operation_id="getHealth")
def get_health() -> HealthResponse:
    return HealthResponse(status="ok")


static_dir = Path(os.environ.get("STATIC_DIR", Path(__file__).parent.parent / "dist"))
if static_dir.is_dir():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
