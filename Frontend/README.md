# ViKey 🔑
### AI Agent Platform · Secured by Auth0 Token Vault

> Built for the **Auth0 "Authorized to Act" Hackathon 2026**

ViKey lets you describe workflows in plain English — "When I star a GitHub repo, save it to Notion" — and an AI agent executes them, using Auth0 Token Vault to securely manage every OAuth token.



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




