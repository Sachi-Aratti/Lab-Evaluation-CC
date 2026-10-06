import os
from contextlib import contextmanager

import mysql.connector
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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

# Other microservices, reached through the Docker network by service name
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:8000")
HANDOVER_SERVICE_URL = os.getenv("HANDOVER_SERVICE_URL", "http://handover-service:8000")

app = FastAPI(
    title="Lost & Found - Item Service",
    description="Lost and found item management microservice",
    version="1.1.0"
)

# Allow the Swagger UI (served on another port) to call this API from the browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Data model for creating an item
class ItemCreate(BaseModel):
    item_name: str
    description: str
    location: str
    reporter_name: str
    reporter_phone: str
    report_type: str
    status: str = "open"


def call_service(url: str, name: str) -> dict:
    """GET another microservice; map any failure to a 502 Bad Gateway."""
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError):
        raise HTTPException(status_code=502, detail=f"{name} is unavailable")


@app.get("/health")
def health():
    return {"service": "item-service", "status": "ok"}


# 1. GET - All items
@app.get("/items")
def get_items():
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, item_name, location,
                   report_type, status
            FROM items
            """
        )
        items = cursor.fetchall()

    return {"count": len(items), "items": items}


# 2. GET - Item details by ID
@app.get("/items/{item_id}")
def get_item(item_id: int):
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM items WHERE id = %s", (item_id,))
        item = cursor.fetchone()

    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    return item


# 3. POST - Create a new item
@app.post("/items", status_code=201)
def create_item(item: ItemCreate):
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO items
            (item_name, description, location,
             reporter_name, reporter_phone,
             report_type, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                item.item_name,
                item.description,
                item.location,
                item.reporter_name,
                item.reporter_phone,
                item.report_type,
                item.status,
            ),
        )
        new_item_id = cursor.lastrowid

    return {"message": "Item created successfully", "item_id": new_item_id}


# 4. GET - Inter-service communication (Item -> User + Handover)
@app.get("/item-summary/{item_id}")
def item_summary(item_id: int):
    # Item from this service's own database access
    item = get_item(item_id)

    # Call User Service and Handover Service using Docker service names
    users = call_service(f"{USER_SERVICE_URL}/users", "User Service")
    handovers = call_service(f"{HANDOVER_SERVICE_URL}/handovers", "Handover Service")

    return {
        "item": item,
        "user_service": users,
        "handover_service": handovers,
    }
