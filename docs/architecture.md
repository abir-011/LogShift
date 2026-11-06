# LogShift — System Architecture

## 1. Overview

LogShift is a lightweight, containerized log aggregation platform designed to collect, store, search and monitor structured application logs from multiple services.

The application uses Django REST Framework for ingestion and retrieval, PostgreSQL for persistent storage, and a browser-based dashboard for log exploration.

The current implementation runs locally using Docker Compose.

## 2. High-Level Architecture

```text
+----------------------+     +----------------------+
|   payment-service   |     |     auth-service     |
|   Python Simulator  |     |   Python Simulator   |
+----------+-----------+     +----------+-----------+
           |                            |
           |          HTTP              |
           +-------------+--------------+
                         |
                         v
              +----------------------+
              |      LogShift        |
              |                      |
              | Django REST API      |
              | Log Validation       |
              | Query & Filtering    |
              | Statistics           |
              +----------+-----------+
                         |
                         v
              +----------------------+
              |     PostgreSQL       |
              |                      |
              | Structured Columns   |
              | JSON Fields          |
              | Persistent Volume    |
              +----------------------+
                         ^
                         |
              +----------+-----------+
              |                      |
              |   Dashboard          |
              |   Log Explorer       |
              |   Statistics         |
              +----------------------+

              +----------------------+
              |     order-service    |
              |   Python Simulator   |
              +----------------------+
                         |
                         +---- HTTP ----> LogShift API
```

## 3. Application Components

### 3.1 Simulated Services

The project currently includes three independent Python scripts:

- `payment_service.py`
- `auth_service.py`
- `order_service.py`

Each script generates structured application events containing information such as:

- Event ID and timestamp.
- Service name and version.
- Environment and severity level.
- Event type and message.
- Performance information.
- Correlation identifiers.
- Additional event attributes.
- Exception details when applicable.

The scripts send events to the LogShift ingestion API over HTTP.

These are simulated producers, not independently deployed microservices.

### 3.2 Django Application

The Django application is responsible for receiving, validating, storing and retrieving log events.

Its main components are:

| Component | Responsibility |
|---|---|
| `config` | Django project configuration and URL routing |
| `logs` | Log model, serializers, ingestion APIs and statistics |
| `dashboard` | Dashboard rendering and database health endpoint |

Django REST Framework handles the API layer.

### 3.3 PostgreSQL Database

PostgreSQL stores all ingested log events.

The database uses a hybrid storage model:

- Dedicated columns for frequently queried fields such as event ID, timestamp, service name, environment and severity.
- JSON fields for flexible nested metadata such as cloud information, performance, correlation, attributes and exceptions.

Indexes are defined for commonly filtered fields.

### 3.4 Dashboard

The dashboard provides a browser-based interface for exploring ingested logs.

It displays:

- Total log count.
- Error count.
- Warning count.
- Recent log events.
- Service and severity filters.
- Message search.

The dashboard retrieves its data from the LogShift REST API.

## 4. API Architecture

The application exposes the following endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/logs/` | Ingest one event |
| POST | `/api/v1/logs/batch/` | Ingest multiple events |
| GET | `/api/v1/logs/` | Retrieve and filter events |
| GET | `/api/v1/logs/<event_id>/` | Retrieve a specific event |
| GET | `/api/v1/stats/` | Retrieve aggregated statistics |
| GET | `/health/` | Check application and database health |

### Ingestion flow

1. A simulated service generates a structured event.
2. The service sends the event to the ingestion API.
3. Django REST Framework validates the incoming payload.
4. Valid events are stored in PostgreSQL.
5. The API returns an appropriate HTTP response.

### Batch ingestion

Batch ingestion accepts multiple events in a single request.

The current implementation validates the complete batch before saving it and uses a database transaction for insertion.

This provides all-or-nothing behaviour for the batch.

### Retrieval flow

1. The dashboard requests log records from the API.
2. Django applies the requested filters and search conditions.
3. PostgreSQL retrieves matching records.
4. Django returns paginated JSON responses.
5. The dashboard displays the results.

## 5. Container Architecture

Docker Compose manages two application containers.

| Container | Image | Responsibility |
|---|---|---|
| `logshift-web` | Custom Django image | API and dashboard |
| `logshift-db` | PostgreSQL 16 | Persistent log storage |

The web container runs Django through Gunicorn.

The database uses a named Docker volume called `postgres_data`.

### Container startup dependency

The web service depends on the database passing its PostgreSQL health check before starting.

This helps prevent the application from starting before the database is ready.

### Data persistence

PostgreSQL data is stored outside the database container in the named Docker volume.

Consequently, restarting or recreating the database container does not remove stored records as long as the volume is retained.

## 6. Health Monitoring

LogShift exposes:

```http
GET /health/
```

The health endpoint executes a simple SQL query against PostgreSQL.

A successful response indicates that the application can communicate with the database.

Example healthy response:

```json
{
  "status": "healthy",
  "database": "connected"
}
```

If the database connection fails, the endpoint returns HTTP 503.

## 7. Testing Strategy

The application includes automated tests using Django's test framework and Django REST Framework's API test client.

The current test suite covers:

- Single-event ingestion.
- Duplicate event rejection.
- Invalid log-level validation.
- Batch ingestion.
- Batch all-or-nothing behaviour.
- Service filtering.
- Individual event retrieval.
- Missing event handling.
- Statistics endpoint.
- Database health endpoint.

Tests run against a temporary test database, keeping the normal development database separate.

## 8. Current Deployment Model

The current architecture is local-first.

```text
Windows Host
    |
    +-- Docker Desktop
          |
          +-- logshift-web
          |      |
          |      +-- Django
          |      +-- Gunicorn
          |
          +-- logshift-db
                 |
                 +-- PostgreSQL 16
                 +-- postgres_data volume
```

The simulated producer scripts run directly on the Windows host and communicate with the Django container through the published HTTP port.

## 9. Planned Infrastructure Evolution

The project is being developed in phases.

| Phase | Planned architecture |
|---|---|
| Phase 1 | Local Docker Compose deployment |
| Phase 2 | Manual AWS deployment using EC2 and ECR |
| Phase 3 | Terraform infrastructure and GitHub Actions CI/CD |
| Phase 4 | Migration to Google Cloud Platform |
| Phase 5 | Optional Kubernetes deployment |

These are planned changes, not components of the current local deployment.

---

**Document status:** Phase 1 — Local architecture implemented.