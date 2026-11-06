# LogShift

**A lightweight, containerized log aggregation and monitoring platform built with Django and PostgreSQL.**

LogShift collects structured logs from multiple simulated services, stores them centrally, and provides APIs and a dashboard to search, filter, and monitor application events.

The project is designed to demonstrate practical DevOps concepts, including Docker containerization, persistent storage, health checks, automated testing, CI/CD, and cloud deployment.

## Features

- Centralized log ingestion through REST APIs.
- Single-event and batch log ingestion.
- Structured logging with a provider-neutral telemetry schema.
- PostgreSQL storage with JSON fields for flexible metadata.
- Log filtering by service, severity, and environment.
- Message search and timestamp-based filtering.
- Paginated log retrieval.
- Individual event lookup using event IDs.
- Dashboard displaying log statistics and recent events.
- Database health monitoring.
- Simulated payment, authentication, and order services.
- Automated tests using Django REST Framework.
- Docker Compose-based local deployment.

## Architecture

```text
 payment-service ──┐
 auth-service ─────┼──> Django REST API ───> PostgreSQL
 order-service ────┘           │
                               │
                         Dashboard
                               │
                         Log Explorer
```

The simulated services generate structured events and send them to LogShift over HTTP. Django validates and stores the events in PostgreSQL. The dashboard retrieves aggregated statistics and log records through the REST API.

## Technology Stack

| Component | Technology |
|---|---|
| Backend | Python, Django |
| API | Django REST Framework |
| Database | PostgreSQL 16 |
| Containerization | Docker |
| Container orchestration | Docker Compose |
| Application server | Gunicorn |
| Frontend | HTML, CSS, JavaScript |
| API testing | Postman |
| Automated testing | Django Test Framework |

## Project Structure

```text
LogShift/
├── app/
│   ├── config/
│   ├── logs/
│   ├── dashboard/
│   ├── manage.py
│   └── requirements.txt
├── simulated-services/
│   ├── payment_service.py
│   ├── auth_service.py
│   └── order_service.py
├── docs/
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .gitignore
├── .env.example
└── README.md
```

## Getting Started

### Prerequisites

- Docker Desktop
- Git
- Python 3.11 or later (for running simulated services locally)

### 1. Clone the repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd LogShift
```

### 2. Configure environment variables

Create a `.env` file in the project root using `.env.example` as a reference.

Configure the following values:

```env
SECRET_KEY=your-local-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=logshift
DB_USER=logshift_user
DB_PASSWORD=your-local-database-password
DB_HOST=db
DB_PORT=5432
```

Never commit your actual `.env` file or production secrets.

### 3. Build and start containers

```bash
docker compose up -d --build
```

### 4. Apply database migrations

```bash
docker compose exec web python manage.py migrate
```

### 5. Access LogShift

| Component | URL |
|---|---|
| Dashboard | http://localhost:8000/ |
| Health check | http://localhost:8000/health/ |
| Django Admin | http://localhost:8000/admin/ |
| Log ingestion API | http://localhost:8000/api/v1/logs/ |
| Statistics API | http://localhost:8000/api/v1/stats/ |

To create an admin account:

```bash
docker compose exec web python manage.py createsuperuser
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/logs/` | Ingest a single log |
| POST | `/api/v1/logs/batch/` | Ingest multiple logs |
| GET | `/api/v1/logs/` | Retrieve logs |
| GET | `/api/v1/logs/<event_id>/` | Retrieve an individual log |
| GET | `/api/v1/stats/` | Retrieve log statistics |
| GET | `/health/` | Check application and database health |

### Supported log filters

The log retrieval endpoint supports:

- `service_name`
- `level`
- `environment`
- `search`
- `start_time`
- `end_time`
- `page`
- `page_size`

Example:

```http
GET /api/v1/logs/?service_name=payment-service&level=ERROR&search=timeout
```

### Example ingestion request

```json
{
  "event_id": "evt-10021",
  "timestamp": "2026-11-05T20:30:12Z",
  "service_name": "payment-service",
  "service_version": "1.2.0",
  "environment": "development",
  "level": "ERROR",
  "event_type": "dependency_failure",
  "operation": "process_payment",
  "message": "Payment gateway timeout",
  "cloud": {
    "provider": "local"
  },
  "log_source": {
    "provider": "simulated"
  },
  "performance": {
    "duration_ms": 5032,
    "status_code": 504,
    "outcome": "failure"
  },
  "correlation": {
    "trace_id": "tr-8f21a9c43d",
    "request_id": "req-10021"
  },
  "attributes": {
    "payment_id": "pay-123"
  },
  "exception": {},
  "raw": {}
}
```

## Simulated Services

LogShift includes three lightweight Python scripts that generate sample telemetry events:

```bash
python simulated-services/payment_service.py
python simulated-services/auth_service.py
python simulated-services/order_service.py
```

These scripts send generated events to the local LogShift ingestion API.

## Automated Testing

Run the automated test suite inside the web container:

```bash
docker compose exec web python manage.py test logs
```

The current test suite covers:

- Successful single-event ingestion.
- Duplicate event rejection.
- Invalid log-level validation.
- Batch ingestion.
- Batch all-or-nothing behaviour.
- Service-based filtering.
- Individual log retrieval.
- Missing event handling.
- Statistics endpoint.
- Database health endpoint.

## Database Persistence

PostgreSQL data is stored in a named Docker volume:

```yaml
volumes:
  postgres_data:
```

This allows database records to survive container restarts and container recreation.

To restart the database:

```bash
docker compose restart db
```

To recreate the database container while retaining its data:

```bash
docker compose up -d --force-recreate db
```

**Warning:** `docker compose down -v` deletes named volumes and therefore removes the stored database data.

## Stopping the Application

```bash
docker compose down
```

This stops and removes the containers without deleting the PostgreSQL volume.

## Project Roadmap

- [x] Phase 1 — Local application and Docker Compose setup.
- [ ] Phase 2 — Manual AWS deployment.
- [ ] Phase 3 — CI/CD automation and Terraform infrastructure.
- [ ] Phase 4 — Migration to Google Cloud Platform.
- [ ] Phase 5 — Optional Kubernetes deployment.

## Learning Objectives

This project is intended to demonstrate practical experience with:

- Containerization and container lifecycle management.
- Application and database separation.
- Persistent storage and service health checks.
- REST API development and automated testing.
- Infrastructure provisioning.
- CI/CD pipeline automation.
- Cloud deployment and migration.

---

**LogShift — Centralized logs. Clearer operations.**