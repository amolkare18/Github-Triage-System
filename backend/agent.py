import os
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import interrupt
from dotenv import load_dotenv
import tools

load_dotenv()

# ── State ─────────────────────────────────────────────────────────────────────

class State(TypedDict):
    repo:           str
    github_token:   str
    issues:         list[dict]
    current_issue:  Optional[dict]
    duplicate_of:   Optional[int]
    classification: Optional[str]
    severity:       Optional[str]
    comment:        Optional[str]
    approved:       Optional[bool]
    results:        list[dict]

# ── Nodes ─────────────────────────────────────────────────────────────────────

def fetch_node(state: State) -> dict:
    issues = tools.fetch_issues(state["repo"], state["github_token"])
    return {"issues": issues, "results": []}

def duplicate_node(state: State) -> dict:
    issue     = state["issues"][0]
    dup_of    = tools.find_duplicate(issue)
    comment   = f"This looks like a duplicate of #{dup_of}." if dup_of else None
    return {
        "current_issue": issue,
        "duplicate_of":  dup_of,
        "comment":       comment,
    }

def analyse_node(state: State) -> dict:
    result = tools.analyse_issue(state["current_issue"])
    return {
        "classification": result["classification"],
        "severity":       result["severity"],
        "comment":        result["comment"],
    }

def approval_node(state: State) -> dict:
    # pauses here — resumes when /approve is called
    approved = interrupt({
        "issue":  state["current_issue"],
        "comment": state["comment"],
    })
    return {"approved": approved}

def post_node(state: State) -> dict:
    if state["approved"]:
        tools.post_comment(
            state["repo"],
            state["github_token"],
            state["current_issue"]["number"],
            state["comment"],
        )
        if not state["duplicate_of"]:
            tools.store_issue(state["repo"], state["current_issue"])

    # log result and pop the processed issue
    results = state["results"] + [{
        "issue":   state["current_issue"],
        "comment": state["comment"],
        "posted":  state["approved"],
    }]
    remaining = state["issues"][1:]

    return {
        "results":        results,
        "issues":         remaining,
        "current_issue":  None,
        "duplicate_of":   None,
        "classification": None,
        "severity":       None,
        "comment":        None,
        "approved":       None,
    }

# ── Routing ───────────────────────────────────────────────────────────────────

def is_duplicate(state: State) -> str:
    return "duplicate" if state["duplicate_of"] else "new"

def has_more_issues(state: State) -> str:
    return "continue" if state["issues"] else END

# ── Graph ─────────────────────────────────────────────────────────────────────

checkpointer = PostgresSaver.from_conn_string(os.getenv("SUPABASE_DB_URL"))

builder = StateGraph(State)

builder.add_node("fetch",    fetch_node)
builder.add_node("duplicate", duplicate_node)
builder.add_node("analyse",  analyse_node)
builder.add_node("approval", approval_node)
builder.add_node("post",     post_node)

builder.set_entry_point("fetch")

builder.add_edge("fetch", "duplicate")
builder.add_conditional_edges("duplicate", is_duplicate, {
    "duplicate": "approval",
    "new":       "analyse",
})
builder.add_edge("analyse", "approval")
builder.add_edge("approval", "post")
builder.add_conditional_edges("post", has_more_issues, {
    "continue": "duplicate",
    END:        END,
})

graph = builder.compile(checkpointer=checkpointer, interrupt_before=["approval"])