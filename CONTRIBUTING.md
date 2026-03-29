# Contributing to ShellGuard

Thank you for your interest in contributing to ShellGuard. This guide covers setting up a development environment, running tests, and the pull request process.

## Prerequisites

- **Node.js 20** (LTS) -- for the frontend
- **Python 3.12** -- for the backend
- **PostgreSQL 16** -- for local development (or use Docker Compose)
- **Git**

## Repository Structure

```
shellguard/
├── src/                  # React frontend (TypeScript)
├── backend/              # FastAPI backend (Python)
│   ├── app/
│   │   ├── routes/       # API route handlers
│   │   ├── services/     # Business logic
│   │   ├── models.py     # SQLAlchemy models
│   │   ├── schemas.py    # Pydantic schemas
│   │   ├── config.py     # Environment configuration
│   │   └── main.py       # FastAPI application entry point
│   └── tests/            # Backend tests
├── supabase/migrations/  # Database migration files
├── deploy/k3s/           # Kubernetes manifests
├── docs/                 # Documentation
├── docker-compose.yml    # Docker Compose for local dev/deployment
└── CLAUDE.md             # Project conventions for AI assistants
```

## Development Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd shellguard
```

### 2. Start the Database

The easiest way to get a local PostgreSQL instance:

```bash
docker compose up -d shellguard-db
```

This starts PostgreSQL 16 on port 5432 with user `shellguard` and database `shellguard`.

### 3. Set Up the Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # On Windows: .venv\Scripts\activate
pip install -e ".[test]"
```

Create a `.env` file in the project root (or `backend/` directory):

```bash
DATABASE_URL=postgresql://shellguard:shellguard@localhost:5432/shellguard
ADMIN_API_KEY=dev-api-key
LOG_LEVEL=debug
```

Run the backend:

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

The API is now available at `http://localhost:8080`. Swagger docs are at `http://localhost:8080/docs`.

### 4. Set Up the Frontend

```bash
# From the project root
npm install
```

Create a `.env` file in the project root with Supabase credentials (for the admin UI auth):

```bash
VITE_SUPABASE_URL=your-supabase-url
VITE_SUPABASE_ANON_KEY=your-supabase-anon-key
```

Run the frontend dev server:

```bash
npm run dev
```

The frontend dev server runs on `http://localhost:5173` and proxies API requests to the backend.

## Running Tests

### Backend Tests

```bash
cd backend
python -m pytest -v
```

### Frontend Lint

```bash
npm run lint
```

### Frontend Type Check

```bash
npm run typecheck
```

### Run All Checks

Before submitting a PR, run all validation:

```bash
# Frontend
npm run lint
npm run typecheck

# Backend
cd backend && python -m pytest -v
```

## Code Conventions

### TypeScript (Frontend)

- Strict mode is enabled with `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`.
- All domain types live in `src/types/index.ts`.
- Use Tailwind CSS utility classes for styling. No CSS modules or styled-components.
- Use the `cn()` helper from `src/lib/utils.ts` for conditional class merging.
- Pages (`src/pages/`) own data fetching and state. UI components (`src/components/ui/`) are stateless primitives.

### Python (Backend)

- FastAPI with async SQLAlchemy.
- Pydantic for request/response schemas.
- All configuration via environment variables through the `Settings` class in `app/config.py`.
- Routes are organized by domain in `app/routes/`.
- Business logic lives in `app/services/`.

## Pull Request Process

1. **Create a branch** from `main` with a descriptive name:
   ```bash
   git checkout -b feature/add-gpu-policy-support
   ```

2. **Make your changes** following the code conventions above. When your changes affect user-facing behavior, configuration options, API endpoints, or architecture, update the relevant documentation in `docs/` as part of the same PR. See the [Documentation Hub](docs/README.md) for the doc structure.

3. **Run all checks** before committing:
   ```bash
   npm run lint
   npm run typecheck
   cd backend && python -m pytest -v
   ```

4. **Write clear commit messages** that explain the "why" rather than the "what".

5. **Open a pull request** against `main` with:
   - A clear title (under 70 characters)
   - A summary of changes in the description
   - Any testing instructions

6. **Address review feedback** with new commits (do not force-push over review comments).

## Useful Commands

| Command | Description |
|---|---|
| `npm run dev` | Start Vite frontend dev server |
| `npm run build` | Production frontend build (outputs to `dist/`) |
| `npm run preview` | Preview production build locally |
| `npm run lint` | Run ESLint on frontend code |
| `npm run typecheck` | TypeScript type checking (`tsc --noEmit`) |
| `cd backend && uvicorn app.main:app --reload` | Start backend with hot reload |
| `cd backend && python -m pytest -v` | Run backend tests |
| `docker compose up -d` | Start all services |
| `docker compose up -d shellguard-db` | Start database only |
| `docker compose logs -f shellguard` | Tail backend logs |
