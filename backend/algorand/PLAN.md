# OPSonic — Project Plan & Scope
## Hackathon Handoff Document

This document describes exactly what OPSonic is, what has been built,
what it does, and what every file is responsible for.
Give this to any AI assistant before asking it to work on this codebase.

---

## What OPSonic Is

OPSonic is an AI-powered autonomous cloud deployment platform.
A user uploads their code — as a ZIP, a GitHub URL, or a compiled Java JAR —
and OPSonic automatically reads and understands the project using an LLM,
makes an intelligent deployment decision, provisions the required cloud
infrastructure, and returns a live URL. Zero manual configuration required.

---

## What We Added for the Hackathon (Algorand Integration)

Two features were added on top of the original OPSonic:

### Feature 1 — Algorand dApp Deployment

OPSonic can now detect and deploy Algorand smart contract projects
(dApps) in addition to its existing Web2 deployment paths.

When a user uploads an Algorand dApp (AlgoKit-generated, PyTeal, or Puya):
1. The AI detects it is an Algorand project
2. The contract is compiled and deployed to Algorand TestNet
3. The frontend (if any) is deployed to AWS Amplify
4. The user receives the App ID, contract address, explorer URL, and frontend URL

### Feature 2 — Algorand Credential Vault

AWS IAM credentials entered by users are encrypted with AES-256-GCM
and stored in Algorand box storage. On future deployments, users only
need to provide their Access Key ID — the vault retrieves and decrypts
the secret automatically. Plaintext credentials never touch disk.

---

## Full System Architecture

```
User (Browser)
    │
    │  Upload ZIP / JAR / GitHub URL
    ▼
FastAPI Backend (app.py)
    │
    ├── fileUploadLayer/
    │     zip_handler.py       — extracts ZIP to local storage
    │     github_handler.py    — clones GitHub repo via GitPython
    │
    ├── codeReviewLayer/
    │     repo_scanner.py      — walks directory tree, detects Algorand signals
    │     structure_analyzer.py — infers monorepo / dApp / frontend / backend structure
    │     dependency_analyzer.py — reads requirements.txt, package.json, algokit.toml
    │     prompts.py           — LLM prompt with explicit Algorand detection rules
    │     repo_reasoner.py     — calls Ollama LLM, validates JSON response
    │     reviewer.py          — orchestrates the pipeline, applies safety-net correction
    │
    ├── aiLayer/
    │     decision_engine.py   — routes to correct deployment path:
    │                            A. JAR  → EC2 Java
    │                            B. Algorand dApp → Algorand TestNet + Amplify
    │                            C. Frontend → Amplify (snapshot or CI/CD)
    │                            D. Backend/Fullstack → EC2 source deploy
    │
    ├── auth/
    │     aws_credentials.py   — credential resolution: frontend → vault → env → terminal
    │
    └── mcpServer/
          server.py            — TOOLS registry (all callable deployment functions)
          mcpClient.py         — thin dispatch client (unchanged)
          │
          ├── tools/
          │     ec2_provision.py       — existing
          │     java_deploy.py         — existing
          │     source_deploy.py       — existing
          │     amplify_deploy.py      — existing
          │     amplify_cicd_tools.py  — existing
          │     algorand_deploy.py     — NEW: deploys Algorand contract
          │     algorand_credentials.py — NEW: vault MCP tool wrappers
          │
          └── infraScripts/
                provision_ec2.py       — existing
                deploy_app.py          — existing
                deploy_source.py       — existing
                amplify_deploy.py      — existing
                amplify_cicd.py        — existing
                algorand_deploy.py     — NEW: algosdk + algokit-utils contract deploy
                algorand_credential_store.py — NEW: AES-256-GCM + Algorand box storage
```

---

## Environment Variables Required

```env
# AWS (for EC2 and Amplify deployments)
AWS_ACCESS_KEY_ID="AKIA..."
AWS_SECRET_ACCESS_KEY="..."
AWS_DEFAULT_REGION="ap-south-1"

# Algorand TestNet
ALGOD_TOKEN=""                          # Empty is fine for AlgoNode TestNet
ALGOD_SERVER="https://testnet-api.algonode.cloud"
ALGORAND_DEPLOYER_MNEMONIC="word1 word2 ... word25"   # 25-word wallet mnemonic

# Vault (filled automatically after running scripts/setup_vault.py)
CREDENTIAL_VAULT_APP_ID=""
```

---

## Setup Order (Run Once Before First Demo)

```bash
# 1. Install dependencies
cd backend
pip install -r requirements.txt

# 2. Deploy vault contract to Algorand TestNet
#    This costs ~0.1 ALGO and writes CREDENTIAL_VAULT_APP_ID to .env
python scripts/setup_vault.py

# 3. Verify vault is working
python -c "
from mcpServer.infraScripts.algorand_credential_store import has_credentials
print('Vault OK:', has_credentials('AKIATEST000000000000'))
"

# 4. Start backend
uvicorn app:app --host 0.0.0.0 --port 8000

# 5. Start frontend (in a second terminal)
cd ../frontend
npm install
npm run dev
```

---

## API Endpoints

| Method | Path             | Purpose                                        |
|--------|------------------|------------------------------------------------|
| POST   | /upload          | Upload ZIP or JAR — full deployment pipeline   |
| POST   | /upload/github   | GitHub URL — clone, review, deploy             |
| POST   | /review          | Standalone code review only (no deploy)        |
| POST   | /vault/check     | Check if credentials exist in Algorand vault   |
| POST   | /vault/store     | Explicitly store credentials in vault          |
| POST   | /vault/delete    | Delete credentials, reclaim Algorand MBR       |

---

## Deployment Paths (Decision Engine)

### Path A — Java JAR → AWS EC2
- Trigger: uploaded file ends with `.jar`
- Steps: provision EC2 → upload JAR via SSH → run `java -jar` on port 8080
- Returns: `{ endpoint: "http://<ip>:8080" }`

### Path B — Algorand dApp → Algorand TestNet + AWS Amplify
- Trigger: `project_type == "algorand_dapp"` OR `is_algorand_dapp == true`
- Detection signals: algokit.toml, algopy/pyteal imports, .teal files, arc32.json
- Steps:
  1. Deploy smart contract → get App ID
  2. (If frontend exists) deploy frontend to Amplify
- Returns: `{ app_id, app_address, explorer_url, endpoint (frontend URL) }`

### Path C — Frontend → AWS Amplify
- Trigger: `project_type == "frontend"` OR `language == "static"`
- Sub-path C1 (CI/CD): GitHub URL + PAT → Amplify connected to GitHub
- Sub-path C2 (Snapshot): ZIP or no PAT → build locally, upload to Amplify
- Returns: `{ endpoint: "https://<branch>.<appId>.amplifyapp.com" }`

### Path D — Backend / Fullstack → AWS EC2
- Trigger: `project_type in ["backend", "fullstack"]`
- Languages supported: Python (FastAPI/Flask), Node.js (Express)
- Steps: provision EC2 → SCP source zip → install runtime → start with PM2
- Returns: `{ endpoint: "http://<ip>:8080" }`

---

## Algorand Credential Vault — Security Model

```
AWS Secret Key (plaintext)
    │
    ▼
HKDF-SHA256 key derivation
  ikm  = Algorand wallet private key bytes  ← never leaves server
  salt = AWS_ACCESS_KEY_ID                  ← semi-public, per-user salt
  info = b"opsonic-aws-creds-v1"           ← domain separation constant
    │
    ▼
AES-256-GCM encryption
  nonce = 12 random bytes (new each time)
  output = base64(nonce + ciphertext + 16-byte auth tag)
    │
    ▼
Algorand Box Storage
  box_key   = sha256(AWS_ACCESS_KEY_ID)[:32]
  box_value = encrypted blob (~170 bytes)
  cost      = ~0.097 ALGO per credential stored
```

**Why this is secure:**
- On-chain data is an encrypted blob — useless without the private key
- Private key alone is useless — HKDF needs the access_key_id salt too
- GCM auth tag detects any tampering of the stored blob
- Plaintext credentials never written to disk, database, or logs

---

## Algorand dApp Detection — How It Works

The Code Review Layer uses a three-stage static analysis pipeline BEFORE
calling the LLM:

1. **repo_scanner.py** walks the directory and collects `algorand_signals`:
   - `config:algokit.toml` — AlgoKit project marker (strongest signal)
   - `algorand_import:path/to/contract.py` — .py file importing algopy/pyteal
   - `teal_file:path/to/file.teal` — compiled TEAL output
   - `dir:smart_contracts` — directory named smart_contracts or contracts

2. **dependency_analyzer.py** checks requirements.txt and pyproject.toml for:
   `pyteal`, `algopy`, `algokit-utils`, `beaker`, `algosdk`
   Sets `is_algorand_project = True` if any found.

3. **repo_reasoner.py** sends all signals to the LLM with strict rules:
   "If ANY algorand signal exists → project_type MUST be algorand_dapp"

4. **Safety net in reviewer.py**: if `is_algorand_project = True` from
   static analysis but AI returned something else, the result is overridden.
   The AI cannot miss an Algorand project.

---

## Files Changed vs Original OPSonic

### Modified (replace originals completely)
| File | What Changed |
|------|-------------|
| `requirements.txt` | Added py-algorand-sdk, algokit-utils |
| `app.py` | JAR section uses vault, added 3 vault endpoints |
| `auth/aws_credentials.py` | Full credential resolution pipeline |
| `codeReviewLayer/schema.py` | Added Algorand fields to Pydantic model |
| `codeReviewLayer/analyzers/repo_scanner.py` | Algorand signal detection |
| `codeReviewLayer/analyzers/structure_analyzer.py` | Algorand structure inference |
| `codeReviewLayer/analyzers/dependency_analyzer.py` | Algorand lib detection |
| `codeReviewLayer/prompts.py` | Explicit Algorand detection rules for LLM |
| `codeReviewLayer/llm/repo_reasoner.py` | Updated schema, better fallbacks |
| `codeReviewLayer/reviewer.py` | Safety net correction, richer context |
| `aiLayer/decision_engine.py` | Added Path B (Algorand dApp) |
| `mcpServer/server.py` | Registered 5 new tools |
| `frontend/src/App.jsx` | Vault-aware AWS modal, Algorand success card |

### New Files (create these)
| File | Purpose |
|------|---------|
| `mcpServer/infraScripts/algorand_deploy.py` | algosdk contract deployment |
| `mcpServer/infraScripts/algorand_credential_store.py` | Vault encryption + box storage |
| `mcpServer/tools/algorand_deploy.py` | MCP tool wrapper |
| `mcpServer/tools/algorand_credentials.py` | MCP tool wrappers (4 vault tools) |
| `scripts/setup_vault.py` | One-time vault contract deployment |
| `.env.example` | Updated with Algorand vars |

### Unchanged (do not touch)
- `fileUploadLayer/services/zip_handler.py`
- `fileUploadLayer/services/github_handler.py`
- `fileUploadLayer/utils/file_utils.py`
- `mcpClient.py`
- `mcpServer/tools/ec2_provision.py`
- `mcpServer/tools/java_deploy.py`
- `mcpServer/tools/source_deploy.py`
- `mcpServer/tools/amplify_deploy.py`
- `mcpServer/tools/amplify_cicd_tools.py`
- `mcpServer/infraScripts/provision_ec2.py`
- `mcpServer/infraScripts/deploy_app.py`
- `mcpServer/infraScripts/deploy_source.py`
- `mcpServer/infraScripts/amplify_deploy.py`
- `mcpServer/infraScripts/amplify_cicd.py`
- `frontend/package.json`
- `frontend/vite.config.js`
- `frontend/index.css`
- `frontend/main.jsx`

---

## Algorand ALGO Cost Estimates (TestNet)

| Operation | Cost |
|-----------|------|
| Deploy vault contract (once) | ~0.101 ALGO |
| Store credentials in box | ~0.097 ALGO |
| Retrieve credentials | 0 ALGO (read-only) |
| Check credentials exist | 0 ALGO (read-only) |
| Delete credentials (reclaims MBR) | Net -0.094 ALGO |
| Deploy Algorand contract | ~0.002 ALGO |
| **Total for full hackathon demo** | **< 0.5 ALGO** |

With 6 ALGO in the wallet, there is no budget concern.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Vite 7, Tailwind CSS 4, lucide-react |
| API Server | FastAPI + Uvicorn |
| Code Analysis | Custom Python analyzers |
| AI Reasoning | Ollama (gpt-oss:20b via custom host) |
| Credential Encryption | AES-256-GCM + HKDF-SHA256 (cryptography lib) |
| Algorand SDK | py-algorand-sdk (algosdk) |
| Algorand Deployment | algokit-utils ApplicationClient |
| Algorand Storage | Box storage via algod API |
| AWS EC2 | boto3 + Paramiko (SSH) |
| AWS Amplify | boto3 amplify client |
| Process Manager | PM2 (on EC2) |
| Git Cloning | GitPython |

---

## Known Constraints

- EC2 deployments use `ap-south-1` region (Mumbai). Configurable via env.
- Algorand deployments target TestNet only. Change ALGOD_SERVER for MainNet.
- Algorand dApp detection works best with AlgoKit-generated projects that
  have `algokit.toml` and a compiled `application.json` ABI spec.
- Raw PyTeal projects without a compiled spec will attempt raw TEAL deployment
  which requires `approval.teal` and `clear.teal` to be present.
- The vault is deployed by the OPSonic service wallet — all credentials are
  tied to that wallet's private key. Losing the mnemonic = losing vault access.
- Frontend port is `8000` for the backend API (updated from original 8080).
