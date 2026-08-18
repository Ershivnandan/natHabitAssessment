# TaskFlow

A task-management API with asynchronous notifications. Users create projects,
assign tasks, and get notified when a task becomes overdue or is reassigned —
notifications are produced by a background worker, never in the request path.

Built with **FastAPI**, **PostgreSQL**, **Redis**, and **Celery** on Python 3.11+.

## Quick start

```bash
docker compose up --build
```

Brings up the API, Postgres, Redis, Celery worker, and beat. API at
http://localhost:8000, docs at http://localhost:8000/docs. Migrations run
automatically on startup.

```bash
# signup, then grab a token
curl -s -X POST localhost:8000/auth/signup -H 'content-type: application/json' \
  -d '{"email": "shiv@example.com", "password": "shiv@123"}'
TOKEN=$(curl -s -X POST localhost:8000/auth/login -H 'content-type: application/json' \
  -d '{"email": "shiv@example.com", "password": "shiv@123"}' | jq -r .access_token)
```

## Tests

Run against SQLite + fake Redis, so no external services are needed:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check . && pytest
```

## Architecture

Thin routes call service functions; all business logic and authorization live in
`app/services`, reusable from both the HTTP layer and the Celery workers.

- **Auth** — JWT bearer tokens (stateless, no shared session store to scale).
  Passwords hashed with bcrypt, never logged or returned.
- **Authorization** — every project/task is owner-scoped. Cross-user access
  returns `404`, not `403`, so the API doesn't leak resource existence.
- **Notifications** — reassignment enqueues a Celery job; Celery beat runs a
  periodic overdue sweep. Both are idempotent. Delivery is simulated (table row
  + log line).
- **Caching** — `GET /tasks` is Redis-backed. Keys embed the user, filters, and
  a per-user version counter that any task write increments, instantly orphaning
  stale listings — so a stale read after a status change can't happen.
- **Ops** — `/health` checks Postgres + Redis; `/metrics` exposes Prometheus
  request/error/latency, labeled by route template to bound cardinality.

## Deployment

Documented, not-live path. `render.yaml` provisions the web service, worker,
beat, managed Postgres, and Redis, wiring connections and generating the JWT
secret — a one-click "New Blueprint" on Render. Not run (no hosting account
provisioned); the same image/commands as `docker-compose.yml`.

## Tradeoffs & what I'd do with more time

Prioritised the highest-risk, hardest-to-retrofit areas: authorization
boundaries, correct cache invalidation, and getting notifications out of the
request path. Deprioritised, in order I'd pick them up:

- **Integration tests on real Postgres/Redis** (Testcontainers) — SQLite +
  fakeredis miss enum constraints, cascades, and real Redis semantics.
- **Real notification delivery** — email/webhook behind the same job, with
  retries and a dead-letter queue.
- **Overdue sweep at scale** — batching/keyset pagination and per-task locking.
- **Refresh tokens + revocation** — Redis-backed denylist for logout/rotation.
- **Rate limiting, business metrics, structured logging/tracing.**

### Assumptions

- Any registered user can be an assignee; there's no project-membership model.
- Only the project owner can act on its tasks.
- Notification recipients are the task's assignee (notifying owners is a follow-up).
