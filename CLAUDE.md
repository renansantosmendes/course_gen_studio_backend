# CLAUDE.md

## About this project

Back end of **CourseGen Studio** (SynapseAI Solutions), a tool for
generating and reviewing course material with AI. The front end (static
HTML pages) and the database schema live in the sibling repository
`../course_gen_studio_front`.

FastAPI application (package `src/coursegen_backend`) deployed on
Vercel through `api/index.py` and `vercel.json`. It currently covers
sign-in, sessions and password management.

## About the architecture

- Clean Architecture with SOLID; dependencies point inwards only:
  `domain` (entities, errors, rules; no I/O) <- `application` (use
  cases, ports, policies, DTOs) <- `infrastructure` (PostgreSQL,
  Argon2, JWT, SMTP, settings) and `presentation/api` (FastAPI).
- Use cases depend on ports from `application/ports`, never on
  adapters. Wire implementations only in
  `presentation/api/dependencies.py`.
- Business errors are `DomainError` subclasses with a stable `code`;
  map them to HTTP statuses in `presentation/api/error_handlers.py`.
- Document every route for Swagger in English: `summary`,
  `description`, `response_description`, every error status in
  `responses`, and `Field(description=..., examples=...)` in schemas.

## About dependencies and commands

- `requirements.txt` holds only runtime packages (Vercel installs it);
  development tools go in `requirements-dev.txt`.
- Set up: `uv venv` and `uv pip install -r requirements-dev.txt`.
- Run locally: `uv run --no-project uvicorn api.index:app --reload`.
- Tests: `uv run --no-project pytest -q`.
- Lint: `uv run --no-project pylint --rcfile=.pylintrc src api` and
  `uv run --no-project pylint --rcfile=tests/.pylintrc tests`. Both
  must score 10/10, as enforced by `.github/workflows/ci.yml`.
- Tests use the in-memory fakes in `tests/fakes.py`; do not require a
  database in unit tests.

## About the database

- The back end uses the Neon PostgreSQL database, schema `coursegen`.
  The source of truth for the schema is
  `../course_gen_studio_front/db/schema.sql`, applied by
  `../course_gen_studio_front/db/apply_schema.py`. Do not create tables
  from application code; change the schema there.
- At runtime, connect only with `COURSEGEN_DATABASE_URL` (role
  `coursegen_app`). This role can read and write data in `coursegen`
  but cannot create or alter tables, cannot write to `bloom_levels`
  and can only insert into `audit_log`. Never use the owner URL
  (`NEON_DATABASE_URL`) in the application.
- The database is shared with other projects (`public`, `pgl_auth`,
  `pgl_proxy`, `agent_conversations`); never read or write outside
  `coursegen`.
- Every organization is an isolated tenant: every query on tenant data
  must be filtered by `organization_id`.
- Exports are only allowed for approved course versions (enforced by
  the `exports_require_approved` trigger); surface that error to the
  user instead of working around it.

## About AI features

- LLM calls use the OpenAI API (`OPENAI_API_KEY`) and must be traced
  with Langfuse (`LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`,
  `LANGFUSE_BASE_URL`).
- Record each generation in the `ai_generations` table.
- Retrieval (RAG) uses the `source_chunks` table with `pgvector`
  embeddings, always scoped to the requesting organization.

## About secrets

- Secrets are read from a local `.env` file, which is git-ignored.
  Never hardcode keys, passwords or connection strings in code, tests
  or logs.

## About Python code

Always follow these guidelines when writing or editing Python code in
this project:

- Always use `uv` as the package manager whenever a package needs to be
  installed.
- Write all docstrings in English.
- Docstrings must be complete: describe the input parameters
  (`Parameters`) and the return value (`Returns`).
- When a function or method is complex, include a usage example in the
  docstring (`Example` section).
- Respect the per-line character limit in docstrings according to
  PEP 8 / PEP 257 (79 characters).
- Variables, functions, classes and methods must have descriptive,
  meaningful names written in English.
- Use type hints on function and method parameters and return values.
- Do not use type hints on simple variable assignments inside the body
  of the code.
- Do not add comments in the code — keep only the docstrings.
- Whenever a function or method has 2 or more parameters, break the
  signature across multiple lines, one parameter per line, for example:

```python
def func1(
    param_1: type_1,
    param_2: type_2,
    ...
    param_n: type_n,
) -> type_of_return:
```

- Whenever production code is created or changed, add (or update) the
  corresponding unit tests under `tests/`, mirroring the structure of
  `src/`.
- Always check whether the existing documentation (README, docstrings,
  files under `docs/`, if any) is still consistent with the change; if
  it needs an update, update it right away.
