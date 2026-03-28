# Contributing to ShellGuard

## Development Setup

### Prerequisites

- **Node.js** 20+ (frontend)
- **Python** 3.11+ (backend)
- **PostgreSQL** 16+ (database)

### Frontend

```bash
npm install
npm run dev          # Start Vite dev server on http://localhost:5173
```

Create `.env` with:
```
VITE_SUPABASE_URL=<your-supabase-url>
VITE_SUPABASE_ANON_KEY=<your-supabase-anon-key>
```

### Backend

```bash
cd backend
pip install -e ".[test]"
uvicorn app.main:app --reload --port 8080
```

Create `backend/.env` with:
```
DATABASE_URL=postgresql+asyncpg://shellguard:shellguard@localhost:5432/shellguard
```

### Database

For local development with Supabase:
```bash
supabase start
supabase db push
```

For standalone PostgreSQL with Alembic:
```bash
cd backend
alembic upgrade head
```

## Running Tests

### Backend tests
```bash
cd backend
python -m pytest -v
```

### Frontend validation
```bash
npm run lint         # ESLint
npm run typecheck    # TypeScript type checking
npm run build        # Production build
```

## Code Style

- **TypeScript**: Strict mode, no unused locals/parameters
- **Python**: Follow existing patterns — FastAPI routes, SQLAlchemy models, Pydantic schemas
- **Styling**: Tailwind CSS utility classes only — no CSS modules
- **Linting**: ESLint for frontend, no Prettier

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes
3. Run `npm run lint && npm run typecheck` (frontend)
4. Run `cd backend && python -m pytest -v` (backend)
5. Commit with a descriptive message
6. Open a PR with a clear description of changes

## Project Structure

See `CLAUDE.md` for the full project structure and architecture guide.
