import os
import logging
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool
from langgraph.types import interrupt
from dotenv import load_dotenv
import tools

load_dotenv()
logger = logging.getLogger(__name__)

# ── State ─────────────────────────────────────────────────────────────────────

class State(TypedDict):
    repo:          str
    user_id:       str          # used to fetch github_token from DB at runtime (never stored in state)
    mode:          str          # "full" (has token) | "lite" (no token, no storage)
    issues:        list[dict]   # raw issues fetched from GitHub
    fetched_count: int
    classified:    list[dict]   # [{issue, classification, severity, comment, duplicate_of}] — never mutated after classify_all
    review_index:  int          # which classified issue is next for approval
    decisions:     list         # parallel to classified: True=posted, False=skipped, grows as user reviews
    approved:      Optional[bool]

# ── Nodes ─────────────────────────────────────────────────────────────────────

def fetch_node(state: State) -> dict:
    github_token = tools.get_github_token(state["user_id"])
    issues = tools.fetch_issues(state["repo"], github_token)
    return {"issues": issues, "fetched_count": len(issues), "classified": [], "decisions": [], "review_index": 0}

def classify_all_node(state: State) -> dict:
    classified = []
    for issue in state["issues"]:
        # lite mode: skip duplicate detection (no DB reads, no storage)
        dup_of = tools.find_duplicate(issue) if state["mode"] == "full" else None
        if dup_of:
            entry = {
                "issue":          issue,
                "classification": "duplicate",
                "severity":       "low",
                "comment":        f"This looks like a duplicate of #{dup_of}.",
                "duplicate_of":   dup_of,
            }
        else:
            result = tools.analyse_issue(issue)
            entry = {
                "issue":          issue,
                "classification": result["classification"],
                "severity":       result["severity"],
                "comment":        result["comment"],
                "duplicate_of":   None,
            }
        classified.append(entry)
    return {"classified": classified}

def approval_node(state: State) -> dict:
    item     = state["classified"][state["review_index"]]
    approved = interrupt({
        "issue":          item["issue"],
        "comment":        item["comment"],
        "classification": item["classification"],
        "severity":       item["severity"],
    })
    return {"approved": approved}

def post_node(state: State) -> dict:
    idx  = state["review_index"]
    item = state["classified"][idx]

    if state["approved"]:
        github_token = tools.get_github_token(state["user_id"])
        tools.post_comment(
            state["repo"],
            github_token,
            item["issue"]["number"],
            item["comment"],
        )
        if not item["duplicate_of"]:
            tools.store_issue(state["repo"], item["issue"])

    return {
        "decisions":    state["decisions"] + [state["approved"]],
        "review_index": idx + 1,
        "approved":     None,
    }

# ── Routing ───────────────────────────────────────────────────────────────────

def has_issues(state: State) -> str:
    return "continue" if state.get("fetched_count", 0) > 0 else END

def after_classify(state: State) -> str:
    # lite mode ends here — no approval loop, no posting
    return END if state["mode"] == "lite" else "approval"

def has_more_to_review(state: State) -> str:
    return "continue" if state["review_index"] < len(state["classified"]) else END

# ── Graph ─────────────────────────────────────────────────────────────────────

def build_checkpointer():
    checkpoint_backend = os.getenv("LANGGRAPH_CHECKPOINTS", "").lower()
    env = os.getenv("ENV", "dev").lower()

    if checkpoint_backend in {"memory", "inmemory", "in-memory"} or (
        env != "production" and checkpoint_backend != "postgres"
    ):
        logger.info("Using in-memory LangGraph checkpoints.")
        return MemorySaver()

    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        logger.warning("SUPABASE_DB_URL is not set; using in-memory LangGraph checkpoints.")
        return MemorySaver()

    pool = ConnectionPool(
        db_url,
        min_size=0,
        max_size=10,
        timeout=5,
        kwargs={"autocommit": True, "prepare_threshold": None},
    )
    checkpointer = PostgresSaver(pool)
    try:
        checkpointer.setup()
        return checkpointer
    except Exception as exc:
        pool.close()
        logger.warning(
            "Could not initialize Postgres checkpoints; using in-memory LangGraph checkpoints. %s",
            exc,
        )
        return MemorySaver()


checkpointer = build_checkpointer()

builder = StateGraph(State)

builder.add_node("fetch",        fetch_node)
builder.add_node("classify_all", classify_all_node)
builder.add_node("approval",     approval_node)
builder.add_node("post",         post_node)

builder.set_entry_point("fetch")

builder.add_conditional_edges("fetch", has_issues, {
    "continue": "classify_all",
    END:        END,
})
builder.add_conditional_edges("classify_all", after_classify, {
    "approval": "approval",
    END:        END,
})
builder.add_edge("approval",     "post")
builder.add_conditional_edges("post", has_more_to_review, {
    "continue": "approval",
    END:        END,
})

graph = builder.compile(checkpointer=checkpointer, interrupt_before=["approval"])
