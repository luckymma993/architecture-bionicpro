import os
from datetime import date, timedelta
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .auth import current_user
from .olap import fetch_report

app = FastAPI(title="BionicPRO Reports API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["GET"],
    allow_headers=["Authorization"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/reports")
def reports(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    user: dict = Depends(current_user),
):
    if date_to is None:
        date_to = date.today()
    if date_from is None:
        date_from = date_to - timedelta(days=6)
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from позже date_to")
    if (date_to - date_from).days > 92:
        raise HTTPException(status_code=400, detail="Период не больше 93 дней")
    return fetch_report(user["username"], date_from, date_to)
