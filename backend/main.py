import os
import uuid
import bcrypt
from datetime import datetime, timedelta
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, Depends, Cookie, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from jose import jwt, JWTError
from langgraph.types import Command

from agent import graph
from tools import supabase, analyse_issue, encrypt_token

load_dotenv()

app = FastAPI()

_FRONTEND_URL = os.getenv("FRONTEND_URL", "")
_origins = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:5501",
    "http://127.0.0.1:5501",
]
if _FRONTEND_URL:
    _origins.append(_FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_FRONTEND_URL or _origins,  # in prod, only allow the real frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
JWT_SECRET    = os.getenv("JWT_SECRET", "changeme")
COOKIE_SECURE = os.getenv("ENV", "dev") == "production"

# ── Auth helpers ──────────────────────────────────────────────────────────────

def make_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(days=7),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def current_user(token: str = Cookie(None)) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail="Not logged in")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = supabase.table("users").select("*").eq("id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=401, detail="User not found")
    return result.data[0]

# ── Request models ────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email:        str
    password:     str
    github_token: str = ""   # optional — empty means lite mode

class GenerateCommentRequest(BaseModel):
    title: str
    body:  str

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
        "id":            str(uuid.uuid4()),
        "email":         body.email,
        "password_hash": hashed,
        "github_token":  encrypt_token(body.github_token),
    }
    supabase.table("users").insert(user).execute()

    response = JSONResponse({"ok": True})
    response.set_cookie(
        key="token",
        value=make_token(user["id"]),
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=7 * 24 * 3600,
    )
    return response

@app.post("/login")
def login(body: LoginRequest):
    result = supabase.table("users").select("*").eq("email", body.email).execute()
    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = result.data[0]
    if not bcrypt.checkpw(body.password.encode(), user["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    response = JSONResponse({"ok": True})
    response.set_cookie(
        key="token",
        value=make_token(user["id"]),
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=7 * 24 * 3600,
    )
    return response

@app.post("/logout")
def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie("token")
    return response




# ── Triage routes ─────────────────────────────────────────────────────────────

@app.post("/triage")
def start_triage(body: TriageRequest, user: dict = Depends(current_user)):
    thread_id = str(uuid.uuid4())
    config    = {"configurable": {"thread_id": thread_id}}

    mode = "full" if user.get("github_token") else "lite"

    graph.invoke({
        "repo":          body.repo,
        "user_id":       user["id"],
        "mode":          mode,
        "issues":        [],
        "fetched_count": 0,
        "classified":    [],
        "decisions":     [],
        "review_index":  0,
    }, config=config)

    return {"thread_id": thread_id, "mode": mode}



@app.get("/status/{thread_id}")
def get_status(thread_id: str, user: dict = Depends(current_user)):
    config = {"configurable": {"thread_id": thread_id}}
    state  = graph.get_state(config)

    classified   = state.values.get("classified", [])
    decisions    = state.values.get("decisions", [])
    review_index = state.values.get("review_index", 0)

    # merge decisions into classified so frontend knows posted/skipped/pending
    merged = []
    for i, item in enumerate(classified):
        posted = decisions[i] if i < len(decisions) else None
        merged.append({**item, "posted": posted})

    pending = None
    if state.next and "approval" in state.next and review_index < len(classified):
        item    = classified[review_index]
        pending = {
            "issue":          item["issue"],
            "comment":        item["comment"],
            "classification": item["classification"],
            "severity":       item["severity"],
        }

    return {
        "status":        "waiting" if pending else "done",
        "mode":          state.values.get("mode", "full"),
        "pending":       pending,
        "classified":    merged,
        "fetched_count": state.values.get("fetched_count", 0),
    }

@app.post("/approve")
def approve(body: ApproveRequest, user: dict = Depends(current_user)):
    config = {"configurable": {"thread_id": body.thread_id}}
    graph.invoke(Command(resume=body.approved), config=config)
    return {"ok": True}

@app.post("/generate-comment")
def generate_comment(body: GenerateCommentRequest, _user: dict = Depends(current_user)):
    issue  = {"title": body.title, "body": body.body}
    result = analyse_issue(issue)
    return {"comment": result["comment"]}