# CLAUDE.md — ShellGuard

## Project Overview

ShellGuard is an admin dashboard for orchestrating secure, per-user terminal sandboxes for Open WebUI. It provides policy-enforced sandbox management, real-time monitoring, audit logging, and user/group administration. The frontend is a React SPA backed by Supabase (PostgreSQL + Auth + Realtime).

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

Always run `lint` and `typecheck` to validate changes before committing.

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
| `User` | Open WebUI user synced into ShellGuard |
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
