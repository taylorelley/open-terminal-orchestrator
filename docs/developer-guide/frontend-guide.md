# Frontend Development Guide

This guide covers the architecture, conventions, and workflows for developing the Open Terminal Orchestrator frontend.

## Architecture Overview

The Open Terminal Orchestrator frontend is a React single-page application (SPA) with the following technology stack:

| Technology | Version | Purpose |
|------------|---------|---------|
| **React** | 18 | UI framework |
| **TypeScript** | Strict mode | Type safety |
| **Vite** | 5 | Build tool and dev server |
| **Tailwind CSS** | 3 | Utility-first styling |
| **React Router** | v7 | Client-side routing |
| **Recharts** | Latest | Dashboard charts and visualizations |
| **Lucide React** | Latest | Icon library |
| **Supabase JS** | Latest | Backend client (database, auth, realtime) |

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
│   └── AuthContext.tsx        # Supabase auth provider
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
    └── ui/                   # Reusable UI primitives
```

## Adding a New Page

Follow these steps to add a new route-level page:

### 1. Create the Page Component

Create a new file in `src/pages/`. Page components own their data fetching, state management, and layout.

```tsx
// src/pages/Reports.tsx
import { useState } from 'react';
import { useSupabaseQuery } from '../hooks/useSupabaseQuery';
import type { Report } from '../types';

export default function Reports() {
  const { data: reports, loading, error } = useSupabaseQuery<Report>('reports');

  if (loading) return <div className="p-6">Loading...</div>;
  if (error) return <div className="p-6 text-red-500">Error: {error.message}</div>;

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Reports</h1>
      {/* Page content */}
    </div>
  );
}
```

### 2. Add the Route in App.tsx

Register the route in the router configuration:

```tsx
// In App.tsx, inside the route definitions
<Route path="/reports" element={<Reports />} />
```

The route should be nested inside the `AdminLayout` wrapper to include the sidebar and top bar.

### 3. Add a Sidebar Link

Add a navigation entry in the Sidebar component (`src/components/layout/Sidebar.tsx`):

```tsx
{ label: 'Reports', path: '/reports', icon: FileText }
```

### 4. Add Type Definitions

If the page works with a new domain entity, add the type to `src/types/index.ts`:

```tsx
export interface Report {
  id: string;
  name: string;
  created_at: string;
  // ...
}
```

## Data Fetching with useSupabaseQuery

The `useSupabaseQuery` hook (`src/hooks/useSupabaseQuery.ts`) is the primary way to fetch data. It provides:

- Automatic data loading from Supabase tables
- Built-in loading and error states
- Automatic realtime subscriptions (data updates when the database changes)

### Basic Usage

```tsx
const { data, loading, error } = useSupabaseQuery<Policy>('policies');
```

### With Filters

```tsx
const { data, loading, error } = useSupabaseQuery<Sandbox>('sandboxes', {
  filter: { column: 'state', value: 'ACTIVE' },
});
```

### Realtime Updates

The hook automatically subscribes to Supabase Realtime channels for the queried table. When rows are inserted, updated, or deleted, the local state updates without a manual refetch.

## Component Patterns

### Pages (src/pages/)

Pages are full route-level components. They are responsible for:

- Fetching data via `useSupabaseQuery` or the Supabase client
- Managing local state (filters, modals, selections)
- Composing layout using UI primitives
- Handling user interactions and mutations

### UI Components (src/components/ui/)

UI components are stateless, reusable primitives. They receive all data via props and emit events via callbacks.

Available UI components:

| Component | Purpose |
|-----------|---------|
| `Badge` | Status indicators and labels |
| `Modal` | Overlay dialogs for confirmations and forms |
| `SlidePanel` | Side-panel drawers for detail views |
| `StatCard` | Dashboard metric cards |
| `EmptyState` | Placeholder for empty data sets |
| `Tabs` | Tabbed navigation within a page |

Example usage:

```tsx
import Badge from '../components/ui/Badge';
import Modal from '../components/ui/Modal';

<Badge variant="success">Active</Badge>

<Modal
  isOpen={showModal}
  onClose={() => setShowModal(false)}
  title="Confirm Action"
>
  <p>Are you sure you want to proceed?</p>
</Modal>
```

### Layout Components (src/components/layout/)

Layout components manage the application shell:

- **AdminLayout** -- wraps all authenticated routes with sidebar and top bar
- **Sidebar** -- navigation menu with route links
- **TopBar** -- header with user info and global actions

## Styling

All styling uses Tailwind CSS utility classes. There are no CSS modules, styled-components, or custom CSS files beyond `index.css` (which contains Tailwind directives).

### The cn() Helper

Use the `cn()` helper from `src/lib/utils.ts` for conditional class merging:

```tsx
import { cn } from '../lib/utils';

<div className={cn(
  'rounded-lg border p-4',
  isActive && 'border-blue-500 bg-blue-50',
  isDisabled && 'opacity-50 cursor-not-allowed'
)} />
```

This utility merges classes cleanly and handles Tailwind class conflicts.

### Styling Conventions

- Use Tailwind utility classes directly in JSX.
- Avoid creating custom CSS classes.
- Use `cn()` for conditional or dynamic class names.
- Follow the existing color palette and spacing scale used throughout the project.

## Type Definitions

All domain types are defined in `src/types/index.ts`. Key entities include:

| Type | Description |
|------|-------------|
| `Policy` | Security policy with YAML definition and versioning |
| `Sandbox` | Per-user container with lifecycle states |
| `User` | Open WebUI user synced into Open Terminal Orchestrator |
| `Group` | User group with optional policy assignment |
| `PolicyAssignment` | Maps policies to users, groups, or roles |
| `AuditLogEntry` | Enforcement, lifecycle, and admin events |
| `SystemConfig` | Key-value system configuration |

When adding new types, define them in this file and import them where needed. Do not define types inline in page components.

## Authentication

Authentication is managed by the `AuthContext` (`src/contexts/AuthContext.tsx`), which wraps the application in `App.tsx`.

### Using the Auth Context

```tsx
import { useAuth } from '../contexts/AuthContext';

function MyComponent() {
  const { user, session, signOut } = useAuth();

  if (!user) return null;

  return <span>Logged in as {user.email}</span>;
}
```

### Auth Flow

1. `App.tsx` wraps all routes in `AuthProvider`.
2. Unauthenticated users are redirected to `/login`.
3. The `Login` page handles email/password authentication via Supabase Auth.
4. On successful login, the session is stored and the user is redirected to the dashboard.

## Build and Chunk Splitting

The Vite build configuration splits the production bundle into optimized chunks:

| Chunk | Contents |
|-------|----------|
| `vendor` | React, React DOM, React Router |
| `charts` | Recharts and its dependencies |
| `supabase` | Supabase JS client library |

This splitting ensures that large dependencies are cached independently and not re-downloaded when application code changes.

### Build Commands

```bash
npm run build    # Production build (output in dist/)
npm run preview  # Preview the production build locally
```

### Environment Variables

Frontend environment variables must be prefixed with `VITE_` to be available in the browser bundle:

```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

Access them in code via `import.meta.env`:

```tsx
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
```
