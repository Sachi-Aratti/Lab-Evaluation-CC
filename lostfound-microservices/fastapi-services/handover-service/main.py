import os
from contextlib import contextmanager

import mysql.connector
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Database settings come from environment variables (set in docker-compose.yml)
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "db"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "college_lost_found"),
    "connection_timeout": 5,
}


@contextmanager
def db_cursor(commit: bool = False):
    """Open a connection + dict cursor, always close them, and turn
    database problems into clean HTTP errors instead of a raw 500."""
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        try:
            yield cursor
            if commit:
                conn.commit()
        finally:
            cursor.close()
    except mysql.connector.IntegrityError:
        raise HTTPException(status_code=409, detail="Duplicate or invalid data")
    except mysql.connector.Error:
        raise HTTPException(status_code=503, detail="Database unavailable")
    finally:
        if conn is not None and conn.is_connected():
            conn.close()

app = FastAPI(
    title="Lost & Found - Handover Service",
    description="Handover management microservice",
    version="1.1.0"
)

# Allow the Swagger UI (served on another port) to call this API from the browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"service": "handover-service", "status": "ok"}


# 1. GET - All handovers
@app.get("/handovers")
def get_handovers():
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, item_name, claimant_name,
                   claimant_phone, status
            FROM items
            WHERE claimant_name IS NOT NULL
            """
        )
        handovers = cursor.fetchall()

    return {"count": len(handovers), "handovers": handovers}


# 2. GET - Handover details by item ID
@app.get("/handovers/{item_id}")
def get_handover(item_id: int):
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, item_name, claimant_name,
                   claimant_phone, status
            FROM items
            WHERE id = %s
              AND claimant_name IS NOT NULL
            """,
            (item_id,),
        )
        handover = cursor.fetchone()

    if handover is None:
        raise HTTPException(status_code=404, detail="Handover details not found")

    return handover
