# Managing Users & Groups

ShellGuard synchronizes users from Open WebUI and provides group-based organization and policy assignment. This guide covers the user directory, group management, and the policy resolution system.

---

## User Sync from Open WebUI

ShellGuard does not maintain its own user registration. Instead, it synchronizes user records from Open WebUI to ensure that every person who can request a terminal session has a corresponding ShellGuard identity.

### Automatic Sync

User records are synchronized automatically in two ways:

1. **On first terminal request** -- When a user triggers a terminal session in Open WebUI, the `X-Open-WebUI-User-Id` header is sent to ShellGuard. If no matching user record exists, ShellGuard queries the Open WebUI API to fetch the user's profile (name, email, role) and creates a local record.

2. **Periodic background sync** -- A background job runs on a configurable interval (default: every 15 minutes) to pull new and updated users from Open WebUI. This ensures the ShellGuard user directory stays current even for users who have not yet requested a terminal session.

### Manual Sync

To trigger an immediate sync:

1. Navigate to **Users & Groups** in the sidebar.
2. Click the **Sync Users** button in the top-right corner.
3. A progress indicator shows the sync status. New users appear in the directory once the sync completes.

### Sync Behavior

- New users from Open WebUI are created in ShellGuard with the **pending** role by default, regardless of their Open WebUI role.
- Existing users have their **name** and **email** updated if changed in Open WebUI.
- Users deleted in Open WebUI are not automatically removed from ShellGuard. An admin must manually deactivate or delete them.
- The sync does not overwrite ShellGuard-specific fields (role, group membership, policy assignments).

---

## User Directory

The user directory is a searchable, sortable table of all known users.

### Columns

| Column | Description |
|--------|-------------|
| **Name** | User's display name (synced from Open WebUI) |
| **Email** | User's email address |
| **Role** | ShellGuard role: `admin`, `user`, or `pending` |
| **Group** | Group(s) the user belongs to |
| **Policy** | Directly assigned policy, if any (overrides group/role default) |
| **Last Active** | Timestamp of the user's most recent terminal session |
| **Status** | Whether the user has an active sandbox, is idle, or has never connected |

### Search and Filter

- **Search bar:** Filter by name or email (partial match supported)
- **Role filter:** Dropdown to show only admins, users, or pending users
- **Group filter:** Dropdown to show members of a specific group
- **Policy filter:** Dropdown to show users assigned to a specific policy

### User Detail Panel

Click a user row to open a slide-out detail panel showing:

- Full profile information
- Current role and group memberships
- Assigned policy (direct, group-inherited, or role default) with the resolution source
- Sandbox history (recent and active sandboxes)
- Audit log entries for this user

---

## Roles

ShellGuard uses three roles to control access and defaults:

| Role | Description |
|------|-------------|
| **admin** | Full access to the ShellGuard dashboard. Can manage all users, groups, policies, and system settings. Can access any sandbox terminal. |
| **user** | Standard role for terminal consumers. Cannot access the admin dashboard. Terminal sessions are governed by their assigned policy. |
| **pending** | Default role for newly synced users. Pending users cannot create terminal sessions until an admin promotes them to `user` or `admin`. |

### Changing a User's Role

1. Open the user detail panel by clicking on the user row.
2. Click the **Role** dropdown.
3. Select the new role.
4. Confirm the change.

Role changes take effect immediately. If a pending user is promoted to `user`, they can request terminal sessions on their next attempt. If an active user is changed to `pending`, their current sandbox (if any) remains active until it times out or is manually destroyed, but new sessions are blocked.

Role changes are recorded in the audit log.

---

## Groups

Groups let you organize users and assign policies collectively rather than individually.

### Creating a Group

1. Navigate to **Users & Groups**.
2. Click the **Groups** tab.
3. Click **Create Group**.
4. Fill in:
   - **Name** -- A descriptive name (e.g., "Engineering", "Data Science", "Interns")
   - **Description** -- Optional description of the group's purpose
   - **Default Policy** -- Select a policy to apply to all members of this group
5. Click **Save**.

### Editing a Group

1. Click on a group row to open the detail panel.
2. Modify the name, description, or default policy.
3. Click **Save**.

Changes to a group's default policy affect all members who do not have a user-level policy override. The new policy applies to their next sandbox session (existing active sandboxes retain the policy they were created with).

### Deleting a Group

1. Open the group detail panel.
2. Click **Delete Group**.
3. Confirm the deletion.

Deleting a group removes all membership associations. Users who were in the group fall back to their role-based default policy. Active sandboxes are not affected.

### Managing Group Membership

**Adding users to a group:**

1. Open the group detail panel.
2. In the **Members** section, click **Add Members**.
3. Search for users by name or email.
4. Select one or more users and click **Add**.

**Removing users from a group:**

1. Open the group detail panel.
2. In the **Members** section, click the remove icon next to the user.
3. Confirm the removal.

A user can belong to multiple groups. When a user is in multiple groups with different policies, the policy resolution system determines which policy applies (see below).

---

## Assigning Policies

Policies can be assigned at three levels: directly to a user, to a group, or as a role default.

### Direct User Assignment

1. Open the user detail panel.
2. In the **Policy** section, click **Assign Policy**.
3. Select a policy from the dropdown.
4. Click **Save**.

To remove a direct assignment, click **Remove Override** in the policy section. The user will then inherit their group or role default.

### Group Assignment

1. Open the group detail panel.
2. Set the **Default Policy** dropdown to the desired policy.
3. Click **Save**.

All members of the group inherit this policy unless they have a direct user-level override.

### Role Default

Role defaults are configured in **Settings > Policies**:

| Setting | Description |
|---------|-------------|
| **Admin default policy** | Policy applied to users with the `admin` role who have no direct or group assignment |
| **User default policy** | Policy applied to users with the `user` role who have no direct or group assignment |

> **Note:** Users with the `pending` role cannot create sessions and do not need a default policy.

---

## Policy Resolution Precedence

When a user requests a terminal session, ShellGuard determines the effective policy using the following precedence order (highest to lowest):

```
1. User-level override  (direct assignment to the specific user)
        |
        v  (if none)
2. Group assignment      (policy from the user's group)
        |
        v  (if none, or multiple groups)
3. Role default          (system-wide default for the user's role)
        |
        v  (if none)
4. System default        (global fallback policy)
```

### Detailed Rules

1. **User-level override** -- If a policy is directly assigned to the user, it always wins regardless of group or role.

2. **Group assignment** -- If the user has no direct override and belongs to one group with a policy, that group's policy is used.

3. **Multiple groups** -- If the user belongs to multiple groups with different policies, the policy with the **highest priority value** wins. Priority is a numeric field on the policy assignment record (lower number = higher priority). In case of a tie, the most recently created assignment wins.

4. **Role default** -- If the user has no direct override and no group-level policy (or belongs to groups with no policy set), the system-wide default for their role is used.

5. **System default** -- If no role default is configured, the system-wide fallback policy is used. This is configured in **Settings > Policies > System Default Policy** and should always be set.

### Viewing Effective Policy

The user detail panel shows the **effective policy** along with a label indicating its source:

- "Direct" -- User-level override
- "Group: Engineering" -- Inherited from a group (group name shown)
- "Role default" -- From the role-level system setting
- "System default" -- Global fallback

This makes it easy to understand why a particular user has a specific policy and where to go to change it.

---

## Bulk Operations

### Bulk Role Change

1. On the Users tab, select multiple users using the checkboxes.
2. Click **Change Role** in the bulk action bar.
3. Select the target role.
4. Confirm.

### Bulk Group Assignment

1. Select multiple users.
2. Click **Add to Group** in the bulk action bar.
3. Choose the target group.
4. Confirm.

### Bulk Policy Assignment

1. Select multiple users.
2. Click **Assign Policy** in the bulk action bar.
3. Choose the policy.
4. Confirm.

All bulk operations are recorded as individual audit log entries for each affected user.

---

## Next Steps

- [Managing Policies](managing-policies.md) -- Learn how to create and configure security policies
- [Managing Sandboxes](managing-sandboxes.md) -- See how policies affect sandbox provisioning
- [Audit Log](audit-log.md) -- Review user and group change events
- [Dashboard Overview](dashboard-overview.md) -- Return to the dashboard guide
