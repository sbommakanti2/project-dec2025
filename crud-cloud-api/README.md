# Takehome Challenge CRUD API

This repo is exactly how I’d hand a take-home project back to a teammate. It focuses on a clear CRUD API, leans on the required stack (FastAPI, SQLite, JWT, SlowAPI, Docker, Terraform on ECS Fargate), and puts all the “how do I run this?” details in one place for reviewers.

---

## How I Navigate the Project
1. Everything lives inside `crud-cloud-api/`; there are no hidden folders or scripts elsewhere.
2. I always run it locally with Docker first so I can demo the API without depending on AWS.
3. Once it works locally, I tag the Docker image, push it to ECR, and let Terraform create the ECS + ALB stack.
4. This README is literally the checklist I follow when repeating the flow.

---

## What’s Inside
- **FastAPI app (`app/`)** – Implements `/health`, `/auth/login`, and the protected `/items` CRUD operations. Here’s what a single Item looks like when you hit GET `/items/1`:
  ```json
  {
    "id": 1,
    "name": "notebook",
    "description": "plain ruled",
    "created_at": "2025-12-16T20:17:00Z",
    "updated_at": "2025-12-16T20:19:12Z"
  }
  ```
  SQLite + SQLAlchemy handle persistence, and SlowAPI enforces 60 req/min globally plus 5 req/min on the login endpoint.
- **Container bits** – A single Dockerfile (locked to `linux/amd64` so ECS Fargate doesn’t complain) and a `docker-compose.yml` that mounts the SQLite file into a named volume. That means you can restart `docker compose` without losing test data.
- **Terraform (`terraform/`)** – Creates the AWS scaffolding: ECR repo, ECS cluster/service (256 CPU / 512 MB), IAM roles, security groups in the default VPC, and an ALB that points to `/health`. Terraform purposely stops short of building or pushing Docker images so you can keep that step explicit.

---

## Local Runbook
Requirements: Docker Desktop (or Engine). Python 3.11 only matters if you want to run pytest outside Docker.

1. Start the API (Docker will grab base layers the first time, so give it a minute):
   ```bash
   cd crud-cloud-api
   docker compose up --build
   ```
   Sanity check:
   ```bash
   curl http://localhost:8000/health
   # {"status":"ok"}
   ```

2. Optional tests:
   ```bash
   pip install -r requirements.txt
   pytest
   ```

3. Manual API flow (exactly what I demo on calls):
   ```bash
   # login (POST + form body is important)
   curl -X POST -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=demo&password=password123" \
     http://localhost:8000/auth/login
   export TOKEN="<paste access_token>"

   # create/read/update/delete
   curl -X POST http://localhost:8000/items \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"name":"notebook","description":"plain ruled"}'
   curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/items
   curl -X PUT http://localhost:8000/items/1 \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"description":"updated text"}'
   curl -X DELETE -H "Authorization: Bearer $TOKEN" http://localhost:8000/items/1
   ```

---

## How the Requirements Are Covered
- **Auth** – `/auth/login` issues a 30-minute JWT and every `/items` route injects `get_current_user`. Missing or bad tokens get a 401 response that looks like
  ```json
  {
    "detail": "Could not validate credentials"
  }
  ```
  with the `WWW-Authenticate: Bearer` header so clients know to re-auth.
- **Rate limiting** – SlowAPI wraps the FastAPI app. Global limit = 60 req/min per IP, login route = 5 req/min. Overflow returns 429 with `{"detail":"Rate limit exceeded..."}` and a `Retry-After` header so you know how long to wait.

---

## Deploying to AWS (us-west-2 by default)
These are the exact commands I run once AWS credentials are configured.

1. **Prep Terraform and create the ECR repo** (run once per environment)
   ```bash
   cd crud-cloud-api/terraform
   terraform init
   terraform apply -target=aws_ecr_repository.app -var "aws_region=us-west-2"
   ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
   IMAGE_REPO="$ACCOUNT_ID.dkr.ecr.us-west-2.amazonaws.com/takehome-challenge-crud-api"
   ```

2. **Build + push the image** (Dockerfile already pins to amd64)
   ```bash
   cd ..
   docker build -t "$IMAGE_REPO:latest" .
   aws ecr get-login-password --region us-west-2 | \
     docker login --username AWS --password-stdin "$IMAGE_REPO"
   docker push "$IMAGE_REPO:latest"
   ```

3. **Provision ECS, ALB, etc.** (takes ~10 min the first time)
   ```bash
   cd terraform
   terraform apply \
     -var "aws_region=us-west-2" \
     -var "image_tag=latest"
   ```

4. **Smoke test through the ALB**
   Terraform prints `alb_dns_name`. Use it just like localhost—only the hostname changes:
   ```bash
   BASE_URL="http://takehome-challenge-crud-api-alb-XXXX.us-west-2.elb.amazonaws.com"
   curl "$BASE_URL/health"
   curl -X POST ... "$BASE_URL/auth/login"
   curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/items"
   ```

If the ALB ever returns 503, run `aws ecs describe-services ...` and `aws logs tail /ecs/takehome-challenge-crud-api --region us-west-2` to see whether the new task is still booting or failing health checks. Most issues boil down to “forgot to push the Docker image” or “health checks haven’t turned green yet.”

---

## Design Notes
- SQLite keeps the demo self-contained. Each ECS task has its own DB file; for real workloads I’d jump to RDS or DynamoDB.
- Hard-coded demo user keeps auth simple under time pressure.
- Tables are created on startup so I didn’t have to introduce Alembic just for one model.
- Targeting `linux/amd64` in the Dockerfile avoids Fargate’s “exec format error”.
- Terraform footprint is intentionally small: one cluster, one service, one ALB listener.

---

## Things Still on the Wishlist
1. Add TLS (ACM cert + 443 listener) so the ALB speaks HTTPS.
2. Move data to a shared store so multiple tasks can run at once.
3. Replace the fake user with a real `users` table + hashed passwords.
4. Wire in a lightweight CI workflow to run pytest + docker build automatically.

---

## Troubleshooting Cheatsheet
| Symptom | What usually fixes it |
| ------- | --------------------- |
| `docker compose up` can’t pull `python:3.11-slim` | Remove the `credsStore` entry in `~/.docker/config.json` or reinstall Docker Desktop. |
| `/auth/login` says “Method Not Allowed” | That endpoint only accepts POST with form data. |
| ECS `CannotPullContainerError` | Push the tag you referenced in Terraform (defaults to `latest`). |
| ECS `exec format error` | Rebuild/push after the Dockerfile change (`--platform=linux/amd64`). |
| ALB returns 503 | New task isn’t healthy yet—check ECS events and CloudWatch logs. |

---

## When You’re Done
Here’s how I tear everything down once a reviewer is finished:
```bash
cd crud-cloud-api/terraform
terraform destroy -var "aws_region=us-west-2" -var "image_tag=latest"
aws ecr delete-repository --repository-name takehome-challenge-crud-api --force --region us-west-2
```
Locally, `docker compose down -v` will remove the container and the persisted SQLite volume.

---

## Final Notes
This codebase is intentionally small: one API process, one SQLite file, one ECS service. The README mirrors how I actually work—validate locally, push a tagged image, apply Terraform. If you want to extend it (TLS, persistent database, CI/CD), I’m happy to walk through next steps. Otherwise, clone it, run the commands, and you’ll reproduce the entire deployment end-to-end.
