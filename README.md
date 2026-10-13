# CourseGen Studio API

Back end of CourseGen Studio, built with FastAPI and deployed on Vercel.
It uses the `coursegen` schema of the Neon PostgreSQL database defined in
`../course_gen_studio_front/db/schema.sql`.

Interactive documentation, once the API is running:

- Swagger UI: `/docs`
- ReDoc: `/redoc`
- OpenAPI document: `/openapi.json`

## Authentication

Sign-in, sessions and passwords are handled by the shared **auth
service** (`../auth_service`). CourseGen never stores passwords or issues
tokens:

1. The front end signs in at the auth service (`POST /api/v1/auth/login`)
   and renews the session there (`POST /api/v1/auth/refresh`).
2. It calls this API with `Authorization: Bearer <access_token>`.
3. This API verifies the token with the auth service's public keys
   (`AUTH_JWKS_URL`, RS256), checking issuer and audience.
4. The first request of an account creates its CourseGen profile in
   `coursegen.users`, using the token's `sub` as the id; later requests
   keep e-mail and name in sync. Job title, the `is_active` flag and the
   organization memberships belong to CourseGen.

Access tokens are verified locally, so a sign-out in the auth service
takes effect here when the token expires (15 minutes by default).

## Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/v1/health` | - | Liveness check |
| GET | `/api/v1/me` | Bearer | CourseGen profile, organizations and roles |

## Architecture

The code follows Clean Architecture; dependencies point inwards only.

```
src/coursegen_backend/
├── domain/           Entities and business errors (no I/O)
├── application/      Use cases, ports (interfaces), DTOs
├── infrastructure/   Adapters: PostgreSQL, JWKS token verifier, settings
└── presentation/api  FastAPI app, routers, schemas, error handlers,
                      dependency wiring (composition root)
api/index.py          Vercel entry point
```

- Use cases depend on ports (`application/ports`), never on concrete
  adapters (dependency inversion).
- Each use case has one reason to change (single responsibility).
- `presentation/api/dependencies.py` is the only place that knows which
  adapter implements each port; tests replace them through
  `app.dependency_overrides`.

## Local development

```bash
uv venv
uv pip install -r requirements-dev.txt
cp .env.example .env        # then fill in the values
uv run --no-project uvicorn api.index:app --reload
```

`AUTH_JWKS_URL` must point at a running auth service (locally, for
example, `http://localhost:8001/.well-known/jwks.json`).

## Quality checks

```bash
uv run --no-project pytest -q
uv run --no-project pylint --rcfile=.pylintrc src api
uv run --no-project pylint --rcfile=tests/.pylintrc tests
```

The same checks run on GitHub Actions (`.github/workflows/ci.yml`) for
every push to `main` and every pull request.

## Deploy on Vercel

1. Import the repository in Vercel (framework preset: *Other*).
2. Set the environment variables from `.env.example` in the project
   settings. Required: `COURSEGEN_DATABASE_URL` (Neon pooled host) and
   `AUTH_JWKS_URL`; `AUTH_JWT_ISSUER` / `AUTH_JWT_AUDIENCE` must match the
   auth service, and `CORS_ALLOWED_ORIGINS` the front end.
3. Deploy. `vercel.json` routes every path to `api/index.py`, and
   Vercel installs `requirements.txt`.
