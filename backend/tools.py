import os
import requests
from dotenv import load_dotenv
from github import Github
from github.GithubException import GithubException, UnknownObjectException
from supabase import create_client
from groq import Groq
from cryptography.fernet import Fernet

load_dotenv()

# ── Clients ──────────────────────────────────────────────────────────────────

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
groq     = Groq(api_key=os.getenv("GROQ_API_KEY"))
fernet   = Fernet(os.getenv("ENCRYPTION_KEY").encode())

HF_API_KEY = os.getenv("HF_API_KEY", "")
_HF_URL    = "https://router.huggingface.co/hf-inference/models/sentence-transformers/all-MiniLM-L6-v2/pipeline/feature-extraction"

# ── Token encryption ──────────────────────────────────────────────────────────

def encrypt_token(token: str) -> str:
    if not token:
        return ""
    return fernet.encrypt(token.encode()).decode()

def decrypt_token(encrypted: str) -> str:
    if not encrypted:
        return ""
    try:
        return fernet.decrypt(encrypted.encode()).decode()
    except Exception:
        return ""  # token was stored before encryption was added

def get_github_token(user_id: str) -> str:
    result = supabase.table("users").select("github_token").eq("id", user_id).execute()
    if not result.data:
        return ""
    return decrypt_token(result.data[0].get("github_token", ""))

# ── GitHub ────────────────────────────────────────────────────────────────────

def fetch_issues(repo_name: str, github_token: str = "", max_issues: int = 20) -> list[dict]:
    if "/" not in repo_name:
        raise ValueError("Enter the repository as owner/repo, for example facebook/react.")

    gh   = Github(github_token) if github_token else Github()
    try:
        repo = gh.get_repo(repo_name)
    except UnknownObjectException as exc:
        raise ValueError(
            "Repository not found. Check the owner/repo name, or add a GitHub token for private repositories."
        ) from exc
    except GithubException as exc:
        raise RuntimeError(f"GitHub API error: {exc.data.get('message', exc.status)}") from exc

    issues = []
    for issue in repo.get_issues(state="open"):
        if issue.pull_request:
            continue
        issues.append({
            "number": issue.number,
            "title":  issue.title,
            "body":   (issue.body or "")[:500],  # trim long bodies
            "url":    issue.html_url,
        })
        if len(issues) >= max_issues:
            break
    return issues

def post_comment(repo_name: str, github_token: str, issue_number: int, body: str):
    repo = Github(github_token).get_repo(repo_name)
    repo.get_issue(issue_number).create_comment(body)

# ── Embeddings + Supabase ─────────────────────────────────────────────────────

def embed(text: str) -> list[float]:
    headers = {"Authorization": f"Bearer {HF_API_KEY}"} if HF_API_KEY else {}
    resp = requests.post(_HF_URL, headers=headers, json={"inputs": text}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    # HF returns [[...float...]] for sentence-transformers
    return data[0] if isinstance(data[0], list) else data

def find_duplicate(issue: dict, threshold: float = 0.88) -> int | None:
    vector = embed(issue["title"] + " " + issue["body"])
    result = supabase.rpc("match_issues", {
        "query_embedding": vector,
        "match_threshold": threshold,
        "match_count":     1,
    }).execute()
    if result.data:
        return result.data[0]["issue_number"]
    return None

def store_issue(repo: str, issue: dict):
    vector = embed(issue["title"] + " " + issue["body"])
    supabase.table("issue_embeddings").upsert({
        "repo":         repo,
        "issue_number": issue["number"],
        "embedding":    vector,
    }).execute()

# ── Groq ──────────────────────────────────────────────────────────────────────

def analyse_issue(issue: dict) -> dict:
    prompt = f"""Analyse this GitHub issue and respond in exactly this format:
classification: bug | feature | question
severity: critical | high | medium | low
comment: <a short triage comment to post on the issue>

Issue title: {issue['title']}
Issue body: {issue['body']}"""

    response = groq.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )

    text  = response.choices[0].message.content
    lines = {l.split(":")[0].strip(): l.split(":", 1)[1].strip()
             for l in text.strip().splitlines() if ":" in l}

    return {
        "classification": lines.get("classification", "unknown"),
        "severity":       lines.get("severity", "medium"),
        "comment":        lines.get("comment", text),
    }
