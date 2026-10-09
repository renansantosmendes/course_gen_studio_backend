# CourseGen Studio API

Authentication and password management API of CourseGen Studio, built
with FastAPI and deployed on Vercel. It uses the `coursegen` schema of the
Neon PostgreSQL database defined in
`../course_gen_studio_front/db/schema.sql`.

Interactive documentation, once the API is running:

- Swagger UI: `/docs`
- ReDoc: `/redoc`
- OpenAPI document: `/openapi.json`

## Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/v1/health` | - | Liveness check |
| POST | `/api/v1/auth/login` | - | Sign in, returns access and refresh tokens |
| POST | `/api/v1/auth/refresh` | - | Rotate the refresh token, new access token |
| POST | `/api/v1/auth/logout` | Bearer | End the current session |
| GET | `/api/v1/auth/me` | Bearer | Profile, organizations and roles |
| POST | `/api/v1/auth/password/forgot` | - | E-mail a single-use reset link (neutral answer) |
| POST | `/api/v1/auth/password/reset` | - | Define a new password with the reset token |
| POST | `/api/v1/auth/password/change` | Bearer | Change the password, ending the other sessions |

Security measures:

- Passwords hashed with Argon2id, rehashed when parameters change.
- Short-lived JWT access tokens (HS256) checked against the stored session,
  so sign-out and password changes take effect at once.
- Opaque refresh and reset tokens stored only as SHA-256 hashes; refresh
  tokens rotate on every use.
- Per-account lockout after repeated failed sign-ins, counted from the
  audit trail.
- Responses never reveal whether an e-mail is registered.
- Every sign-in, sign-out and password event is written to
  `coursegen.audit_log`.

## Architecture

The code follows Clean Architecture; dependencies point inwards only.

```
src/coursegen_backend/
├── domain/           Entities, business errors, password policy (no I/O)
├── application/      Use cases, ports (interfaces), policies, DTOs
├── infrastructure/   Adapters: PostgreSQL, Argon2, JWT, SMTP, settings
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

With `EMAIL_BACKEND=console`, the password reset e-mail (including the
link) is printed to the log instead of being sent.

Users are not created by this API. Insert them in `coursegen.users`
(the `password_hash` must be an Argon2 hash) or let them define a password
through the recovery flow.

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
   settings. Required: `COURSEGEN_DATABASE_URL` (Neon pooled host),
   `COURSEGEN_JWT_SECRET_KEY`, `PASSWORD_RESET_URL`,
   `CORS_ALLOWED_ORIGINS`, `EMAIL_BACKEND=smtp` and the `SMTP_*` values.
3. Deploy. `vercel.json` routes every path to `api/index.py`, and
   Vercel installs `requirements.txt`.
