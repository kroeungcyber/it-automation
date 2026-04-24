# IT Automation System

An internal automation platform that lets IT staff submit tasks (like running commands on servers or managing user accounts) through a safe, controlled pipeline. Every action is classified, reviewed if risky, and logged with a tamper-evident audit trail.

---

## What It Does

1. **Receives task requests** — via Slack bot, CLI, or web portal.
2. **Classifies the risk** — low, medium, or high, based on YAML rules and an AI classifier.
3. **Runs a safety check (GuardRail Gate)** — blocks dangerous actions, requires human approval for high-risk ones, and stops runaway agents via a circuit breaker.
4. **Logs everything** — every decision is written to PostgreSQL with a cryptographic hash chain so nothing can be quietly edited.
5. **Controls who can do what** — three-tier role system (Employee → IT Admin → Super Admin) enforced on every endpoint.

---

## Roles

| Role | Can do |
|---|---|
| **Employee** | Submit tasks, log out, view own profile |
| **IT Admin** | Everything above + approve/deny actions, view circuit breaker status |
| **Super Admin** | Everything above + reset circuit breakers, read audit log |

---

## Main Endpoints

### Auth
| Method | Path | Description |
|---|---|---|
| POST | `/auth/login` | Get a token (username + password) |
| POST | `/auth/logout` | Invalidate your token |
| GET | `/auth/me` | See your user info |

### GuardRail
| Method | Path | Who |
|---|---|---|
| POST | `/guardrail/authorize` | IT Admin+ |
| POST | `/guardrail/approvals/{id}/decision` | IT Admin+ |
| GET | `/guardrail/circuit-breaker/status` | IT Admin+ |
| POST | `/guardrail/circuit-breaker/reset` | Super Admin only |

### Audit
| Method | Path | Who |
|---|---|---|
| GET | `/audit/log` | Super Admin only |

---

## How to Run Locally

**Requirements:** Docker, Docker Compose, Python 3.12

```bash
# 1. Copy and fill in the environment file
cp .env.example .env
# Set DATABASE_URL, REDIS_URL, ANTHROPIC_API_KEY, JWT_SECRET, etc.

# 2. Start the database and Redis
docker-compose up postgres redis -d

# 3. Apply migrations
psql $DATABASE_URL -f src/db/migrations/001_initial.sql
psql $DATABASE_URL -f src/db/migrations/002_guardrail_audit.sql
psql $DATABASE_URL -f src/db/migrations/003_create_users.sql

# 4. Install dependencies
pip install -e ".[dev]"

# 5. Run the app
uvicorn src.router.app:app --reload
```

Or run everything with Docker:

```bash
docker-compose up --build
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

---

## Running Tests

```bash
pytest tests/ -q
```

189 tests covering unit logic and end-to-end API flows.

---

## Project Layout

```
src/
  auth/          # Login, logout, JWT tokens, role enforcement
  guardrail/     # Safety pipeline — risk classification, approval, circuit breaker, audit
  router/        # Task intake — classify, scan, queue
  db/            # Database connection and migrations
  shared/        # Logging setup
config/
  guardrail_rules.yaml   # Risk classification rules
tests/
  unit/          # Fast, no external dependencies
  integration/   # Full request-response flows (mocked DB/Redis)
```

---

## Tech Stack

- **Python 3.12**, FastAPI, Pydantic v2
- **PostgreSQL** — tasks and audit records
- **Redis** — job queues, approval state, circuit breaker, token revocation
- **SQLAlchemy 2** — async (app) + sync (audit writes)
- **PyJWT + bcrypt** — authentication
- **Ollama** (local) + **Claude** (cloud) — AI-assisted task classification
- **Docker Compose** — local development stack
