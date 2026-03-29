# CLAUDE.md — Open Terminal Orchestrator

## Project Overview

Open Terminal Orchestrator is an admin dashboard for orchestrating secure, per-user terminal sandboxes for Open WebUI. It provides policy-enforced sandbox management, real-time monitoring, audit logging, and user/group administration. The frontend is a React SPA backed by Supabase (PostgreSQL + Auth + Realtime).

See `PRD.md` for full product requirements and architecture details.

## Tech Stack

- **Language:** TypeScript (strict mode)
- **Framework:** React 18 with React Router v7
- **Build:** Vite 5
- **Styling:** Tailwind CSS 3 + PostCSS
- **Backend:** Supabase (PostgreSQL, Auth, Realtime subscriptions)
- **Charts:** Recharts
- **Icons:** Lucide React
- **Linting:** ESLint 9 with TypeScript ESLint + React Hooks/Refresh plugins

## Commands

```bash
npm run dev        # Start Vite dev server
npm run build      # Production build (outputs to dist/)
npm run preview    # Preview production build locally
npm run lint       # Run ESLint across the project
npm run typecheck  # TypeScript type checking (tsc --noEmit)
```

### Backend

```bash
cd backend && pip install -e ".[test]"   # Install backend with test deps
cd backend && python -m pytest -v        # Run backend tests
```

Always run `lint` and `typecheck` to validate frontend changes before committing.

## Project Structure

```
src/
├── main.tsx                  # React entry point
├── App.tsx                   # Router with protected routes
├── index.css                 # Tailwind base styles
├── types/index.ts            # All TypeScript interfaces and type aliases
├── lib/
│   ├── supabase.ts           # Supabase client initialization
│   └── utils.ts              # Shared utilities (formatting, cn helper)
├── contexts/
│   └── AuthContext.tsx        # Supabase auth provider (session, user, login/signup)
├── hooks/
│   └── useSupabaseQuery.ts   # Data fetching hook with realtime subscriptions
├── pages/                    # Route-level page components
│   ├── Dashboard.tsx
│   ├── Policies.tsx
│   ├── Sandboxes.tsx
│   ├── UsersGroups.tsx
│   ├── AuditLog.tsx
│   ├── Monitoring.tsx
│   ├── Settings.tsx
│   └── Login.tsx
└── components/
    ├── layout/               # App shell (AdminLayout, Sidebar, TopBar)
    └── ui/                   # Reusable UI primitives (Badge, Modal, SlidePanel, StatCard, EmptyState, Tabs)

supabase/
└── migrations/               # PostgreSQL migration files (schema, RLS policies, indexes)
```

## Architecture Patterns

### Authentication
- Supabase email/password auth managed via `AuthContext` (`src/contexts/AuthContext.tsx`)
- `App.tsx` wraps routes in `AuthProvider`; unauthenticated users redirect to `/login`

### Data Fetching
- `useSupabaseQuery` hook (`src/hooks/useSupabaseQuery.ts`) provides data loading with automatic Supabase realtime subscriptions
- All database access goes through the Supabase JS client (`src/lib/supabase.ts`)

### Routing
- React Router v7 with a flat route structure in `App.tsx`
- `AdminLayout` wraps all authenticated routes (sidebar + top bar)

### Component Conventions
- **Pages** (`src/pages/`) are full route components — they own data fetching, state, and layout for their route
- **UI components** (`src/components/ui/`) are stateless, reusable primitives — they receive data via props
- **Layout components** (`src/components/layout/`) handle the app shell structure

### Styling
- Tailwind CSS utility classes for all styling — no CSS modules or styled-components
- `cn()` helper from `src/lib/utils.ts` for conditional class merging

## Domain Types

All domain types live in `src/types/index.ts`. Key entities:

| Type | Description |
|------|-------------|
| `Policy` | Security policy with YAML definition and versioning |
| `Sandbox` | Per-user container (states: POOL, WARMING, READY, ACTIVE, SUSPENDED, DESTROYED) |
| `User` | Open WebUI user synced into Open Terminal Orchestrator |
| `Group` | User group with optional policy assignment |
| `PolicyAssignment` | Maps policies to users, groups, or roles with priority |
| `AuditLogEntry` | Enforcement, lifecycle, and admin events |
| `SystemConfig` | Key-value system configuration |

## Database

- **Engine:** PostgreSQL via Supabase
- **Migrations:** `supabase/migrations/` — applied via Supabase CLI
- **RLS:** Row-Level Security enabled on all tables; admin-only access enforced
- **Key tables:** `policies`, `policy_versions`, `groups`, `users`, `sandboxes`, `policy_assignments`, `audit_log`, `system_config`

## Environment Variables

Required in `.env` (not committed):

```
VITE_SUPABASE_URL=<your-supabase-project-url>
VITE_SUPABASE_ANON_KEY=<your-supabase-anon-key>
```

## Code Conventions

- TypeScript strict mode with `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`
- ESLint enforces React Hooks rules and React Refresh compatibility
- No test framework is configured yet — testing infrastructure is a future addition
- No Prettier — rely on ESLint for code quality
- Vite build splits chunks: `vendor` (React), `charts` (Recharts), `supabase` (Supabase JS)

## Documentation Maintenance

**Rule:** When making changes that affect any of the following, update the corresponding documentation in the same commit or PR:

| Change Type | Update These Docs |
|---|---|
| New or changed API endpoints | `docs/architecture/api-reference.md` |
| New or changed configuration / env vars | `docs/admin-guide/configuration-reference.md` AND `.env.example` |
| New frontend pages or features | `docs/user-guide/` (relevant file) AND `docs/developer-guide/frontend-guide.md` |
| New backend routes or services | `docs/developer-guide/backend-guide.md` |
| Policy engine changes | `docs/user-guide/managing-policies.md` |
| Deployment or infrastructure changes | `docs/admin-guide/deployment.md` |
| Database schema changes | `docs/developer-guide/database-migrations.md` |
| Security-relevant changes | `docs/architecture/security-review.md` |
| Authentication changes | `docs/admin-guide/authentication.md` |
| Monitoring or alerting changes | `docs/admin-guide/monitoring-alerting.md` |
| Sandbox lifecycle changes | `docs/user-guide/managing-sandboxes.md` |

If you add a new documentation file, add a link to it in `docs/README.md`.

### Documentation Structure

```
docs/
├── README.md                    # Documentation hub — start here
├── user-guide/                  # For operators using the dashboard
│   ├── getting-started.md
│   ├── dashboard-overview.md
│   ├── managing-sandboxes.md
│   ├── managing-policies.md
│   └── managing-users-groups.md
├── admin-guide/                 # For sysadmins deploying and configuring
│   ├── deployment.md
│   ├── configuration-reference.md
│   ├── authentication.md
│   ├── tls-reverse-proxy.md
│   ├── inference-routing.md
│   ├── monitoring-alerting.md
│   └── backup-restore.md
├── operations/                  # Day-to-day operational procedures
│   ├── runbook.md
│   └── troubleshooting.md
├── architecture/                # System design and reference
│   ├── overview.md
│   ├── api-reference.md
│   └── security-review.md
├── developer-guide/             # For contributors extending the codebase
│   ├── setup.md
│   ├── frontend-guide.md
│   ├── backend-guide.md
│   ├── testing.md
│   └── database-migrations.md
└── releases/
    └── changelog.md
```
