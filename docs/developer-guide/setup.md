# Developer Setup Guide

This guide walks you through setting up a local Open Terminal Orchestrator development environment from scratch.

## Prerequisites

Ensure the following tools are installed on your system:

| Tool | Version | Purpose |
|------|---------|---------|
| **Node.js** | 20 LTS | Frontend build and development |
| **npm** | 10+ (bundled with Node.js 20) | Package management |
| **Python** | 3.12 | Backend runtime |
| **PostgreSQL** | 16 (or Docker) | Database |
| **Docker & Docker Compose** | Latest stable | Database and service orchestration |
| **Git** | 2.x | Version control |

### Verifying Prerequisites

```bash
node --version    # v20.x.x
python3 --version # Python 3.12.x
docker --version  # Docker 2x.x.x
git --version     # git version 2.x.x
```

## Clone the Repository

```bash
git clone https://github.com/oto/open-terminal-orchestrator.git
cd open-terminal-orchestrator
```

## Database Setup

The easiest way to run PostgreSQL locally is via Docker Compose. The project includes a Compose file with a pre-configured database service.

```bash
docker compose up -d oto-db
```

This starts a PostgreSQL 16 instance with the default development credentials. To verify:

```bash
docker compose ps oto-db
# Should show status: running

pg_isready -h localhost -p 5432
# Should show: accepting connections
```

To apply the database schema and migrations:

```bash
# If using the Supabase CLI
supabase db push

# Or apply manually
psql "postgresql://postgres:postgres@localhost:5432/oto" \
  -f supabase/migrations/*.sql
```

## Backend Setup

1. **Create a virtual environment:**

   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate   # On Windows: .venv\Scripts\activate
   ```

2. **Install dependencies (including test dependencies):**

   ```bash
   pip install -e ".[test]"
   ```

3. **Create the backend environment file:**

   ```bash
   cp .env.example .env
   ```

   Edit `backend/.env` and configure at minimum:

   ```env
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/oto
   ADMIN_API_KEY=dev-admin-key-change-in-production
   LOG_LEVEL=debug
   ```

4. **Start the development server:**

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   The API will be available at `http://localhost:8000`. Interactive docs are at `http://localhost:8000/docs`.

5. **Verify the backend is running:**

   ```bash
   curl http://localhost:8000/health
   ```

## Frontend Setup

1. **Install dependencies** (from the repository root):

   ```bash
   npm install
   ```

2. **Create the frontend environment file:**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` in the repository root and set:

   ```env
   VITE_SUPABASE_URL=http://localhost:54321
   VITE_SUPABASE_ANON_KEY=your-local-supabase-anon-key
   ```

   If you are running Supabase locally via `supabase start`, these values are printed on startup. If connecting to a hosted Supabase project, use the project URL and anon key from the Supabase dashboard.

3. **Start the development server:**

   ```bash
   npm run dev
   ```

   The frontend will be available at `http://localhost:5173` by default (Vite will print the exact URL).

4. **Verify the frontend is running:**

   Open `http://localhost:5173` in your browser. You should see the Open Terminal Orchestrator login page.

## Running Checks

Always run linting and type checking before committing frontend changes:

```bash
# Frontend
npm run lint         # ESLint across all TypeScript/React files
npm run typecheck    # TypeScript type checking (tsc --noEmit)

# Backend
cd backend
python -m pytest -v  # Run all backend tests
```

All checks must pass before submitting a pull request.

## IDE Recommendations

### Visual Studio Code

Install the following extensions for the best development experience:

| Extension | Purpose |
|-----------|---------|
| **ESLint** (`dbaeumer.vscode-eslint`) | JavaScript/TypeScript linting |
| **Tailwind CSS IntelliSense** (`bradlc.vscode-tailwindcss`) | Tailwind class autocomplete and hover previews |
| **Python** (`ms-python.python`) | Python language support, debugging, linting |
| **Pylance** (`ms-python.vscode-pylance`) | Python type checking and IntelliSense |
| **Prettier - Code formatter** (optional) | Formatting for JSON, YAML, Markdown files |

### Recommended VS Code Settings

Add to your workspace `.vscode/settings.json`:

```json
{
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": "explicit"
  },
  "typescript.tsdk": "node_modules/typescript/lib",
  "python.defaultInterpreterPath": "./backend/.venv/bin/python",
  "tailwindCSS.experimental.classRegex": [
    ["cn\\(([^)]*)\\)", "'([^']*)'"]
  ]
}
```

## Common Development Workflows

### Full Stack Development

Run both the backend and frontend simultaneously in separate terminals:

```bash
# Terminal 1: Backend
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload

# Terminal 2: Frontend
npm run dev
```

### Database Reset

To reset the database to a clean state:

```bash
docker compose down oto-db
docker volume rm oto_db_data   # Remove persistent data
docker compose up -d oto-db
# Re-apply migrations
```

### Production Build Test

To test the production frontend build locally:

```bash
npm run build    # Build to dist/
npm run preview  # Serve the production build
```
