# AI for Controls — Policy Control Automation Platform

A modern, production-grade compliance control automation platform that translates natural-language regulatory policies into verified, auditable database retention workflows.

The system is configured and confined to the **Default Compliance DB (SQLite) [SQLITE]** (`ai_controls.db`), featuring live dual-table management, archive-first cryptographic safety, human-in-the-loop approvals, and automated SQLite query generation.

---

## 🏗️ System Architecture

```
┌─────────────────────────────────┐
│     React + Vite Frontend       │ (Port 5173: Responsive Top-to-Bottom UI)
└────────────────┬────────────────┘
                 │ REST API (JSON)
┌────────────────▼────────────────┐
│      FastAPI Backend Engine     │ (Port 8000: Async Python & SQLAlchemy)
├────────────────┬────────────────┤
│  Rule Engine   │ Gemini 2.5 LLM │ (Natural Language Policy → Structured Rules)
└────────┬───────┴────────┬───────┘
         │                │
┌────────▼────────────────▼───────────────────────────────────────────────┐
│             Default Compliance DB (SQLite) [SQLITE]                    │
│                        (ai_controls.db)                                 │
│                                                                         │
│  🟢 source_transactions (Active)   ──▶  📦 archive_transactions (Archive)│
│     Operational records                   Immutable records with        │
│     Subject to retention policy           SHA-256 cryptographic hashes  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔒 Safety-First Compliance Lifecycle

The platform enforces a strict 10-step regulatory compliance lifecycle:

1. **Policy Ingestion**: Upload compliance documents (PDF/TXT) outlining data retention and regulatory mandates.
2. **AI Policy Analysis**: Google Gemini extracts structured retention criteria, entity scopes, thresholds, and legal hold exemptions.
3. **Structured Rule Engine**: Schema-aware validation ensures rules only execute against relevant target entities.
4. **Active Selection**: Generates dialect-accurate SQLite `SELECT` queries to isolate eligible records while honoring legal holds (`legal_hold = 0`).
5. **Archive-First Execution**: Eligible records are copied to `archive_transactions` with cryptographic SHA-256 checksums before any deletion can occur.
6. **Independent Hash Verification**: Automated SHA-256 hash reconciliation verifies archive integrity between source and target storage.
7. **Human Approval Gate**: Two-person approval workflow with mandatory compliance officer review and sign-off.
8. **Controlled Source Cleanup**: Generates and executes verified SQLite `DELETE` queries strictly targeting approved records.
9. **Final Dual-Database Reconciliation**: Verifies zero remnants remain in the active source database while confirming archive persistence.
10. **Immutable Audit Evidence**: Every action, actor, timestamp, and query is permanently recorded in the audit trail.

---

## 🗄️ Database Environment

The system is strictly confined to:

- **Database**: `Default Compliance DB (SQLite)`
- **File**: `backend/ai_controls.db`
- **Dialect**: `SQLite` (`sqlite+aiosqlite:///./ai_controls.db`)
- **Concurrency Mode**: `WAL` (Write-Ahead Logging enabled for seamless simultaneous viewing in DB Browser for SQLite and FastAPI)
- **Active Table**: `source_transactions`
- **Archive Table**: `archive_transactions`

---

## 🚀 Quick Start Guide

### Prerequisites

- **Python**: 3.11+
- **Node.js**: 18+ (with npm)
- **Git**

---

### 1. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment
# Windows (PowerShell):
python -m venv .venv
.venv\Scripts\Activate.ps1

# Linux / macOS:
# python3 -m venv .venv
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
# Copy or create .env (see Backend Environment Variables below)
cp .env.example .env

# Run FastAPI development server
uvicorn app.main:app --reload --port 8000
```

Backend API will be running at: `http://localhost:8000`  
Interactive Swagger Docs: `http://localhost:8000/docs`

---

### 2. Frontend Setup

```bash
# Open a new terminal and navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Start Vite development server
npm run dev
```

Frontend application will be running at: `http://localhost:5173`

---

## ⚙️ Configuration & Environment Variables

### Backend (`backend/.env`)

```ini
# Application Environment
ENVIRONMENT=development
LOG_LEVEL=INFO

# Default SQLite Compliance Database
DATABASE_URL=sqlite+aiosqlite:///./ai_controls.db

# Authentication Security
JWT_SECRET=your-super-secret-jwt-key-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Google Gemini AI Configuration
GEMINI_API_KEY=your_google_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# CORS Settings (Allow Frontend)
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

### Frontend (`frontend/.env`)

```ini
VITE_API_URL=http://localhost:8000
```

---

## 📁 Repository Structure

```
├── backend/
│   ├── app/
│   │   ├── api/routes/          # FastAPI route handlers (control runs, policies, approvals, audit)
│   │   ├── core/                # DB engine, config, and security
│   │   ├── engines/             # Rule engine and Gemini LLM policy analyzer
│   │   ├── models/              # SQLAlchemy ORM models (Source & Archive transactions, runs, policies)
│   │   ├── schemas/             # Pydantic validation schemas
│   │   └── services/            # Database seeder and SQLite profile registry
│   ├── ai_controls.db           # SQLite database (auto-created on startup)
│   ├── requirements.txt         # Python dependencies
│   └── uploads/                 # Storage for uploaded policy documents (.gitkeep tracked)
├── frontend/
│   ├── src/
│   │   ├── components/          # Reusable UI components
│   │   ├── pages/               # Pages (Dashboard, Policies, ControlRuns, Approvals, AuditEvidence)
│   │   ├── services/            # Axios API client modules
│   │   ├── index.css            # Design system, variables, responsive layout
│   │   └── App.jsx              # Routing & application shell
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── .gitignore                   # Comprehensive repository ignore rules
└── README.md                    # Project documentation
```

---

## 🔍 Database Inspection & Tools

You can inspect the database in two ways:

1. **Inside the App**: Navigate to **Control Runs** → select any run → use the live tabbed database viewer:
   - **Active DB (`source_transactions`)**: Live view of current operational records.
   - **Archive DB (`archive_transactions`)**: Live view of archived records with SHA-256 hashes.
   - **Evaluation**: Record-by-record breakdown of eligibility and hold statuses.
2. **External GUI (DB Browser for SQLite)**:
   - Open `backend/ai_controls.db` directly in [DB Browser for SQLite](https://sqlitebrowser.org/).
   - Thanks to SQLite WAL mode (`PRAGMA journal_mode=WAL`), you can browse records and run queries in DB Browser without encountering database lock errors while the FastAPI server is running.

---

## 🛡️ License & Disclaimers

Built for automated data governance and compliance auditability. Adheres to SOC2, GDPR, and FINRA archive-first safety protocols.
