# Takehome Challenge CRUD API

I built this repo to show how I would approach a small but production-minded CRUD service. It sticks to the required stack—FastAPI, SQLite, JWT auth, SlowAPI rate limiting, Docker, and Terraform to land on ECS Fargate—while keeping the layout friendly for reviewers.

---

## How I Navigate the Project
1. Everything lives inside `crud-cloud-api/`.
2. I run it locally with Docker first, just to prove out the API.
3. Once I’m happy, I push an image to ECR and let Terraform spin up ECS + an ALB.
4. This README is the playbook for both steps.

---

## What’s Inside
- **FastAPI app (`app/`)** – `/health`, `/auth/login`, and the protected `/items` CRUD operations. SQLite + SQLAlchemy for storage. SlowAPI enforces 60 req/min globally and 5 req/min on login.
- **Container bits** – Dockerfile (pinned to `linux/amd64` for Fargate) and a `docker-compose.yml` that mounts the SQLite file into a named volume.
- **Terraform (`terraform/`)** – Creates an ECR repo, ECS cluster/service (256 CPU / 512 MB), IAM roles, security groups in the default VPC, and an ALB pointed at `/health`. Terraform deliberately doesn’t build/push images—those stay manual.

---

## Local Runbook
Requirements: Docker Desktop (or Engine). Python 3.11 only if you want to run pytest.

1. Start the API:
   ```bash
   cd crud-cloud-api
   docker compose up --build
   ```
   Sanity check: `curl http://localhost:8000/health`

2. Optional tests:
   ```bash
   pip install -r requirements.txt
   pytest
   ```

3. Manual API flow:
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
- **Auth** – `/auth/login` issues a 30-minute JWT and every `/items` route injects `get_current_user`. Missing or bad tokens get a 401.
- **Rate limiting** – SlowAPI wraps the FastAPI app. Global limit = 60 req/min per IP, login route = 5 req/min. Overflow returns 429 with `Retry-After`.

---

## Deploying to AWS (us-west-2 by default)
Assumes you already have AWS credentials configured.

1. **Prep Terraform and create the ECR repo**
   ```bash
   cd crud-cloud-api/terraform
   terraform init
   terraform apply -target=aws_ecr_repository.app -var "aws_region=us-west-2"
   ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
   IMAGE_REPO="$ACCOUNT_ID.dkr.ecr.us-west-2.amazonaws.com/takehome-challenge-crud-api"
   ```

2. **Build + push the image (note the amd64 pin in Dockerfile)**
   ```bash
   cd ..
   docker build -t "$IMAGE_REPO:latest" .
   aws ecr get-login-password --region us-west-2 | \
     docker login --username AWS --password-stdin "$IMAGE_REPO"
   docker push "$IMAGE_REPO:latest"
   ```

3. **Provision ECS, ALB, etc.**
   ```bash
   cd terraform
   terraform apply \
     -var "aws_region=us-west-2" \
     -var "image_tag=latest"
   ```

4. **Smoke test through the ALB**
   Terraform prints `alb_dns_name`. Use it exactly like localhost:
   ```bash
   BASE_URL="http://takehome-challenge-crud-api-alb-XXXX.us-west-2.elb.amazonaws.com"
   curl "$BASE_URL/health"
   curl -X POST ... "$BASE_URL/auth/login"
   curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/items"
   ```

If the ALB ever returns 503, run `aws ecs describe-services ...` and `aws logs tail /ecs/takehome-challenge-crud-api --region us-west-2` to see whether the new task is still booting or failing health checks.

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
Tear down the AWS resources and clean up the registry so the Free Tier bill doesn’t creep up:
```bash
cd crud-cloud-api/terraform
terraform destroy -var "aws_region=us-west-2" -var "image_tag=latest"
aws ecr delete-repository --repository-name takehome-challenge-crud-api --force --region us-west-2
```
Locally, `docker compose down -v` will remove the container and the persisted SQLite volume.

---

## Final Notes
This codebase is intentionally small: one API process, one SQLite file, one ECS service. The README mirrors how I actually work—validate locally, push a tagged image, apply Terraform. If you want to extend it (TLS, persistent database, CI/CD), I’m happy to walk through next steps. Otherwise, clone it, run the commands, and you’ll reproduce the entire deployment end-to-end.
