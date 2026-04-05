# ViKey 🔑
### AI Agent Platform · Secured by Auth0 Token Vault

> Built for the **Auth0 "Authorized to Act" Hackathon 2026**

ViKey lets you describe workflows in plain English — "When I star a GitHub repo, save it to Notion" — and an AI agent executes them, using Auth0 Token Vault to securely manage every OAuth token.

---

## 🎬 Quick Demo (no setup needed)

Just open `frontend/index.html` in your browser. It runs fully in-browser with simulated responses — perfect for the demo video.

---

## 🏗️ Full Stack Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- Auth0 account (free): https://auth0.com/signup
- Anthropic API key: https://console.anthropic.com

---

### Step 1 — Auth0 Setup (10 min)

1. Go to https://auth0.com/signup and create a free account
2. Create a new **Application** → choose "Regular Web Application"
3. Note your: `Domain`, `Client ID`, `Client Secret`
4. Go to **APIs** → create a new API with identifier `https://your-tenant.auth0.com/api/v2/`
5. Enable **Token Vault** in your Auth0 dashboard under AI Agents → Token Vault
6. Add connections for GitHub, Notion, Spotify in Auth0's Social Connections

---

### Step 2 — Backend Setup

```bash
cd backend
cp .env.example .env
# Fill in your keys in .env
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Your API will be live at http://localhost:8000

---

### Step 3 — Frontend Setup

```bash
cd frontend
# Option A: Simple (no build needed)
open index.html   # or double-click it

# Option B: Full React app
npm install
npm start
```

---

## 🔑 How Token Vault Works in ViKey

```
User connects GitHub
        ↓
Auth0 handles OAuth flow
        ↓
Token stored encrypted in Token Vault
        ↓
User describes workflow to ViKey
        ↓
Claude AI parses intent → structured actions
        ↓
ViKey backend requests token from Vault per-action
        ↓
Action executes with minimum required scope
        ↓
User can revoke at any time from Permissions page
```

**Tokens are:**
- 🔐 Encrypted at rest in Auth0 Token Vault
- 🎯 Scoped to minimum permissions per service
- 🚫 Never logged or returned to the frontend
- ✋ Instantly revocable by the user

---

## 📁 Project Structure

```
vikey/
├── backend/
│   ├── main.py              # FastAPI app + agent logic
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── index.html           # Standalone demo (open this!)
    └── src/
        └── App.jsx          # Full React app
```

---

## 🧠 AI Agent Logic

ViKey uses Claude (Anthropic) to parse natural language into structured workflow JSON:

**Input:** `"When I star a GitHub repo, save it to Notion"`

**Output:**
```json
{
  "title": "GitHub Star → Notion Sync",
  "actions": [
    {"service": "github", "action": "get_starred_repos", ...},
    {"service": "notion", "action": "create_page", ...}
  ],
  "requires_permissions": ["github:read", "notion:write"]
}
```

---

## 🏆 Judging Criteria Coverage

| Criterion | ViKey's approach |
|---|---|
| Security Model | Token Vault handles all OAuth, tokens never in frontend |
| User Control | Permissions page shows/revokes every scope |
| Technical Execution | FastAPI + Auth0 Token Vault + Claude AI |
| Design | Bespoke dark UI with Playfair Display + DM Mono |
| Potential Impact | Universal use case for all developers |
| Insight Value | Demonstrates multi-service agent auth patterns |

---

## 🔧 Supported Services

| Service | Actions |
|---|---|
| GitHub | get_starred_repos, create_issue |
| Notion | create_page |
| Spotify | get_current_track, create_playlist |
| Gmail | get_latest (coming soon) |
| Slack | post_message (coming soon) |

---

## 📝 Bonus Blog Post

See the `## Bonus Blog Post` section in the Devpost submission for the 250-word blog post about our Token Vault journey.

---

Built with ❤️ using Auth0, Anthropic Claude, FastAPI, and React.
