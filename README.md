# TaskFlow

A task-management API with asynchronous notifications. Users create projects,
assign tasks, and receive notifications when a task becomes overdue or is
reassigned. Notifications are produced by a background worker, never inside the
request/response cycle.

Built with **FastAPI**, **PostgreSQL**, **Redis**, and **Celery** on Python 3.11+.

## Quick start

The whole stack — API, Postgres, Redis, Celery worker, and Celery beat — comes
up with a single command:

```bash
docker compose up --build
```

The API is then available at http://localhost:8000, with interactive docs at
http://localhost:8000/docs. Database migrations run automatically when the API
container starts.

### Try it

```bash
# Register and log in
curl -s -X POST localhost:8000/auth/signup \
  -H 'content-type: application/json' \
  -d '{"email": "shiv@example.com", "password": "shiv@123"}'

TOKEN=$(curl -s -X POST localhost:8000/auth/login \
  -H 'content-type: application/json' \
  -d '{"email": "shiv@example.com", "password": "shiv@123"}' | jq -r .access_token)

# Create a project and a task
PROJECT=$(curl -s -X POST localhost:8000/projects \
  -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"name": "Launch"}' | jq -r .id)

curl -s -X POST localhost:8000/projects/$PROJECT/tasks \
  -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"title": "Write the spec", "status": "todo"}'

# Filtered, paginated listing (cache-backed)
curl -s "localhost:8000/tasks?status=todo&limit=20" -H "authorization: Bearer $TOKEN"
```

## Running the tests

Tests run against an in-memory SQLite database and a fake Redis, so no external
services are required:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest
```

## Architecture

```
app/
  api/routes/     HTTP layer — thin handlers, one router per resource
  api/deps.py     Auth dependency (JWT -> current user) and session provider
  core/           Config, database engine, security, cache, metrics
  models/         SQLAlchemy models (User, Project, Task, Notification)
  schemas/        Pydantic request/response models
  services/       Business logic and authorization (the layer routes call)
  workers/        Celery app, scheduled tasks, and enqueued jobs
migrations/       Alembic migrations
```

**Layering.** Routes stay thin: they validate input, call a service function,
and serialise the result. All business rules and authorization checks live in
`app/services`, which keeps them testable in isolation and reusable from both
the HTTP layer and the Celery workers.

**Authentication.** JWT bearer tokens. Passwords are hashed with bcrypt and are
never logged or returned in any response (the read schemas simply do not include
the field). JWT was chosen over server-side sessions because it is stateless,
which keeps the deployed API and its workers free of a shared session store and
makes the service trivial to scale horizontally.

**Authorization.** Every project and task access is scoped to the authenticated
owner. Requests for resources owned by another user return `404`, not `403`, so
the API does not leak the existence of resources the caller cannot see.

**Notifications (background jobs).** Notification creation never runs in the
request path:

- *Reassignment* — updating a task's assignee enqueues a Celery job
  (`notify_task_reassigned`) that writes the notification asynchronously.
- *Overdue* — Celery beat runs a periodic sweep (`scan_overdue_tasks`) that
  finds tasks past their due date that are not done and not yet notified,
  creates a notification, and marks the task so repeat sweeps stay idempotent.

Delivery is simulated: notifications are persisted to the `notifications` table
and written to the application log. No real email/SMS integration is involved.

**Caching.** `GET /tasks` is backed by Redis. Cache keys embed the requesting
user, the active filter/pagination parameters, and a per-user *version counter*.
Any task write (create, update, delete) increments that user's counter via
`bump_task_cache_version`, which instantly orphans all of their previously
cached listings — so a stale read after a status change cannot occur. Using a
version pointer rather than deleting individual keys keeps invalidation O(1)
regardless of how many filter combinations were cached; orphaned entries expire
naturally via their TTL.

**Operational endpoints.** `GET /health` verifies connectivity to Postgres and
Redis and reports per-dependency status. `GET /metrics` exposes Prometheus
counters and a latency histogram, populated by an ASGI middleware that labels by
route template (not raw path) to keep cardinality bounded.

## Deployment

I chose the **documented, not-live** path. A `render.yaml` blueprint is included
that provisions the web service, Celery worker, Celery beat, a managed Postgres
instance, and Redis, wiring the connection strings between them and generating
the JWT secret. Deploying is a one-click "New Blueprint" on Render pointed at
this repository; I have not run it, as no hosting account is provisioned for the
submission. The same image and commands used by `docker-compose.yml` are what
Render runs, so the local and deployed stacks are identical.

## Tradeoffs & what I'd do with more time

This assignment is deliberately larger than can be polished end-to-end, so I
prioritised the areas that carry the most risk and are hardest to retrofit:
authorization boundaries, correct cache invalidation, and getting notifications
genuinely out of the request path. Here is what I consciously deprioritised and
would pick up next, roughly in order:

- **Integration tests against real Postgres/Redis.** The suite runs on SQLite +
  fakeredis for speed and zero setup. This covers logic well but not
  Postgres-specific behaviour (enum check constraints, `ON DELETE` cascades) or
  real Redis semantics. I'd add a Testcontainers-based tier in CI to close that
  gap.
- **Notification fan-out and delivery.** Delivery is a log line plus a table
  row. In production I'd add a real channel (email/webhook) behind the same job,
  with retries and a dead-letter queue, and likely notify the project owner in
  addition to the assignee.
- **Overdue sweep at scale.** The sweep is a single query flagging rows with a
  boolean. That is fine for this size but would need batching/keyset pagination
  and a per-task lock to be safe under a large backlog with multiple workers.
- **Refresh tokens and revocation.** Access tokens are short-lived but there is
  no refresh flow or revocation list. I'd add refresh tokens and a Redis-backed
  denylist for logout/rotation.
- **Rate limiting and richer metrics.** No rate limiting yet; `/metrics` covers
  request/error/latency but not business metrics (notifications emitted, cache
  hit ratio), which I'd add next.
- **Observability.** Structured JSON logging with request IDs and tracing would
  be the next step for a real deployment.

### Assumptions

- "Assignee" is any registered user; there is no project-membership model, so a
  task can be assigned to any user id. A membership/roles model would be the
  natural next iteration.
- Only the project owner can act on its tasks. Shared/collaborator access was
  out of scope for the stated requirements.
- Notification recipients are the task's assignee. Notifying owners as well is
  noted above as a follow-up.
