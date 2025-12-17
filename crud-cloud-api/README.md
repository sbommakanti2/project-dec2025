# Takehome Challenge CRUD API

FastAPI + SQLite CRUD service with JWT auth, SlowAPI rate limiting, Docker packaging, and Terraform IaC for AWS ECS Fargate. Everything lives under `crud-cloud-api/`.

---

## 1. Start Here
1. **Clone & open** `crud-cloud-api/`.
2. **Run locally** with Docker to validate behavior.
3. **Deploy to AWS** using the Terraform + ECR + ECS steps once you are confident locally.
4. **Use this README** as the single source of truth; every command you need is documented.

---

## 2. Architecture Overview
- **FastAPI Application (`app/`)**
  - `/health` (unauthenticated)
  - `/auth/login` → returns JWT for the demo user (`demo` / `password123`)
  - `/items` CRUD endpoints (bearer token required)
  - SQLite file DB via SQLAlchemy models with timestamps
  - SlowAPI limits: global 60 req/min per IP, login endpoint 5 req/min
- **Containerization**
  - Single Dockerfile targeting `linux/amd64` (required for ECS Fargate)
  - `docker-compose.yml` exposes port 8000 with a volume-backed SQLite file
- **Infrastructure (`terraform/`)**
  - Provider: AWS, default region `us-west-2`
  - Resources: ECR repo, ECS cluster + Fargate service (256 CPU / 512 MB), ALB + target group + listener, IAM roles, security groups wired to default VPC subnets
  - Terraform does **not** run Docker builds; it only provisions infra

---

## 3. Quick Start (Local Development)
### Requirements
- Docker Desktop (or Docker Engine)
- Optional: Python 3.11 if you want to run pytest outside Docker

### Run with Docker Compose
```bash
cd crud-cloud-api
docker compose up --build
```
Check that the app is live:
```bash
curl http://localhost:8000/health   # → {"status":"ok"}
```

### Run Tests (optional sanity)
```bash
pip install -r requirements.txt
pytest
```

### Local Auth + CRUD Examples
```bash
# 1) Login (POST is required, x-www-form-urlencoded)
curl -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=demo&password=password123" \
  http://localhost:8000/auth/login
export TOKEN="<paste access_token>"

# 2) Create
curl -X POST http://localhost:8000/items \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"notebook","description":"plain ruled"}'

# 3) List
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/items

# 4) Update
curl -X PUT http://localhost:8000/items/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"description":"updated text"}'

# 5) Delete
curl -X DELETE -H "Authorization: Bearer $TOKEN" http://localhost:8000/items/1
```

---

## 4. Requirement Mapping
- **Authentication (Requirement a)** – `/auth/login` issues a short-lived JWT (30 minutes). Every `/items` route injects `get_current_user`, so calls without `Authorization: Bearer <token>` return 401.
- **Rate Limiting (Requirement b)** – SlowAPI decorator + application-level limiter enforce:
  - Global: 60 requests/minute per client IP.
  - Login endpoint: 5 requests/minute per IP.
  - Responses over the limit return HTTP 429 with `Retry-After`.

---

## 5. AWS Deployment (ECR + Terraform + ECS Fargate)
These commands assume AWS CLI credentials are configured and you want the default `us-west-2` region. Adjust as needed.

### 5.1. Initialize Terraform & Create ECR
```bash
cd crud-cloud-api/terraform
terraform init
terraform apply -target=aws_ecr_repository.app -var "aws_region=us-west-2"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
IMAGE_REPO="$ACCOUNT_ID.dkr.ecr.us-west-2.amazonaws.com/takehome-challenge-crud-api"
```

### 5.2. Build & Push Docker Image (amd64)
```bash
cd ..
docker build -t "$IMAGE_REPO:latest" .
aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin "$IMAGE_REPO"
docker push "$IMAGE_REPO:latest"
```

### 5.3. Provision ECS + ALB
```bash
cd terraform
terraform apply \
  -var "aws_region=us-west-2" \
  -var "image_tag=latest"
```
Terraform prints:
- `alb_dns_name`
- `ecr_repository_url`
- `ecs_cluster_id`
- `ecs_service_name`

### 5.4. Verify in AWS
```bash
BASE_URL="http://<alb_dns_name>"
curl "$BASE_URL/health"                           # expect {"status":"ok"}
curl -X POST -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=demo&password=password123" \
  "$BASE_URL/auth/login"
export TOKEN="<copy token>"
curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/items"
```

> Tip: If the ALB ever returns 503, check `aws ecs describe-services ...` events and `aws logs tail /ecs/takehome-challenge-crud-api --region us-west-2` for clues. The most common fixes are “push the latest image” or “wait for health checks.”

---

## 6. Design Tradeoffs & Notes
- **SQLite on local volume** – quick to ship, but each ECS task has its own DB file. Good enough for a take-home; swap to RDS/DynamoDB for production.
- **Hard-coded demo user** – keeps focus on API behavior. A real auth system (hashing, user store, refresh tokens) would be a follow-up.
- **No migrations** – tables auto-create on startup; this avoids Alembic setup under a tight deadline.
- **Single container** – no background workers or migrations container. Terraform footprint stays small.
- **amd64 image pin** – Dockerfile explicitly targets `linux/amd64` to avoid `exec format error` on Fargate.

---

## 7. Known Limitations
1. HTTP-only ALB (no TLS). Add ACM + HTTPS listener if required.
2. Rate limiting is IP-based; users behind the same NAT share limits.
3. Single demo user; no password reset or refresh tokens.
4. SQLite means scaling the service horizontally will not share data.
5. No automated CI/CD. Builds/pushes are manual by design.

---

## 8. Troubleshooting Checklist
| Symptom | Likely Cause | Fix |
| ------- | ------------ | ---- |
| `docker compose up` fails pulling `python:3.11-slim` | Docker credential helper missing | Remove `credsStore` from `~/.docker/config.json` or reinstall Docker Desktop |
| `/auth/login` returns 405 | Sent GET request | Use POST with form-encoded body |
| ALB returns 503 | ECS task unhealthy / not running | `aws ecs describe-services ...`, tail CloudWatch logs, ensure new image is pushed |
| ECS `CannotPullContainerError` | `latest` tag missing in ECR | Rebuild + push `275755767571.dkr.ecr.us-west-2.amazonaws.com/takehome-challenge-crud-api:latest` |
| ECS `exec format error` | Built ARM image locally | Dockerfile now pins `--platform=linux/amd64`; rebuild & push |

---

## 9. Cleanup (Avoid Surprise Charges)
When you’re done with the review:
```bash
cd crud-cloud-api/terraform
terraform destroy -var "aws_region=us-west-2" -var "image_tag=latest"
aws ecr delete-repository --repository-name takehome-challenge-crud-api --force --region us-west-2
```
Then stop/remove local Docker containers/volumes if desired.

---

## 10. Final Thoughts
- The project intentionally stays small and readable: one service, one database file, minimal IAM footprint.
- Every command you need (local or AWS) is above. If you follow the sections in order, you’ll reproduce the entire deployment end-to-end.
- Reach out or open issues if you want follow-up improvements (HTTPS, persistent DB, CI/CD, etc.).
