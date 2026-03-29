# Managing Sandboxes

Sandboxes are the core unit in Open Terminal Orchestrator -- isolated terminal containers provisioned for each user session. This guide covers the sandbox lifecycle, day-to-day management, pool configuration, and monitoring.

---

## Sandbox Lifecycle

Every sandbox transitions through a defined set of states. Understanding these states is essential for effective management.

### State Diagram

```
                +---------+
                |  POOL   |
                +----+----+
                     |
              (pre-warm trigger)
                     |
                     v
               +-----------+
               |  WARMING  |
               +-----+-----+
                     |
             (container ready)
                     |
                     v
                +--------+
                |  READY  |
                +----+----+
                     |
             (user session starts)
                     |
                     v
               +----------+
               |  ACTIVE  |
               +----+-----+
                    |
         +----------+----------+
         |                     |
    (idle timeout)        (admin action /
         |                 destroy trigger)
         v                     |
   +------------+              |
   |  SUSPENDED |              |
   +-----+------+              |
         |                     |
    +----+----+                |
    |         |                |
 (resume)  (suspend           |
    |      timeout)            |
    v         |                |
 ACTIVE       +--------+------+
                       |
                       v
                 +------------+
                 |  DESTROYED |
                 +------------+
```

### State Descriptions

| State | Description |
|-------|-------------|
| **POOL** | Container image is allocated to the pool but not yet started. This is a placeholder entry representing capacity. |
| **WARMING** | Container is starting up and initializing. The base image is being pulled (if needed), filesystem is mounted, and the sandbox agent is booting. |
| **READY** | Container is fully initialized and waiting for a user session. Ready sandboxes are drawn from the pool when a user requests a terminal. |
| **ACTIVE** | A user is connected to this sandbox. The assigned security policy is enforced. Resource metrics are being collected. |
| **SUSPENDED** | The user session ended or the idle timeout was reached. The container is frozen (SIGSTOP / checkpoint). Filesystem state is preserved. Suspended sandboxes can be resumed quickly. |
| **DESTROYED** | The container has been permanently removed. A destroyed sandbox record is retained in the database for audit purposes but cannot be recovered. |

---

## Viewing Sandboxes

Navigate to **Sandboxes** in the sidebar to access the sandbox management page.

### Tabs

The page is organized into tabs by sandbox state:

- **Active** -- All sandboxes currently in the ACTIVE state, sorted by most recent activity
- **Suspended** -- Sandboxes in SUSPENDED state, showing time since suspension
- **Pool** -- Sandboxes in POOL, WARMING, and READY states, representing available capacity
- **Destroyed** -- Recently destroyed sandboxes (retained for the configured history period)

### Search and Filter

Use the controls above the sandbox table to narrow results:

- **Search:** Full-text search across sandbox ID, user name, and user email
- **Policy filter:** Dropdown to show only sandboxes assigned to a specific policy
- **Date range:** Filter by creation date or last activity date
- **Sort:** Click any column header to sort ascending or descending

---

## Sandbox Actions

### Individual Actions

Click the action menu (three dots) on any sandbox row, or open the detail panel, to perform these actions:

| Action | Available In | Description |
|--------|-------------|-------------|
| **Suspend** | ACTIVE | Freezes the container, preserving filesystem state. The user's terminal session is disconnected. |
| **Resume** | SUSPENDED | Thaws the container and returns it to ACTIVE state. If the user reconnects, they see their previous session. |
| **Destroy** | ACTIVE, SUSPENDED | Permanently removes the container and releases all resources. This action cannot be undone. |
| **Recreate** | DESTROYED | Provisions a new sandbox for the same user with the same policy. The new sandbox starts fresh (no state from the destroyed one). |
| **Open Terminal** | ACTIVE | Opens an embedded terminal view connected to the sandbox, allowing direct inspection and interaction. |
| **View Logs** | Any | Opens the event log filtered to this sandbox, showing all lifecycle transitions and enforcement events. |

### Confirmation

Destructive actions (Destroy, bulk destroy) require confirmation via a modal dialog. The dialog shows the sandbox ID, assigned user, and current state.

### Bulk Operations

To act on multiple sandboxes at once:

1. Check the selection boxes on the left side of the sandbox table.
2. A bulk action bar appears at the top of the table.
3. Available bulk actions depend on the current tab:
   - **Active tab:** Bulk suspend, Bulk destroy
   - **Suspended tab:** Bulk resume, Bulk destroy
   - **Pool tab:** Bulk destroy (remove excess capacity)
4. Confirm the action in the dialog that shows the count and list of affected sandboxes.

---

## Pool Configuration

The sandbox pool ensures that new user sessions start quickly by maintaining a set of pre-warmed containers.

### Pool Settings

Configure pool behavior in **Settings > Pool Settings** or via environment variables:

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| **Warmup Size** | `POOL_WARMUP_SIZE` | `3` | Target number of READY containers to maintain in the pool. Open Terminal Orchestrator automatically provisions new containers when the pool drops below this count. |
| **Max Sandboxes** | `MAX_SANDBOXES` | `50` | Hard limit on total sandbox containers across all states (excluding DESTROYED). When reached, new sessions queue until capacity is available. |
| **Max Active Per User** | `MAX_ACTIVE_PER_USER` | `1` | Maximum concurrent ACTIVE sandboxes per user. Additional session requests reuse the existing active sandbox or queue. |

### How Pooling Works

1. On startup, Open Terminal Orchestrator provisions containers up to the warmup size. Each transitions through POOL, WARMING, and READY.
2. When a user requests a terminal session, a READY container is assigned and transitions to ACTIVE.
3. The pool manager detects the reduced pool count and begins warming a replacement container.
4. If no READY containers are available, the request waits (up to `STARTUP_TIMEOUT`) for a container to become ready.

### Monitoring Pool Health

The Dashboard stat card for **Pool Size** shows the current count of POOL + WARMING + READY containers. A healthy deployment keeps this at or near the warmup size. If pool size consistently drops to zero, consider increasing `POOL_WARMUP_SIZE` or `MAX_SANDBOXES`.

---

## Terminal Access

Active sandboxes include a full PTY terminal powered by the [open-terminal](https://github.com/open-webui/open-terminal) package running inside each sandbox container. The admin dashboard provides an xterm.js-based terminal emulator that connects to the sandbox via a bidirectional WebSocket relay.

Terminal features include:
- Full ANSI color and cursor support (vi, nano, htop, etc.)
- Automatic terminal resizing to fit the panel
- Clickable URLs detected in terminal output
- Copy/paste support

To access a sandbox terminal:

1. Navigate to **Sandboxes > Active**.
2. Click on a sandbox row to open the detail panel.
3. Click the **Open Terminal** button.
4. An xterm.js terminal emulator opens within the dashboard, connected to the sandbox's Open Terminal PTY via WebSocket.

Open WebUI users also get terminal access directly through Open WebUI's terminal integration, which connects to Open Terminal Orchestrator's `/ws/terminal` WebSocket endpoint and is transparently routed to their assigned sandbox.

> **Note:** Admin terminal access is logged as an audit event. All commands executed by administrators are recorded separately from user activity.

---

## Sandbox Metrics

Each active sandbox reports resource usage in real time. View metrics in the sandbox detail panel or on the Monitoring page.

| Metric | Description | Update Interval |
|--------|-------------|-----------------|
| **CPU** | Percentage of allocated CPU currently in use | 5 seconds |
| **Memory** | Current RSS memory usage in MB and percentage of limit | 5 seconds |
| **Disk** | Filesystem usage in MB and percentage of quota | 30 seconds |
| **Network I/O** | Cumulative bytes sent and received since sandbox creation | 5 seconds |

Resource limits are defined by the assigned security policy. When a sandbox exceeds a policy-defined threshold, an enforcement event is logged and the configured action is taken (warn, throttle, or terminate).

---

## Lifecycle Timeouts

Timeouts govern automatic state transitions. Configure these in **Settings > Lifecycle Timeouts** or via environment variables.

| Timeout | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| **Idle Timeout** | `IDLE_TIMEOUT` | `30m` | Duration of inactivity (no terminal input) before an ACTIVE sandbox is automatically suspended. Set to `0` to disable. |
| **Suspend Timeout** | `SUSPEND_TIMEOUT` | `24h` | Duration a sandbox remains in SUSPENDED state before automatic destruction. Set to `0` to keep suspended sandboxes indefinitely. |
| **Startup Timeout** | `STARTUP_TIMEOUT` | `60s` | Maximum time allowed for a sandbox to transition from WARMING to READY. If exceeded, the container is destroyed and a new one is provisioned. |
| **Resume Timeout** | `RESUME_TIMEOUT` | `30s` | Maximum time allowed for a SUSPENDED sandbox to resume to ACTIVE. If exceeded, the sandbox is destroyed and a fresh one is created for the user. |

### Timeout Behavior

- **Idle timeout** is measured from the last user input event (keystroke, command execution). Background processes do not reset the idle timer.
- **Suspend timeout** begins when the sandbox enters SUSPENDED state. If the user returns within this window, the sandbox resumes instantly.
- Timeouts are evaluated by a background scheduler that runs every 30 seconds. Actual transitions may occur up to 30 seconds after the configured timeout.

---

## Next Steps

- [Managing Users & Groups](managing-users-groups.md) -- Control who gets which sandbox policies
- [Managing Policies](managing-policies.md) -- Define the security rules applied to sandboxes
- [Monitoring & Alerts](monitoring-alerts.md) -- Set up alerts for resource thresholds
- [Dashboard Overview](dashboard-overview.md) -- Return to the dashboard guide
