# Real Estate Property Management App

A full-stack property management platform built with Django REST Framework + SvelteKit.

## Stack

| Layer | Technology |
|---|---|
| Backend API | Django 5 + Django REST Framework |
| Auth | JWT (SimpleJWT) with token rotation + blacklist |
| Task queue | Celery + Redis |
| Scheduled tasks | Celery Beat (DatabaseScheduler) |
| Database | PostgreSQL 16 |
| Frontend | SvelteKit 2 + Tailwind CSS 3 |
| Containerisation | Docker Compose |

---

## Quick start

```bash
# 1. Clone and copy env
cp .env.example .env

# 2. Start all services
docker compose up --build

# 3. Create a superuser (first time only)
docker compose exec api python manage.py createsuperuser

# 4. (Optional) Seed demo data
docker compose exec api python manage.py seed_data
```

- **API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/api/docs/
- **Django admin**: http://localhost:8000/admin/
- **Frontend**: http://localhost:5173

Demo credentials after `seed_data`:

| Username | Password | Role |
|---|---|---|
| admin | Admin1234! | Admin |
| manager | Manager1234! | Manager |
| accountant | Account1234! | Accountant |

---

## Project structure

```
real-estate-app/
├── apps/
│   ├── api/                  # Django backend
│   │   ├── config/           # Settings, URLs, Celery
│   │   ├── core/             # User model, RBAC, auth views
│   │   ├── portfolio/        # Owners, Properties, Units
│   │   ├── tenants/          # Tenants, Leases + services
│   │   ├── billing/          # Invoices, Payments, Allocations
│   │   │   └── services/     # invoice_service, payment_service, allocation_service, arrears_service
│   │   ├── deposits/         # Security deposit tracking
│   │   ├── audit/            # Immutable audit log
│   │   ├── notifications/    # Email notifications + Celery tasks
│   │   └── reports/          # Dashboard KPIs + CSV exports
│   └── web/                  # SvelteKit frontend
│       └── src/
│           ├── lib/
│           │   ├── api/      # Typed API client
│           │   ├── stores/   # Auth store
│           │   ├── utils/    # Formatting, status helpers
│           │   └── components/ # Badge, Modal, DataTable, Pagination
│           └── routes/
│               ├── (auth)/login/
│               └── (app)/    # Protected routes
├── compose.yml
└── .env.example
```

---

## RBAC roles

| Role | Read | Write (CRUD) | Finance (invoices/payments) | Admin |
|---|---|---|---|---|
| `read_only` | ✅ | ❌ | ❌ | ❌ |
| `agent` | ✅ | ✅ | ❌ | ❌ |
| `accountant` | ✅ | ✅ | ✅ | ❌ |
| `manager` | ✅ | ✅ | ✅ | ❌ |
| `admin` | ✅ | ✅ | ✅ | ✅ |

Admin-only operations: hard delete (with full audit snapshot), allocation removal.

---

## Billing engine

### Invoice generation
- Idempotent: calling `generate_invoice(lease, period_start, actor)` twice returns the same invoice
- Supports `LEASE_START` anchor (rolling 1st = lease start date) and `MONTH_START` anchor (calendar 1st)
- Optional prorated stub invoice for mid-month starts
- Celery beat runs daily at 01:00 to generate all due invoices

### Payment & allocation
- Payments are posted against a lease, then allocated to invoices
- Allocation validates: payment unallocated amount ≥ allocation, invoice balance ≥ allocation
- Invoice status auto-updates: `issued` → `partially_paid` → `paid`
- Voiding a payment reverses all its allocations

### Late fees
- Configurable per lease: none / fixed amount / percentage of balance
- Grace period in days
- Generated daily by Celery beat

### Void vs hard delete
- **Void**: soft, keeps the record, sets status=void, blocks re-generation for same period
- **Hard delete**: admin-only, writes full JSON snapshot to `AuditLog` before deletion

---

## Scheduled tasks (Celery Beat)

| Task | Schedule | Description |
|---|---|---|
| `billing.tasks.generate_due_invoices` | Daily 01:00 | Generate rent invoices for all active leases |
| `billing.tasks.generate_late_fees` | Daily 02:00 | Generate late fee invoices |
| `notifications.tasks.send_rent_reminders` | Daily 08:00 | Send D-7 reminders |
| `notifications.tasks.send_overdue_notices` | Daily 09:00 | Send overdue notices |
| `notifications.tasks.send_lease_expiry_warnings` | Daily 08:30 | Send 30-day expiry warnings |

---

## Running tests

```bash
docker compose exec api pytest --cov=. --cov-report=term-missing
```

---

## Development commands

```bash
# Run migrations
docker compose exec api python manage.py migrate

# Create migration after model change
docker compose exec api python manage.py makemigrations

# Django shell
docker compose exec api python manage.py shell

# Celery worker logs
docker compose logs -f worker

# Frontend type check
docker compose exec web npm run check
```

---

## Environment variables

See `.env.example` for all variables. Key ones:

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis URL for Celery |
| `CORS_ALLOWED_ORIGINS` | Frontend origins |
| `USE_S3` | Set `True` to use S3 for media storage |
| `EMAIL_BACKEND` | Use `console` for dev, SMTP for prod |
