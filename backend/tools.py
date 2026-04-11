import os
from dotenv import load_dotenv
from github import Github
from sentence_transformers import SentenceTransformer
from supabase import create_client
from groq import Groq

load_dotenv()

# ── Clients ──────────────────────────────────────────────────────────────────

embedder = SentenceTransformer("all-MiniLM-L6-v2")
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
groq     = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ── GitHub ────────────────────────────────────────────────────────────────────

def fetch_issues(repo_name: str, github_token: str = "", max_issues: int = 20) -> list[dict]:
    gh   = Github(github_token) if github_token else Github()
    repo = gh.get_repo(repo_name)
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
    return embedder.encode(text).tolist()

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