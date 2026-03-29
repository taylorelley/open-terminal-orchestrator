# Dashboard Overview

This guide introduces the Open Terminal Orchestrator admin dashboard -- the central interface for managing sandboxes, policies, users, and monitoring your deployment.

---

## Navigation

The dashboard uses a persistent sidebar on the left for primary navigation. The sidebar contains the following items:

| Icon | Label | Route | Description |
|------|-------|-------|-------------|
| LayoutDashboard | **Dashboard** | `/` | At-a-glance metrics, charts, and activity feed |
| Box | **Sandboxes** | `/sandboxes` | Manage active, suspended, and pooled sandbox containers |
| Shield | **Policies** | `/policies` | Create and assign YAML security policies |
| Users | **Users & Groups** | `/users` | User directory, group management, and policy assignments |
| ScrollText | **Audit Log** | `/audit` | Searchable, filterable log of all system events |
| Activity | **Monitoring** | `/monitoring` | Resource usage charts, alert rules, and webhooks |
| Settings | **Settings** | `/settings` | System configuration, pool settings, auth, and integrations |

The **top bar** displays the current page title, a global search input, notification bell, and the authenticated user's avatar with a dropdown menu for profile and sign-out.

---

## Dashboard Page

The Dashboard is the landing page after login. It provides a high-level view of your Open Terminal Orchestrator deployment.

### Stat Cards

The top row displays key metrics in real-time stat cards:

| Metric | Description |
|--------|-------------|
| **Active Sandboxes** | Number of sandboxes currently in the ACTIVE state |
| **Suspended** | Sandboxes in SUSPENDED state, awaiting resume or destruction |
| **Pool Size** | Number of pre-warmed containers in POOL/WARMING/READY states |
| **Enforcement Events** | Policy enforcement actions in the last 24 hours |
| **Avg Startup Time** | Average time to transition a sandbox from READY to ACTIVE |

Each card shows the current value, a trend indicator (up/down compared to the previous period), and a sparkline chart.

### Active Sandboxes Table

Below the stat cards, a table lists all currently active sandboxes with columns for:

- User (name and email)
- Sandbox ID
- Assigned policy
- State
- CPU and memory usage
- Uptime
- Actions (suspend, destroy, open terminal)

The table supports sorting by any column and pagination.

### Resource Usage Charts

Two time-series charts display aggregate resource consumption:

- **CPU & Memory** -- Stacked area chart showing total CPU percentage and memory usage across all active sandboxes over the last hour.
- **Network I/O** -- Line chart showing inbound and outbound network traffic.

Charts update in real time via Supabase Realtime subscriptions.

### Activity Feed

A chronological feed on the right side of the dashboard shows the most recent system events:

- Sandbox lifecycle transitions (created, activated, suspended, destroyed)
- Policy enforcement actions (command blocked, resource limit hit)
- Admin actions (policy updated, user role changed)

Each entry includes a timestamp, event type badge, and a brief description. Clicking an entry navigates to the relevant detail view.

---

## Page Summaries

### Sandboxes

The Sandboxes page provides full management of all sandbox containers.

- **Tabs:** Active, Suspended, Pool (POOL/WARMING/READY), Destroyed (recent history)
- **Search and filter:** Filter by user, policy, state, or date range
- **Bulk actions:** Select multiple sandboxes to suspend, resume, or destroy in batch
- **Detail panel:** Click a sandbox row to open a slide-out panel with full details, resource metrics, event history, and an embedded terminal view
- **Terminal embed:** Directly access a sandbox terminal from the dashboard for debugging or inspection

### Policies

The Policies page is where you define and manage security policies.

- **Policy library:** Card-based grid showing all policies with their tier (restricted, standard, elevated), status (active/draft), and assignment count
- **YAML editor:** Full-featured editor for writing policy definitions with syntax highlighting and validation
- **Version history:** Every policy edit creates a new version; browse and compare previous versions or roll back
- **Assignments:** View and manage which users, groups, or roles are assigned to each policy
- **Publish workflow:** Policies can be saved as drafts and published when ready

### Users & Groups

The Users & Groups page manages identity and access.

- **User directory:** Table of all users synced from Open WebUI, showing name, email, role (admin/user/pending), assigned policy, group membership, and last active timestamp
- **Manual sync:** Button to trigger an immediate user sync from Open WebUI
- **Group management:** Create, edit, and delete groups; assign users to groups; assign a default policy to each group
- **Policy assignments:** Assign policies directly to individual users, overriding group or role defaults
- **Role management:** Change user roles (admin, user, pending)

### Audit Log

The Audit Log page provides a searchable record of all system events.

- **Real-time streaming:** New events appear at the top of the log without page refresh
- **Category filters:** Filter by event category:
  - **Enforcement** -- Policy violations, blocked commands, resource limit events
  - **Lifecycle** -- Sandbox state transitions (created, activated, suspended, destroyed)
  - **Admin** -- Configuration changes, user role changes, policy edits
- **Date presets:** Quick filters for last hour, last 24 hours, last 7 days, last 30 days, or custom range
- **Full-text search:** Search across event descriptions, user names, sandbox IDs, and policy names
- **Export:** Download filtered results as CSV or JSON for external analysis

### Monitoring

The Monitoring page provides detailed resource visibility and alerting.

- **Resource charts:** Time-series charts for:
  - CPU utilization (per-sandbox and aggregate)
  - Memory usage (per-sandbox and aggregate)
  - Disk usage and I/O
  - Network traffic (inbound/outbound)
- **Time range selector:** View metrics over 1 hour, 6 hours, 24 hours, 7 days, or custom range
- **Alert rules:** Define threshold-based alerts (e.g., "alert when any sandbox exceeds 90% CPU for 5 minutes")
- **Webhook configuration:** Send alert notifications to Slack, PagerDuty, or any HTTP endpoint
- **Active alerts:** Table of currently firing alerts with acknowledge and resolve actions

### Settings

The Settings page controls system-wide configuration.

- **General:** System name, default timezone, session expiry duration
- **Pool settings:** Warmup size (number of pre-warmed containers), maximum total sandboxes, maximum active sandboxes per user
- **Lifecycle timeouts:**
  - Idle timeout -- time before an idle active sandbox is suspended
  - Suspend timeout -- time before a suspended sandbox is destroyed
  - Startup timeout -- maximum time allowed for sandbox startup
  - Resume timeout -- maximum time allowed for resuming a suspended sandbox
- **Authentication:** OIDC provider configuration, allowed email domains, session settings
- **Integrations:** OpenShell Gateway URL, LiteLLM proxy URL, Open WebUI connection settings
- **Danger zone:** Reset pool, purge destroyed sandboxes, export/import system configuration

---

## Keyboard Shortcuts

The dashboard supports keyboard shortcuts for common actions:

| Shortcut | Action |
|----------|--------|
| `g d` | Go to Dashboard |
| `g s` | Go to Sandboxes |
| `g p` | Go to Policies |
| `g u` | Go to Users & Groups |
| `g a` | Go to Audit Log |
| `g m` | Go to Monitoring |
| `/` | Focus global search |
| `Esc` | Close open panel or modal |

---

## Next Steps

- [Managing Sandboxes](managing-sandboxes.md) -- Deep dive into sandbox operations
- [Managing Users & Groups](managing-users-groups.md) -- User and group administration
- [Managing Policies](managing-policies.md) -- Policy creation and assignment
