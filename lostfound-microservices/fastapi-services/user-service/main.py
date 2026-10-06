import os
from contextlib import contextmanager

import mysql.connector
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

app = FastAPI(
    title="Lost & Found - User Service",
    description="User management microservice",
    version="1.1.0"
)

# Allow the Swagger UI (served on another port) to call this API from the browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Data model for creating a user
class UserCreate(BaseModel):
    fullname: str
    usn: str
    department: str
    email: str
    mobile: str
    password: str
    role: str = "student"


@app.get("/health")
def health():
    return {"service": "user-service", "status": "ok"}


# 1. GET - All users
@app.get("/users")
def get_users():
    with db_cursor() as cursor:
        cursor.execute("SELECT id, fullname FROM users")
        users = cursor.fetchall()

    return {"count": len(users), "users": users}


# 2. GET - User details by ID
@app.get("/users/{user_id}")
def get_user(user_id: int):
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, fullname, usn, department,
                   email, mobile, role, created_at
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        )
        user = cursor.fetchone()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return user


# 3. POST - Create a new user
@app.post("/users", status_code=201)
def create_user(user: UserCreate):
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO users
            (fullname, usn, department, email, mobile, password, role)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user.fullname,
                user.usn,
                user.department,
                user.email,
                user.mobile,
                user.password,
                user.role,
            ),
        )
        new_user_id = cursor.lastrowid

    return {"message": "User created successfully", "user_id": new_user_id}
