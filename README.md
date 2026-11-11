# LogShift

**A lightweight, containerized log aggregation and monitoring platform built with Django and PostgreSQL.**

LogShift collects structured logs from multiple simulated services, stores them centrally, and provides APIs and a dashboard to search, filter, and monitor application events.

The project demonstrates practical DevOps concepts, including Docker containerization, persistent storage, health checks, automated testing, container registries, cloud infrastructure, and application deployment.

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
- AWS EC2 deployment using Docker containers.
- Private Docker image storage using Amazon ECR.
- Persistent PostgreSQL storage using Docker named volumes backed by EBS.

## Architecture

### Local deployment

```text
 payment-service ──┐
 auth-service ─────┼──> Django REST API ───> PostgreSQL
 order-service ────┘           │
                               │
                         Dashboard
                               │
                         Log Explorer
```

### AWS deployment

```text
              Developer Machine
                     |
                Docker Build
                     |
                     v
              Amazon ECR
             (Private Registry)
                     |
                Docker Pull
                     |
                     v
              AWS EC2 Instance
               (Ubuntu 24.04)
                     |
              Docker Compose
                /        \
               /          \
              v            v
        Django +         PostgreSQL
        Gunicorn         Container
              |            |
              |            v
              |       Docker Named
              |          Volume
              |            |
              |            v
              |         AWS EBS
              |
              v
         REST API
              |
              v
          Dashboard
```

The application and database run as separate containers on a single EC2 instance. PostgreSQL uses a Docker named volume backed by the instance's EBS storage, allowing database records to survive container recreation and EC2 stop/start operations.

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
| Cloud provider | AWS |
| Container registry | Amazon ECR |
| Compute | Amazon EC2 |
| Storage | Amazon EBS (gp3) |
| Operating system | Ubuntu Server 24.04 LTS |
| Instance access | SSH |
| Cloud authentication | AWS IAM roles |

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
├── docker-compose.prod.yml
├── .dockerignore
├── .gitignore
├── .env.example
└── README.md
```

## Getting Started — Local Deployment

### Prerequisites

- Docker Desktop
- Git
- Python 3.11 or later (for running simulated services locally)

### 1. Clone the repository

```bash
git clone https://github.com/abir-011/LogShift.git
cd LogShift
```

### 2. Configure environment variables

Create a `.env` file in the project root using `.env.example` as a reference.

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

## AWS Deployment — Phase 2

LogShift was manually deployed to AWS using Amazon EC2 and Amazon ECR.

### Infrastructure configuration

| Component | Configuration |
|---|---|
| AWS Region | Asia Pacific (Sydney) — `ap-southeast-2` |
| EC2 instance | `t3.small` |
| Operating system | Ubuntu Server 24.04 LTS |
| Architecture | x86_64 |
| EBS storage | 12 GiB gp3 |
| Container registry | Amazon ECR |
| Application server | Gunicorn |
| Database | PostgreSQL 16 |
| Deployment | Docker Compose |

### 1. Container image publishing

The application image is built locally and pushed to a private Amazon ECR repository.

ECR repository:

```text
522979904445.dkr.ecr.ap-southeast-2.amazonaws.com/logshift
```

Authenticate Docker with ECR:

```bash
aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin 522979904445.dkr.ecr.ap-southeast-2.amazonaws.com
```

Build the application image:

```bash
docker compose build web
```

Tag the image:

```bash
docker tag logshift-web:latest 522979904445.dkr.ecr.ap-southeast-2.amazonaws.com/logshift:latest
```

Push the image:

```bash
docker push 522979904445.dkr.ecr.ap-southeast-2.amazonaws.com/logshift:latest
```

### 2. EC2 configuration

The EC2 instance runs Docker Engine, Docker Compose, and AWS CLI.

An IAM instance role named `LogShiftEC2ECRRole` provides read-only access to the private ECR repository.

This allows EC2 to authenticate with ECR using temporary IAM credentials instead of storing long-lived AWS access keys on the server.

### 3. Pull the application image on EC2

Authenticate Docker on the EC2 instance:

```bash
aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin 522979904445.dkr.ecr.ap-southeast-2.amazonaws.com
```

Pull the image:

```bash
docker pull 522979904445.dkr.ecr.ap-southeast-2.amazonaws.com/logshift:latest
```

### 4. Production environment configuration

The production deployment uses a separate `.env` file on the EC2 instance.

Important settings:

```env
SECRET_KEY=your-production-secret
DEBUG=False
ALLOWED_HOSTS=YOUR_EC2_PUBLIC_IP,localhost,127.0.0.1

DB_NAME=logshift
DB_USER=logshift_user
DB_PASSWORD=your-strong-production-password
DB_HOST=db
DB_PORT=5432
```

Production secrets are generated separately from local development credentials and are never committed to GitHub.

Restrict access to the environment file:

```bash
chmod 600 ~/LogShift/.env
```

### 5. Start the production deployment

From the deployment directory:

```bash
docker compose -f docker-compose.prod.yml up -d
```

Apply database migrations:

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
```

Check container status:

```bash
docker compose -f docker-compose.prod.yml ps
```

Check application health:

```bash
curl http://localhost:8000/health/
```

### 6. Production access

The dashboard and APIs are accessible through the EC2 public IPv4 address.

```text
http://YOUR_EC2_PUBLIC_IP:8000/
```

The Security Group restricts SSH (22) and application access (8000) to the developer's public IP. PostgreSQL (5432) is not exposed publicly.

The current learning deployment uses HTTP rather than HTTPS and should not be used to transmit sensitive information.

### 7. EC2 lifecycle management

Stop the application containers without deleting persistent data:

```bash
docker compose -f docker-compose.prod.yml down
```

Start them again:

```bash
docker compose -f docker-compose.prod.yml up -d
```

Stopping the EC2 instance preserves its EBS-backed database volume. However, its automatically assigned public IPv4 address can change after a stop/start operation.

If the public IP changes:

1. Update `ALLOWED_HOSTS` in the production `.env` file.
2. Recreate the web container to load the updated environment:

```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate web
```

3. Check whether the Security Group's SSH and application inbound rules still match your current public IP.

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

In the AWS deployment, this volume is backed by the EC2 instance's EBS storage.

Persistence was verified by:

- Recreating Docker containers without deleting the named volume.
- Stopping and starting the EC2 instance.
- Confirming that previously ingested production log events remained available.

To restart the database:

```bash
docker compose restart db
```

To recreate the database container while retaining its data:

```bash
docker compose up -d --force-recreate db
```

**Warning:** `docker compose down -v` deletes named volumes and therefore removes the stored database data.

## Security and Cost Considerations

- Production uses `DEBUG=False`.
- Production secrets are kept outside version control.
- EC2 uses an IAM instance role for ECR image pulls.
- PostgreSQL is not publicly exposed.
- SSH and application inbound access are restricted by Security Group rules.
- The deployment avoids managed load balancers, NAT Gateways, RDS, and Kubernetes.
- A monthly AWS budget with notifications is configured.
- EC2 compute charges can be reduced by stopping the instance when it is not in use.
- EBS storage charges continue while the EC2 instance is stopped.
- AWS promotional credits and Free Plan eligibility are subject to account terms and expiry.

## Project Roadmap

- [x] Phase 1 — Local application and Docker Compose setup.
- [x] Phase 2 — Manual AWS deployment using EC2 and ECR.
- [ ] Phase 3 — CI/CD automation and Terraform infrastructure.
- [ ] Phase 4 — Migration to Google Cloud Platform.
- [ ] Phase 5 — Optional Kubernetes deployment.

## Learning Objectives

This project demonstrates practical experience with:

- Containerization and container lifecycle management.
- Application and database separation.
- Persistent storage and service health checks.
- REST API development and automated testing.
- Container image building and publishing.
- Amazon ECR and EC2 integration.
- IAM roles and cloud authentication.
- Manual cloud infrastructure provisioning.
- Application deployment and operational troubleshooting.
- Infrastructure cost and security considerations.

---

**LogShift — Centralized logs. Clearer operations.**


## CI/CD Pipeline

LogShift uses GitHub Actions to automate testing and Docker image publishing, followed by automatic deployment on AWS EC2.

### Pipeline Architecture

```text
Developer pushes code to GitHub (main)
                |
                v
        GitHub Actions
                |
                v
       Run Django Tests
                |
          Tests Pass?
                |
                v
        Build Docker Image
                |
                v
       Push Image to Amazon ECR
         |              |
      SHA Tag        latest Tag
                |
                v
          AWS EC2 Instance
                |
                v
       Cron-based Image Polling
          (Every 5 Minutes)
                |
                v
       Compare Running Image
          with Latest SHA
                |
                v
       Pull and Deploy New Image
                |
                v
         Health Check
          /       \
       Pass       Fail
        |           |
     Success      Rollback
```

### Technologies Used

- **GitHub Actions:** Runs automated tests and builds Docker images.
- **Amazon ECR:** Stores versioned Docker images using Git commit SHA tags and a `latest` tag.
- **Amazon EC2:** Hosts the containerized LogShift application and PostgreSQL database.
- **Docker Compose:** Manages application and database containers.
- **Bash:** Automates image detection, deployment, health checks, and rollback.
- **Cron:** Checks ECR every five minutes for newly published images.

### Deployment Strategy

The pipeline uses a pull-based deployment strategy.

1. A push to `main` triggers GitHub Actions.
2. Django tests run against a PostgreSQL service.
3. On successful tests, a Docker image is built and pushed to ECR.
4. EC2 periodically checks ECR for the latest published image.
5. If a new commit SHA is detected, EC2 pulls and deploys it.
6. The deployment script verifies application health and attempts to restore the previous image if deployment fails.

### Design Considerations

- Pull-based deployment avoids exposing SSH access to external GitHub-hosted runners.
- Deployment locking prevents overlapping deployment executions.
- PostgreSQL is not recreated during application deployments, preserving database persistence.
- SHA-based image tags provide traceability and make rollback possible.
- Cron polling is a pragmatic alternative to event-driven deployment in the current AWS account environment.
