# AI-Powered IT Automation System — Design Spec

**Date:** 2026-04-11
**Status:** Approved

---

## 1. Overview

A modular, hybrid AI automation platform for a mid-size organization (50–500 endpoints) with a dedicated IT team. The system handles three classes of triggers — end-user self-service, IT staff-driven operations, and event/schedule-driven automation — across six intake interfaces (Slack, Teams, Jira SM, ServiceNow, Web Portal, CLI).

A hard security boundary separates sensitive operations (handled by Gemma 4 running locally on-prem, air-gapped) from non-sensitive knowledge tasks (handled by the Claude API in the cloud). Misclassification defaults to LOCAL — the system never routes sensitive data to the cloud by accident.

---

## 2. Context & Constraints

| Dimension | Detail |
|-----------|--------|
| Scale | 50–500 endpoints, dedicated IT team |
| Infrastructure | Hybrid: on-prem servers + cloud (AWS/Azure/GCP) |
| Intake interfaces | Slack bot, Teams bot, Jira/ServiceNow, Web Portal, CLI |
| Existing tooling | Jira Service Management, ServiceNow, Slack, Microsoft Teams |
| AI split | Gemma 4 (local/on-prem) for sensitive ops; Claude API for non-sensitive |

---

## 3. Architecture

**Pattern:** Modular Service Architecture with a central Task Router and Redis task queue.

```
┌─────────────────────────────────────────────────────┐
│                  INTAKE ADAPTERS                     │
│  Slack Bot · Teams Bot · Jira/SM · Web Portal · CLI  │
└───────────────────────┬─────────────────────────────┘
                        │ TaskRequest (normalized)
                        ▼
┌─────────────────────────────────────────────────────┐
│              TASK ROUTER                             │
│  Classifier (keyword rules → spaCy fallback)         │
│  Task state: PostgreSQL                              │
│  Fail-safe: ambiguous → LOCAL                        │
└──────────────┬──────────────────────┬───────────────┘
               │                      │
       sensitive-queue          cloud-queue
       (Redis, on-prem)        (Redis, outbound ok)
               │                      │
┌──────────────▼──────┐   ┌──────────▼────────────────┐
│  LOCAL AI WORKER    │   │  CLOUD AI WORKER           │
│  Gemma 4 / Ollama   │   │  Claude API                │
│  [AIR-GAPPED]       │   │  (claude-sonnet-4-6)       │
│                     │   │                            │
│  Execution Agents:  │   │  Tools:                    │
│  • Secrets Vault    │   │  • KB Search               │
│  • SSH Executor     │   │  • Doc Writer              │
│  • Backup Agent     │   │  • Log Reader              │
│  • AD/LDAP Agent    │   └──────────────────────────┘
└─────────────────────┘
               │                      │
               └──────────┬───────────┘
                          ▼
┌─────────────────────────────────────────────────────┐
│                SHARED SERVICES                       │
│  Notification Service · Audit Logger · Scheduler    │
│  Auth / RBAC                                         │
└─────────────────────────────────────────────────────┘
```

---

## 4. AI Routing Boundary

### Sensitive → LOCAL (Gemma 4, on-prem, air-gapped)

- Credential management (passwords, API keys, certificates)
- Server admin commands (SSH, remote execution, config changes)
- Backup and restore operations
- User account management (AD/LDAP provisioning and deprovisioning)
- Audit logs and access records

### Non-Sensitive → CLOUD (Claude API)

- IT request triage and knowledge answers
- Documentation generation
- Chatbot / self-service responses
- Non-sensitive diagnostics
- Network configuration guidance

### Classification Logic

1. **Pass 1 — Keyword/regex rules** (fast, deterministic, configurable YAML)
2. **Pass 2 — spaCy intent model** (only for ambiguous cases)
3. **Fail-safe:** ambiguous requests always route LOCAL
4. **Pre-dispatch payload scanner:** strips known secret patterns from any payload before cloud dispatch; any match re-routes LOCAL and raises an alert

---

## 5. Data Flow

1. **User submits request** via any adapter (Slack, Teams, Jira/SM, Web Portal, CLI)
2. **Adapter normalizes** input to `TaskRequest` schema:
   ```json
   {
     "id": "uuid",
     "source": "slack|teams|jira|portal|cli",
     "user_id": "string",
     "org_role": "string",
     "raw_input": "string",
     "context": { "device": "optional", "ticket_id": "optional", "urgency": "normal|high" },
     "timestamp": "ISO8601"
   }
   ```
3. **Router classifies** the request and writes task record to PostgreSQL (`status: queued`)
4. **Task enqueued** to `sensitive-queue` or `cloud-queue`
5. **AI worker picks up task**, generates action plan (Gemma 4 or Claude API)
6. **Execution agent** performs the action (LOCAL path only — SSH, Vault, Backup, AD/LDAP)
7. **Audit log written** — sensitive logs to on-prem PostgreSQL only; non-sensitive logs may flow to central aggregator
8. **Notification Service** routes result back to originating adapter; task record updated to `completed` or `failed`

---

## 6. Components

### Intake Adapters

Each adapter is a thin normalization layer. Adapters are independently deployable.

| Adapter | SDK/Protocol |
|---------|-------------|
| Slack Bot | slack-bolt (Socket Mode) |
| Teams Bot | Bot Framework SDK |
| Jira Service Management | Jira REST API v3 |
| ServiceNow | ServiceNow REST API |
| Web Portal | FastAPI + simple frontend |
| CLI | Click (Python) |

### Task Router

- FastAPI service
- Exposes a single `POST /tasks` endpoint consumed by all adapters
- Runs two-pass classifier on every request
- Writes to PostgreSQL and pushes to Redis queue
- Exposes `GET /tasks/{id}` for status polling

### Local AI Worker (Gemma 4)

- Python RQ worker process, on-prem only
- Runs Gemma 4 via Ollama (GPU-preferred, CPU fallback)
- Has no outbound internet access
- Calls execution agents over local network only
- Prompt templates managed as Jinja2 files per action type

### Cloud AI Worker (Claude API)

- Python RQ worker process
- Calls `claude-sonnet-4-6` via Anthropic SDK
- Payload pre-scanned for secrets before dispatch
- Tools: KB search, document writer, log reader (read-only, non-sensitive sources)

### Execution Agents

| Agent | Responsibility | Interface |
|-------|---------------|-----------|
| Secrets Vault Agent | Read/write credentials | HashiCorp Vault API |
| SSH Executor | Remote command execution | Paramiko |
| Backup Agent | Trigger/verify backup jobs | Shell + backup tool API |
| AD/LDAP Agent | User provisioning/deprovisioning | ldap3 |

### Shared Services

- **Notification Service:** Routes task results back to source adapter (Slack DM, Jira comment, Portal update, CLI stdout)
- **Audit Logger:** Dual-writer — sensitive events to on-prem PostgreSQL only; non-sensitive to central log aggregator (Datadog/Splunk)
- **Scheduler:** APScheduler for cron/event-driven triggers; emits TaskRequests like any other adapter
- **Auth/RBAC:** Role-based permission checks before classification; violations logged and rejected with escalation path

---

## 7. Tech Stack

| Layer | Choice |
|-------|--------|
| Language | Python 3.12 |
| API framework | FastAPI |
| Task queue | Redis + RQ |
| Task state | PostgreSQL |
| Local AI runtime | Ollama (Gemma 4) |
| Cloud AI | Anthropic SDK (claude-sonnet-4-6) |
| NLP classifier | spaCy (fallback only) |
| Prompt management | Jinja2 templates |
| SSH | Paramiko |
| LDAP | ldap3 |
| Secrets | HashiCorp Vault |
| Metrics | Prometheus + Grafana |
| Tracing | OpenTelemetry (task_id as trace ID) |
| Logging | structlog |
| Containerization | Docker Compose (dev) → optional Kubernetes (prod) |
| Config | YAML + environment variables (no secrets in code) |

---

## 8. Error Handling

| Failure | Severity | Behavior |
|---------|----------|----------|
| Gemma 4 / Ollama unreachable | HIGH | Retry 3× with backoff → dead-letter queue → alert IT admin + notify user |
| Claude API rate-limited / down | MED | Exponential backoff → queue for later → user notified of delay |
| Classifier ambiguity | LOW | Always routes LOCAL (fail-safe); logs reason for tuning |
| SSH / execution agent failure | HIGH | Capture stderr + exit code → structured error in task result → rollback if applicable → alert |
| AD/LDAP connector down | HIGH | Task held in queue; IT admin alerted; user told "provisioning pending" |
| Redis queue full / down | HIGH | Adapters return 503; user sees "system busy"; tasks not accepted until queue recovers |
| Sensitive data in cloud payload | HIGH | Pre-dispatch scanner blocks + re-routes LOCAL + raises alert |
| RBAC violation | MED | Rejected before classification; audit log entry written; user given escalation path |

---

## 9. Testing Strategy

### Unit Tests (pytest, no external deps)

- TaskRequest schema validation for all adapter inputs
- Every classifier keyword/regex rule has a passing test case
- Payload scanner — verifies secrets stripped before cloud dispatch
- RBAC permission checks per action type per role
- Retry/backoff logic with mocked failures
- Notification routing correctness

### Integration Tests (pytest + Docker Compose, real Redis + PostgreSQL, mocked AI)

- End-to-end task lifecycle: intake → queue → worker → result → notification
- Sensitive vs non-sensitive routing — tasks land in correct queue
- Dead-letter queue behavior on repeated worker failure
- Audit log isolation — sensitive logs must not appear in non-sensitive store
- Adapter normalization — all sources produce valid TaskRequest

### Classifier Validation Suite (golden dataset, CI-blocking)

A golden dataset of labeled request samples. CI fails on any regression.

| Input | Expected | Test type |
|-------|----------|-----------|
| "Reset Alice's AD password" | LOCAL | Exact match |
| "Run backup job on server-02" | LOCAL | Exact match |
| "SSH into db-prod and check disk" | LOCAL | Exact match |
| "What's our VPN setup guide?" | CLOUD | Exact match |
| "My laptop can't connect to WiFi" | CLOUD | Exact match |
| "Check server logs" (ambiguous) | LOCAL (fail-safe) | Ambiguity test |
| Payload with "password=abc123" | SCANNER BLOCKS | Security test |

### Security Tests (CI-blocking)

- Local worker has zero outbound network calls during execution
- Cloud worker payload contains no credential patterns
- RBAC bypass attempts blocked
- Prompt injection in user input sanitized before AI dispatch
- Audit logs are append-only

### Load Tests (Locust, periodic)

- 50 concurrent tasks, measure end-to-end latency
- Ollama cold-start time after idle
- Claude API p95 latency under load
- Redis failover: primary down, queue drains to replica

---

## 10. Security Considerations

- Local AI worker has **no outbound internet access** (network-level enforcement)
- Sensitive audit logs are **physically separate** from non-sensitive logs
- Secrets never appear in task payloads — execution agents retrieve them directly from Vault at execution time
- All user inputs sanitized for prompt injection before dispatch to either AI
- RBAC enforced before classification — unauthorized requests never reach the AI layer
- `.superpowers/` directory added to `.gitignore` to prevent brainstorm artifacts from being committed
