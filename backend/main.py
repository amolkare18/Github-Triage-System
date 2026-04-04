import os
import uuid
import bcrypt
from datetime import datetime, timedelta
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import jwt, JWTError

from agent import graph
from tools import supabase

load_dotenv()

app = FastAPI()
security = HTTPBearer()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

JWT_SECRET = os.getenv("JWT_SECRET", "changeme")

# ── Auth helpers ──────────────────────────────────────────────────────────────

def make_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(days=7),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        user_id = payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = supabase.table("users").select("*").eq("id", user_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=401, detail="User not found")
    return result.data

# ── Request models ────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email:        str
    password:     str
    github_token: str

class LoginRequest(BaseModel):
    email:    str
    password: str

class TriageRequest(BaseModel):
    repo: str

class ApproveRequest(BaseModel):
    thread_id: str
    approved:  bool

# ── Auth routes ───────────────────────────────────────────────────────────────

@app.post("/signup")
def signup(body: SignupRequest):
    existing = supabase.table("users").select("id").eq("email", body.email).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    user   = {
        "id":           str(uuid.uuid4()),
        "email":        body.email,
        "password_hash": hashed,
        "github_token": body.github_token,
    }
    supabase.table("users").insert(user).execute()
    return {"token": make_token(user["id"])}

@app.post("/login")
def login(body: LoginRequest):
    result = supabase.table("users").select("*").eq("email", body.email).single().execute()
    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = result.data
    if not bcrypt.checkpw(body.password.encode(), user["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {"token": make_token(user["id"])}

# ── Triage routes ─────────────────────────────────────────────────────────────

@app.post("/triage")
def start_triage(body: TriageRequest, user: dict = Depends(current_user)):
    thread_id = str(uuid.uuid4())
    config    = {"configurable": {"thread_id": thread_id}}

    graph.invoke({
        "repo":         body.repo,
        "github_token": user["github_token"],
        "issues":       [],
        "results":      [],
    }, config=config)

    return {"thread_id": thread_id}

@app.get("/status/{thread_id}")
def get_status(thread_id: str, user: dict = Depends(current_user)):
    config = {"configurable": {"thread_id": thread_id}}
    state  = graph.get_state(config)

    # check if graph is paused at approval
    pending = None
    if state.next and "approval" in state.next:
        pending = {
            "issue":   state.values.get("current_issue"),
            "comment": state.values.get("comment"),
        }

    return {
        "status":  "waiting" if pending else "done",
        "pending": pending,
        "results": state.values.get("results", []),
    }

@app.post("/approve")
def approve(body: ApproveRequest, user: dict = Depends(current_user)):
    config = {"configurable": {"thread_id": body.thread_id}}

    graph.invoke(body.approved, config=config)

    return {"ok": True}