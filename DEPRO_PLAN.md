# dePro — Complete Project Plan
## Claude Code Handoff Document

Read this entire document before touching any file.
This is the single source of truth for what dePro is, what has been built, and what every file does.

---

## What dePro Is

dePro is an AI-powered autonomous cloud deployment platform for both Web2 and Web3 developers.
A user connects their Lute (Algorand) wallet, pays a small ALGO deployment fee, uploads their
code — ZIP, GitHub URL, or compiled JAR — and dePro automatically reads the project using an LLM,
decides the optimal deployment strategy, provisions cloud infrastructure, and returns a live URL.
Zero manual configuration required.

---

## Three Algorand Features Built on Top of the Core Platform

### Feature 1 — Algorand dApp Deployment
dePro detects Algorand smart contract projects (AlgoKit, PyTeal, Puya) and deploys them
end-to-end: contract to Algorand TestNet, frontend to AWS Amplify. Returns App ID + live URL.

### Feature 2 — Algorand Credential Vault
AWS IAM credentials are encrypted with AES-256-GCM (HKDF-SHA256 key derivation) and stored
in Algorand box storage. Users enter their secret key once — every future deployment retrieves
it automatically. Plaintext credentials never touch disk, database, or logs.

### Feature 3 — Lute Wallet Login + x402 Payment Gate
Users log in by connecting their Lute wallet and signing a challenge string. Every deployment
requires an upfront ALGO payment (x402 protocol). The backend verifies the on-chain transaction
before executing any deployment.

---

## Full Project Structure

```
backend/
├── app.py                                   ← Main FastAPI server — ALL endpoints here
├── requirements.txt                         ← All Python dependencies
├── .env                                     ← Environment variables (see section below)
│
├── auth/
│   ├── wallet_auth.py                       ← Challenge generation, signature verification, JWT
│   ├── auth_routes.py                       ← /auth/challenge, /auth/verify, /auth/me, /auth/logout
│   └── aws_credentials.py                   ← AWS credential resolution pipeline (vault-aware)
│
├── aiLayer/
│   └── decision_engine.py                   ← Routes to correct deployment path (A/B/C/D)
│
├── codeReviewLayer/
│   ├── reviewer.py                          ← Orchestrates full code review pipeline
│   ├── schema.py                            ← Pydantic schema for AI response (includes Algorand fields)
│   ├── prompts.py                           ← LLM prompt with explicit Algorand detection rules
│   ├── analyzers/
│   │   ├── repo_scanner.py                  ← Walks directory, detects Algorand signals
│   │   ├── structure_analyzer.py            ← Infers monorepo/dApp/frontend/backend structure
│   │   └── dependency_analyzer.py           ← Reads requirements.txt, package.json, algokit.toml
│   └── llm/
│       └── repo_reasoner.py                 ← Calls Ollama LLM, validates JSON response
│
├── fileUploadLayer/
│   └── services/
│       ├── zip_handler.py                   ← Extracts ZIP to local storage
│       └── github_handler.py                ← Clones GitHub repo via GitPython
│
├── mcpServer/
│   ├── server.py                            ← TOOLS registry — all callable deployment functions
│   ├── mcpClient.py                         ← Thin dispatch client
│   ├── tools/
│   │   ├── ec2_provision.py                 ← MCP wrapper: provision EC2
│   │   ├── java_deploy.py                   ← MCP wrapper: deploy JAR to EC2
│   │   ├── source_deploy.py                 ← MCP wrapper: deploy source to EC2
│   │   ├── amplify_deploy.py                ← MCP wrapper: deploy frontend to Amplify
│   │   ├── amplify_cicd_tools.py            ← MCP wrapper: connect GitHub to Amplify CI/CD
│   │   ├── algorand_deploy.py               ← MCP wrapper: deploy Algorand smart contract
│   │   └── algorand_credentials.py          ← MCP wrappers: vault store/retrieve/delete/check
│   └── infraScripts/
│       ├── provision_ec2.py                 ← boto3 + EC2: key pair, security group, launch instance
│       ├── deploy_app.py                    ← SSH + JAR upload and run
│       ├── deploy_source.py                 ← SSH + source zip upload + PM2
│       ├── amplify_deploy.py                ← boto3 + Amplify: build and snapshot deploy
│       ├── amplify_cicd.py                  ← boto3 + Amplify: connect GitHub for CI/CD
│       ├── algorand_deploy.py               ← algosdk + algokit-utils: compile and deploy contract
│       ├── algorand_credential_store.py     ← AES-256-GCM encryption + Algorand box storage
│       └── x402_payment.py                  ← Payment verification before deployments execute
│
└── scripts/
    ├── setup_vault.py                       ← ONE-TIME: deploy CredentialVault contract to TestNet
    ├── fund_contract.py                     ← ONE-TIME: send 0.5 ALGO to vault contract account
    ├── verify_vault.py                      ← TEST: full 7-step vault verification
    └── check_vault_entry.py                 ← TEST: store credential and leave it in Algorand (no delete)

frontend/
└── src/
    └── App.jsx                              ← Complete React UI (all components in one file)
```

---

## Environment Variables (.env)

```env
# ── AWS ─────────────────────────────────────────────────────────
AWS_ACCESS_KEY_ID="AKIA..."
AWS_SECRET_ACCESS_KEY="..."
AWS_DEFAULT_REGION="ap-south-1"

# ── Algorand TestNet ─────────────────────────────────────────────
ALGOD_TOKEN=""
ALGOD_SERVER="https://testnet-api.algonode.cloud"
ALGORAND_DEPLOYER_MNEMONIC="word1 word2 ... word25"

# ── Vault (auto-written by setup_vault.py) ───────────────────────
CREDENTIAL_VAULT_APP_ID="757482499"

# ── Wallet auth ──────────────────────────────────────────────────
JWT_SECRET="any_random_string_min_32_chars"

# ── x402 payment treasury ────────────────────────────────────────
DEPRO_TREASURY_ADDRESS="7UCTS3PFI3ARHWEONK4SVTMW643WBANSLT6CPLATRAIRTUPCDIRZEOOK54"
```

---

## API Endpoints

### Auth (Lute Wallet Login)
| Method | Path | Description |
|--------|------|-------------|
| POST | /auth/challenge | Step 1: get challenge string for wallet to sign |
| POST | /auth/verify | Step 2: submit signature → receive session token |
| GET | /auth/me | Check if session token is still valid |
| POST | /auth/logout | Clear session |

### Deployments (require Authorization header + payment_tx_id)
| Method | Path | Description |
|--------|------|-------------|
| POST | /upload | Upload ZIP or JAR — full pipeline |
| POST | /upload/github | GitHub URL — clone, review, deploy |
| POST | /review | Code review only, no deploy, no auth needed |

### x402 Payments
| Method | Path | Description |
|--------|------|-------------|
| GET | /x402/fees | Returns fee table for all project types |
| POST | /x402/verify | Pre-verify a payment TX before upload |

### Vault
| Method | Path | Description |
|--------|------|-------------|
| POST | /vault/check | Check if credentials exist (no cost, read-only) |
| POST | /vault/store | Explicitly store credentials |
| POST | /vault/delete | Delete credentials and reclaim MBR |

---

## Deployment Paths (Decision Engine)

### Path A — Java JAR → AWS EC2
- Trigger: file ends with `.jar`
- Requires: AWS credentials (from vault or frontend modal)
- Steps: provision EC2 t3.micro → upload JAR via SSH → run java -jar on port 8080
- Returns: `{ endpoint: "http://<ip>:8080", deployed_by: wallet, payment: {...} }`

### Path B — Algorand dApp → Algorand TestNet + AWS Amplify
- Trigger: `project_type == "algorand_dapp"` OR `is_algorand_dapp == true`
- Detection signals (checked before LLM): algokit.toml, algopy/pyteal imports, .teal files, arc32.json
- Steps:
  1. Compile contract (algokit if available)
  2. Deploy via ABI spec (application.json) OR raw TEAL fallback
  3. If frontend/ dir exists → deploy to Amplify
- Returns: `{ app_id, app_address, explorer_url, endpoint (frontend URL) }`

### Path C — Frontend → AWS Amplify
- Trigger: `project_type == "frontend"` OR `language == "static"`
- Sub-path C1: GitHub URL + PAT → Amplify CI/CD connected to GitHub repo
- Sub-path C2: ZIP or no PAT → build locally (npm install + npm run build) → upload to Amplify
- Returns: `{ endpoint: "https://<branch>.<appId>.amplifyapp.com" }`

### Path D — Backend / Fullstack → AWS EC2
- Trigger: `project_type in ["backend", "fullstack"]`
- Languages: Python (FastAPI/Flask), Node.js (Express)
- Steps: provision EC2 → SCP zip → install runtime → start with PM2 on port 8080
- Returns: `{ endpoint: "http://<ip>:8080" }`

---

## Wallet Login Flow (Lute)

```
1. Frontend calls POST /auth/challenge with wallet_address
2. Backend returns challenge string: "dePro-login-<random>-<timestamp>"
3. Frontend calls window.lute.signBytes(challenge, address)
4. Lute popup appears — user clicks SIGN
5. Frontend sends signature to POST /auth/verify
6. Backend runs algosdk.util.verify_bytes() — cryptographic proof of wallet ownership
7. Backend issues JWT session token (24 hour expiry)
8. Frontend stores token in localStorage
9. All subsequent requests include: Authorization: Bearer <token>
```

---

## x402 Payment Flow

```
1. User uploads project — backend analyses and knows deployment_type
2. If no payment_tx_id in request → backend returns HTTP 402:
   { amount_algo: 2, receiver: "DEPRO_TREASURY...", deployment_type: "algorand_dapp" }
3. Frontend shows Payment Modal
4. User opens Lute → sends ALGO to treasury address
5. User finds TX ID in Lute transaction history
6. User pastes TX ID into modal → clicks VERIFY & DEPLOY
7. Frontend calls POST /x402/verify → backend checks TX on Algorand:
   ✓ TX exists on TestNet
   ✓ Receiver = dePro treasury
   ✓ Amount >= required fee
   ✓ TX not already used (replay prevention)
8. Frontend re-submits upload with payment_tx_id included
9. Deployment executes
10. Result includes payment receipt
```

---

## Credential Vault Security Model

```
User types:    AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY

Step 1 — Box label (SHA-256 hash):
  sha256(AWS_ACCESS_KEY_ID) = 32-byte box key
  One-way. Cannot reverse to get the access key.

Step 2 — Encryption key (HKDF-SHA256):
  HKDF(
    ikm  = Algorand private key bytes  ← never leaves server, in .env mnemonic
    salt = AWS_ACCESS_KEY_ID           ← per-user salt
    info = b"opsonic-aws-creds-v1"    ← domain separation
  ) = 32-byte AES key
  Never stored. Deterministically recreated on demand.

Step 3 — Encryption (AES-256-GCM):
  encrypted_blob = AES_GCM_Encrypt(
    key       = 32-byte key from Step 2
    plaintext = JSON({ access_key, secret_key, region })
    nonce     = 12 random bytes
  )
  GCM auth tag detects any tampering.

Step 4 — Store on Algorand:
  Box key   = sha256(access_key_id)
  Box value = base64(nonce + ciphertext + auth_tag)
  Cost      = ~0.097 ALGO (refundable deposit)

Retrieval:
  User provides access_key_id only
  → Backend recreates encryption key (same HKDF inputs)
  → Fetches encrypted blob from Algorand (free, read-only)
  → Decrypts in memory
  → Injects into environment for deployment
  → Discards after use
```

---

## Algorand dApp Detection Pipeline

The code review layer runs three static analysis stages BEFORE calling the LLM:

### Stage 1 — repo_scanner.py
Walks directory tree and collects `algorand_signals` list:
- `config:algokit.toml` — strongest signal, AlgoKit project marker
- `algorand_import:path/to/file.py` — .py file importing algopy, pyteal, or beaker
- `teal_file:path/to/file.teal` — compiled TEAL output
- `dir:smart_contracts` — directory named smart_contracts, contracts, or artifacts

### Stage 2 — dependency_analyzer.py
Reads requirements.txt and pyproject.toml for:
`pyteal`, `algopy`, `algokit-utils`, `beaker`, `algosdk`
Sets `is_algorand_project = True` if any Algorand library found.
Also reads algokit.toml if present.

### Stage 3 — repo_reasoner.py (LLM)
Sends all signals plus file structure to Ollama with strict instruction:
"If ANY algorand signal exists → project_type MUST be algorand_dapp"

### Safety Net — reviewer.py
If static analysis says `is_algorand_project = True` but AI returned something else,
the result is overridden to `algorand_dapp`. The AI cannot miss an Algorand project.

---

## Algorand Infrastructure Details

### Vault Contract
- App ID: 757482499 (deployed on Algorand TestNet)
- Creator: 7UCTS3PFI3ARHWEONK4SVTMW643WBANSLT6CPLATRAIRTUPCDIRZEOOK54
- Logic: only creator can write/delete boxes, anyone can read (data encrypted anyway)
- Box storage: key = sha256(access_key_id), value = AES-256-GCM encrypted blob

### EC2 Instances
- Region: ap-south-1 (Mumbai)
- AMI: ami-0ff91eb5c6fe7cc86 (Ubuntu 24.04 LTS)
- Instance type: t3.micro
- Security group: ports 22, 80, 8080 open
- Process manager: PM2 keeps apps alive after SSH termination

### Amplify
- Build image: amplify:al2023 (Amazon Linux 2023)
- Node version: 20 (via nvm in build spec)
- Supports: React, Vite, Next.js, static sites
- CI/CD mode: connects GitHub repo, auto-deploys on push

---

## x402 Deployment Fee Table

| Deployment Type | Fee |
|----------------|-----|
| Frontend (Amplify) | 1 ALGO |
| Backend (EC2) | 3 ALGO |
| Fullstack (EC2) | 3 ALGO |
| Algorand dApp (contract + Amplify) | 2 ALGO |
| Java JAR (EC2) | 3 ALGO |

All fees go to: `DEPRO_TREASURY_ADDRESS` in .env (your Lute wallet)

---

## Frontend Components (all in App.jsx)

### WalletConnect
- Reads window.lute (Lute browser extension, no npm package needed)
- Calls /auth/challenge → window.lute.signBytes() → /auth/verify
- Stores token in localStorage, restores session on page load
- Shows: CONNECT LUTE button (disconnected) or 🟢 LUTE | ABC...XYZ + DISCONNECT (connected)

### PaymentModal
- Shown automatically when backend returns HTTP 402
- Displays required fee, copy-able treasury address, TX ID input
- Calls /x402/verify before allowing deployment to proceed
- Amber/yellow themed to distinguish from other modals

### AwsAuthModal
- Shown when user uploads a JAR
- Checks /vault/check onBlur of access key field
- If vault entry found: hides secret key input, button says RETRIEVE & DEPLOY
- If not found: shows secret key input, button says ENCRYPT & DEPLOY
- Yellow themed

### GithubAuthModal
- Shown when user pastes a github.com URL
- Optional PAT field — with PAT enables CI/CD, without PAT does snapshot
- Purple themed

### SuccessCard
- Shows deployment result
- For algorand_dapp: shows App ID + contract address + Algorand Explorer link
- For all types: shows live URL
- Shows payment receipt (ALGO paid + TX ID)
- Shows deployed_by wallet address

---

## Files NOT to Touch

These files are unchanged from the original dePro and work correctly:
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

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Vite 7, Tailwind CSS 4 |
| Wallet | Lute (window.lute browser extension) |
| API Server | FastAPI + Uvicorn |
| Code Analysis | Custom Python pipeline (3 stages) |
| AI Reasoning | Ollama gpt-oss:20b via custom host |
| Credential Encryption | AES-256-GCM + HKDF-SHA256 (cryptography lib) |
| Algorand SDK | py-algorand-sdk (algosdk) |
| Algorand Deployment | algokit-utils ApplicationClient |
| Algorand Storage | Box storage via algod API |
| Payment Protocol | x402 (HTTP 402 + on-chain TX verification) |
| AWS EC2 | boto3 + Paramiko (SSH) |
| AWS Amplify | boto3 amplify client |
| Process Manager | PM2 (on EC2) |
| Git Cloning | GitPython |

---

## Known Constraints

- Algorand deployments target TestNet only. For MainNet change ALGOD_SERVER.
- EC2 provisioned in ap-south-1. Configurable via AWS_DEFAULT_REGION.
- Lute wallet requires the browser extension installed — no mobile app support.
- x402 replay prevention uses in-memory set — restarting backend clears it (fine for hackathon).
- Vault mnemonic in .env is the master key — losing it loses vault access.
- Algorand dApp detection works best with AlgoKit projects (algokit.toml + application.json).
- Raw PyTeal projects need approval.teal and clear.teal files present for raw TEAL deployment path.
- Frontend port: backend runs on 8000, frontend dev server on 5173.

---

## One-Time Setup (already done, do not repeat)

```
Vault contract deployed:  App ID 757482499
Contract funded:          0.5 ALGO sent to KSSAXNR... (contract account)
Deployer wallet:          7UCTS3PFI3ARHWEONK4SVTMW643WBANSLT6CPLATRAIRTUPCDIRZEOOK54
Treasury wallet:          same address (fees go to same wallet for hackathon)
```

---

## How to Run

```bash
# Terminal 1 — Backend
cd backend
uvicorn app:app --host 0.0.0.0 --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

Open browser at http://localhost:5173
