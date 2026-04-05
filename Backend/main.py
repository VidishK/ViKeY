"""
ViKeY Backend - Real API Integration
FastAPI backend with Auth0 Token Vault + GitHub + Notion
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import httpx
import os
import json
import secrets
from datetime import date
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="ViKeY API")

# CORS - allows frontend to talk to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── ENV VARS ──────────────────────────────────────────────
AUTH0_DOMAIN        = os.getenv("AUTH0_DOMAIN")
AUTH0_CLIENT_ID     = os.getenv("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
AUTH0_AUDIENCE      = os.getenv("AUTH0_AUDIENCE")
ANTHROPIC_API_KEY   = os.getenv("ANTHROPIC_API_KEY")
GITHUB_CLIENT_ID    = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET= os.getenv("GITHUB_CLIENT_SECRET")
NOTION_SECRET       = os.getenv("NOTION_SECRET")

# ── SESSION STORE (file-backed so reloads don't wipe tokens) ─
import pathlib
_SESSIONS_FILE = pathlib.Path(__file__).parent / "sessions.json"

def _load_sessions() -> dict:
    if _SESSIONS_FILE.exists():
        try:
            return json.loads(_SESSIONS_FILE.read_text())
        except Exception:
            pass
    return {}

def _save_sessions(s: dict):
    _SESSIONS_FILE.write_text(json.dumps(s))

sessions: dict = _load_sessions()
# Backfill notion_token into any persisted sessions that are missing it
for _s in sessions.values():
    if "notion_token" not in _s:
        _s["notion_token"] = os.getenv("NOTION_SECRET")

# ── MODELS ───────────────────────────────────────────────
class WorkflowRequest(BaseModel):
    prompt: str
    services: List[str]
    session_id: Optional[str] = None

class NotionPageRequest(BaseModel):
    title: str
    content: str
    session_id: str

# ── HEALTH CHECK ─────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "auth0": bool(AUTH0_DOMAIN),
        "github": bool(GITHUB_CLIENT_ID),
        "notion": bool(NOTION_SECRET),
        "anthropic": bool(ANTHROPIC_API_KEY),
    }

# ── AUTH0 LOGIN ───────────────────────────────────────────
@app.get("/auth/login")
async def login():
    """Redirect user to Auth0 login page"""
    state = secrets.token_urlsafe(16)
    sessions[state] = {}  # reserve state slot

    params = (
        f"response_type=code"
        f"&client_id={AUTH0_CLIENT_ID}"
        f"&redirect_uri=http://localhost:8000/auth/callback"
        f"&scope=openid profile email"
        f"&audience={AUTH0_AUDIENCE}"
        f"&state={state}"
    )
    return RedirectResponse(f"https://{AUTH0_DOMAIN}/authorize?{params}")


@app.get("/auth/callback")
async def auth_callback(code: str, state: str):
    """Handle Auth0 callback, exchange code for tokens"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://{AUTH0_DOMAIN}/oauth/token",
            json={
                "grant_type": "authorization_code",
                "client_id": AUTH0_CLIENT_ID,
                "client_secret": AUTH0_CLIENT_SECRET,
                "code": code,
                "redirect_uri": "http://localhost:8000/auth/callback",
            }
        )
        token_data = resp.json()

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Auth0 login failed")

    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = {
        "access_token": access_token,
        "github_token": None,
        "notion_token": NOTION_SECRET,  # Notion uses a static integration secret
    }
    _save_sessions(sessions)

    # Redirect back to frontend with session id
    return RedirectResponse(f"http://localhost:3000?session={session_id}")


# ── GITHUB OAUTH VIA TOKEN VAULT ─────────────────────────
@app.get("/auth/github")
async def github_connect(session_id: str):
    """Initiate GitHub OAuth - Auth0 Token Vault style"""
    state = f"{session_id}:github"
    params = (
        f"client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri=http://localhost:8000/auth/github/callback"
        f"&scope=read:user,public_repo"
        f"&state={state}"
    )
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{params}")


@app.get("/auth/github/callback")
async def github_callback(code: str, state: str):
    """Exchange GitHub code for access token, store in session (Token Vault pattern)"""
    session_id = state.split(":")[0]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": "http://localhost:8000/auth/github/callback",
            }
        )
        token_data = resp.json()

    github_token = token_data.get("access_token")
    if not github_token:
        raise HTTPException(status_code=400, detail="GitHub OAuth failed")

    # Store token in session (this is the Token Vault pattern)
    if session_id not in sessions:
        sessions[session_id] = {}
    sessions[session_id]["github_token"] = github_token
    _save_sessions(sessions)

    return RedirectResponse(f"http://localhost:3000?session={session_id}&connected=github")


# ── SESSION STATUS ────────────────────────────────────────
@app.get("/session/{session_id}")
async def get_session(session_id: str):
    session = sessions.get(session_id, {})
    return {
        "github_connected": bool(session.get("github_token")),
        "notion_connected": bool(session.get("notion_token")),
    }


# ── GITHUB API ────────────────────────────────────────────
@app.get("/github/starred")
async def get_starred_repos(session_id: str, limit: int = 10):
    """Fetch real starred repos from GitHub using stored token"""
    session = sessions.get(session_id)
    if not session or not session.get("github_token"):
        raise HTTPException(status_code=401, detail="GitHub not connected. Connect GitHub first.")

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.github.com/user/starred",
            headers={
                "Authorization": f"token {session['github_token']}",
                "Accept": "application/vnd.github.v3+json",
            },
            params={"per_page": limit}
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="GitHub API error")

    repos = resp.json()
    return {
        "repos": [
            {
                "name": r["full_name"],
                "description": r.get("description", ""),
                "stars": r["stargazers_count"],
                "language": r.get("language", "Unknown"),
                "url": r["html_url"],
                "topics": r.get("topics", []),
            }
            for r in repos
        ]
    }


@app.get("/github/profile")
async def get_github_profile(session_id: str):
    """Get the connected GitHub user's profile"""
    session = sessions.get(session_id)
    if not session or not session.get("github_token"):
        raise HTTPException(status_code=401, detail="GitHub not connected")

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"token {session['github_token']}",
                "Accept": "application/vnd.github.v3+json",
            }
        )

    user = resp.json()
    return {
        "username": user["login"],
        "name": user.get("name", user["login"]),
        "avatar": user.get("avatar_url"),
        "public_repos": user.get("public_repos", 0),
        "followers": user.get("followers", 0),
    }


# ── NOTION API ────────────────────────────────────────────
@app.get("/notion/databases")
async def get_notion_databases(session_id: str):
    """List available Notion databases"""
    session = sessions.get(session_id)
    notion_token = (session.get("notion_token") if session else None) or NOTION_SECRET

    if not notion_token:
        raise HTTPException(status_code=401, detail="Notion not connected")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.notion.com/v1/search",
            headers={
                "Authorization": f"Bearer {notion_token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            },
            json={"filter": {"value": "database", "property": "object"}}
        )

    data = resp.json()
    results = data.get("results", [])
    return {
        "databases": [
            {
                "id": db["id"],
                "title": db.get("title", [{}])[0].get("plain_text", "Untitled") if db.get("title") else "Untitled",
            }
            for db in results
        ]
    }


@app.post("/notion/create-page")
async def create_notion_page(req: NotionPageRequest):
    """Create a real page in Notion"""
    session = sessions.get(req.session_id)
    notion_token = (session.get("notion_token") if session else None) or NOTION_SECRET

    if not notion_token:
        raise HTTPException(status_code=401, detail="Notion not connected")

    # First find a parent page or database to add to
    async with httpx.AsyncClient() as client:
        search_resp = await client.post(
            "https://api.notion.com/v1/search",
            headers={
                "Authorization": f"Bearer {notion_token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            },
            json={"filter": {"value": "page", "property": "object"}, "page_size": 1}
        )
        search_data = search_resp.json()
        results = search_data.get("results", [])

        if not results:
            raise HTTPException(status_code=400, detail="No Notion pages found. Share a page with the ViKeY integration first.")

        parent_id = results[0]["id"]

        # Create the page
        create_resp = await client.post(
            "https://api.notion.com/v1/pages",
            headers={
                "Authorization": f"Bearer {notion_token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            },
            json={
                "parent": {"page_id": parent_id},
                "properties": {
                    "title": {
                        "title": [{"text": {"content": req.title}}]
                    }
                },
                "children": [
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": req.content}}]
                        }
                    }
                ]
            }
        )
        page = create_resp.json()

    return {
        "success": True,
        "page_id": page.get("id"),
        "url": page.get("url"),
        "title": req.title,
    }


# ── AI WORKFLOW GENERATOR ─────────────────────────────────
@app.post("/workflow/generate")
async def generate_workflow(req: WorkflowRequest):
    """Use Claude to generate workflow steps from natural language"""
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="Anthropic API key not set")

    system_prompt = """You are ViKeY's workflow engine. Given a user's natural language request,
    generate a structured JSON workflow with concrete steps.
    
    Return ONLY valid JSON in this format:
    {
      "title": "Short workflow title",
      "steps": [
        {
          "id": 1,
          "service": "github|notion|spotify|gmail|slack",
          "action": "Short action label",
          "description": "What this step does",
          "permission": "exact.permission.scope"
        }
      ],
      "summary": "One sentence summary of what this workflow does"
    }"""

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 1000,
                "system": system_prompt,
                "messages": [
                    {"role": "user", "content": f"Services available: {', '.join(req.services)}\n\nUser request: {req.prompt}"}
                ]
            }
        )

    data = resp.json()
    if "error" in data or "content" not in data:
        raise HTTPException(status_code=502, detail=f"Anthropic API error: {data.get('error', {}).get('message', str(data))}")
    raw = data["content"][0]["text"]

    try:
        workflow = json.loads(raw)
    except json.JSONDecodeError:
        # Extract JSON if wrapped in markdown
        import re
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        workflow = json.loads(match.group()) if match else {"title": "Workflow", "steps": [], "summary": raw}

    return workflow


# ── FULL WORKFLOW RUNNER ──────────────────────────────────
@app.post("/workflow/run")
async def run_workflow(req: WorkflowRequest):
    """Run a complete GitHub → Notion workflow"""
    session = sessions.get(req.session_id) if req.session_id else {}

    results = []

    # Step 1: Fetch starred repos from GitHub
    github_token = session.get("github_token") if session else None
    repos = []

    if github_token:
        async with httpx.AsyncClient() as client:
            gh_resp = await client.get(
                "https://api.github.com/user/starred",
                headers={
                    "Authorization": f"token {github_token}",
                    "Accept": "application/vnd.github.mercy-preview+json",
                },
                params={"per_page": 10}
            )
            if gh_resp.status_code == 200:
                repos = gh_resp.json()
                results.append({
                    "step": 1,
                    "service": "github",
                    "action": "Fetch Starred Repos",
                    "status": "success",
                    "data": f"Found {len(repos)} starred repositories",
                })
            else:
                results.append({"step": 1, "service": "github", "action": "Fetch Starred Repos", "status": "error", "data": "GitHub API error"})
    else:
        results.append({"step": 1, "service": "github", "action": "Fetch Starred Repos", "status": "skipped", "data": "GitHub not connected"})

    # Step 2: Upsert repos into a Notion database
    DB_TITLE = "GitHub Starred Repos - ViKeY"
    notion_token = (session.get("notion_token") if session else None) or NOTION_SECRET
    if notion_token and repos:
        notion_headers = {
            "Authorization": f"Bearer {notion_token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        today = date.today().isoformat()

        async with httpx.AsyncClient() as client:

            # ── 1. Check if our database already exists ──────────────
            db_search = await client.post(
                "https://api.notion.com/v1/search",
                headers=notion_headers,
                json={"query": DB_TITLE, "filter": {"value": "database", "property": "object"}},
            )
            db_results = db_search.json().get("results", [])
            existing_db = next(
                (d for d in db_results
                 if any(t.get("plain_text", "") == DB_TITLE
                        for t in d.get("title", []))),
                None,
            )

            if existing_db:
                # ── 2a. Database exists — fetch existing row names ────
                db_id  = existing_db["id"]
                db_url = existing_db.get("url", "")

                rows_resp = await client.post(
                    f"https://api.notion.com/v1/databases/{db_id}/query",
                    headers=notion_headers,
                    json={"page_size": 100},
                )
                existing_names = {
                    row["properties"]["Name"]["title"][0]["plain_text"]
                    for row in rows_resp.json().get("results", [])
                    if row["properties"].get("Name", {}).get("title")
                }
                repos_to_add = [r for r in repos if r["full_name"] not in existing_names]
                action_label = f"Updated existing database ({len(repos_to_add)} new, {len(repos) - len(repos_to_add)} skipped)"

            else:
                # ── 2b. Create the database fresh ────────────────────
                page_search = await client.post(
                    "https://api.notion.com/v1/search",
                    headers=notion_headers,
                    json={"filter": {"value": "page", "property": "object"}, "page_size": 1},
                )
                page_results = page_search.json().get("results", [])
                if not page_results:
                    results.append({"step": 2, "service": "notion", "action": "Create Notion Database", "status": "error", "data": "No Notion page found. Share a page with the ViKeY integration first."})
                    return {"workflow_id": f"wf_{secrets.token_hex(4)}", "status": "completed", "results": results}

                parent_id = page_results[0]["id"]
                db_resp = await client.post(
                    "https://api.notion.com/v1/databases",
                    headers=notion_headers,
                    json={
                        "parent": {"type": "page_id", "page_id": parent_id},
                        "title": [{"type": "text", "text": {"content": DB_TITLE}}],
                        "properties": {
                            "Name":        {"title": {}},
                            "Language":    {"select": {}},
                            "Stars":       {"number": {"format": "number"}},
                            "Description": {"rich_text": {}},
                            "URL":         {"url": {}},
                            "Topics":      {"multi_select": {}},
                            "Date Added":  {"date": {}},
                        },
                    },
                )
                db = db_resp.json()
                db_id = db.get("id")
                if not db_id:
                    results.append({"step": 2, "service": "notion", "action": "Create Notion Database", "status": "error", "data": f"Database creation failed: {db.get('message', str(db))}"})
                    return {"workflow_id": f"wf_{secrets.token_hex(4)}", "status": "completed", "results": results}

                db_url = db.get("url", "")
                repos_to_add = repos
                action_label = f"Created database with {len(repos_to_add)} repos"

            # ── 3. Insert rows ────────────────────────────────────────
            row_errors = []
            for r in repos_to_add:
                topics = [{"name": t} for t in (r.get("topics") or [])[:10]]
                row_resp = await client.post(
                    "https://api.notion.com/v1/pages",
                    headers=notion_headers,
                    json={
                        "parent": {"database_id": db_id},
                        "properties": {
                            "Name":        {"title": [{"text": {"content": r["full_name"]}}]},
                            "Language":    {"select": {"name": r.get("language") or "Unknown"}},
                            "Stars":       {"number": r.get("stargazers_count", 0)},
                            "Description": {"rich_text": [{"text": {"content": (r.get("description") or "")[:2000]}}]},
                            "URL":         {"url": r.get("html_url", "")},
                            "Topics":      {"multi_select": topics},
                            "Date Added":  {"date": {"start": today}},
                        },
                    },
                )
                if row_resp.status_code not in (200, 201):
                    row_errors.append(r["full_name"])

            if row_errors:
                results.append({"step": 2, "service": "notion", "action": "Upsert Notion Database", "status": "error", "data": f"Failed to insert: {', '.join(row_errors)}"})
            else:
                results.append({"step": 2, "service": "notion", "action": "Upsert Notion Database", "status": "success", "data": f"{action_label}: {db_url}"})
    else:
        results.append({"step": 2, "service": "notion", "action": "Upsert Notion Database", "status": "skipped", "data": "No repos or Notion not connected"})

    return {
        "workflow_id": f"wf_{secrets.token_hex(4)}",
        "status": "completed",
        "results": results,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)