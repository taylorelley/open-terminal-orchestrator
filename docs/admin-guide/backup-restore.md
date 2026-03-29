# Backup and Restore

This guide covers backup strategies, restore procedures, and disaster recovery planning for Open Terminal Orchestrator deployments.

---

## What Data Needs Backing Up

Open Terminal Orchestrator stores data in two locations:

### 1. PostgreSQL Database

The database contains all persistent application state:

| Table | Description | Criticality |
|-------|-------------|-------------|
| `policies` | Security policy definitions (name, description, status, YAML content) | **High** -- represents your security posture |
| `policy_versions` | Versioned history of each policy's YAML definition | **High** -- needed for audit and rollback |
| `users` | User records synced from Open WebUI | Medium -- can be re-synced from Open WebUI |
| `groups` | User groups with optional policy assignments | **High** -- defines access control structure |
| `policy_assignments` | Maps policies to users, groups, or roles with priority | **High** -- defines which policies apply where |
| `sandboxes` | Active and historical sandbox records (states, metadata) | Medium -- active sandboxes are ephemeral |
| `audit_log` | Enforcement events, lifecycle events, admin actions | **High** -- required for compliance |
| `system_config` | Key-value system configuration (pool settings, feature flags) | **High** -- defines system behavior |

### 2. Sandbox Data Volumes

Each user's sandbox has a persistent data volume mounted at `/data/<user>` on the host. These volumes contain user-generated files and terminal history. Their importance depends on your use case:

- **Ephemeral sandboxes:** Data volumes can be treated as disposable. No backup needed.
- **Persistent sandboxes:** Back up `/data/` if users store important work in their terminals.

---

## PostgreSQL Backup

### Manual Backup with pg_dump

Create a full database dump:

```bash
pg_dump -h oto-db -U oto -d oto \
  --format=custom \
  --compress=9 \
  --file=oto_$(date +%Y%m%d_%H%M%S).dump
```

For Docker Compose deployments, run the dump inside the database container:

```bash
docker compose exec oto-db \
  pg_dump -U oto -d oto \
    --format=custom \
    --compress=9 \
  > oto_$(date +%Y%m%d_%H%M%S).dump
```

**Flags explained:**

| Flag | Purpose |
|------|---------|
| `--format=custom` | Produces a compressed, restorable archive (supports selective restore) |
| `--compress=9` | Maximum gzip compression |

### Automated Backups with Cron

Create a backup script at `/opt/oto/backup.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="/var/backups/oto"
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/oto_${TIMESTAMP}.dump"

mkdir -p "${BACKUP_DIR}"

# Database backup
docker compose -f /opt/oto/docker-compose.yml exec -T oto-db \
  pg_dump -U oto -d oto \
    --format=custom \
    --compress=9 \
  > "${BACKUP_FILE}"

# Verify the backup is not empty
if [ ! -s "${BACKUP_FILE}" ]; then
  echo "ERROR: Backup file is empty" >&2
  rm -f "${BACKUP_FILE}"
  exit 1
fi

# Delete backups older than retention period
find "${BACKUP_DIR}" -name "oto_*.dump" -mtime +${RETENTION_DAYS} -delete

echo "Backup completed: ${BACKUP_FILE} ($(du -h "${BACKUP_FILE}" | cut -f1))"
```

Add a cron entry to run daily at 2:00 AM:

```bash
# /etc/cron.d/oto-backup
0 2 * * * root /opt/oto/backup.sh >> /var/log/oto-backup.log 2>&1
```

### Offsite Backup

Copy backups to an offsite location (S3, GCS, or a remote server):

```bash
# S3 example
aws s3 cp "${BACKUP_FILE}" s3://your-bucket/oto-backups/

# rsync to remote server
rsync -az "${BACKUP_DIR}/" backup-server:/backups/oto/
```

---

## Incremental Backup with WAL Archiving

For large databases or strict RPO (Recovery Point Objective) requirements, configure PostgreSQL continuous archiving.

### Enable WAL Archiving

Add the following to your PostgreSQL configuration (`postgresql.conf`):

```ini
wal_level = replica
archive_mode = on
archive_command = 'cp %p /var/backups/oto/wal/%f'
```

For Docker Compose, pass these as command-line arguments or mount a custom `postgresql.conf`.

### Base Backup

Take a base backup that WAL archives build upon:

```bash
pg_basebackup -h oto-db -U oto \
  -D /var/backups/oto/base \
  --format=tar \
  --gzip \
  --checkpoint=fast \
  --label="oto-base-$(date +%Y%m%d)"
```

### Recovery

To restore from a base backup and WAL archives:

1. Stop the database server.
2. Replace the data directory with the base backup.
3. Create a `recovery.signal` file and configure `restore_command` in `postgresql.conf`:
   ```ini
   restore_command = 'cp /var/backups/oto/wal/%f %p'
   recovery_target_time = '2026-03-29 12:00:00 UTC'  # optional: point-in-time
   ```
4. Start the database server. PostgreSQL will replay WAL files to reach the target state.

---

## Restore Procedure

### Full Restore from pg_dump

1. **Stop the Open Terminal Orchestrator backend** to prevent writes during restore:

   ```bash
   docker compose stop oto-backend
   ```

2. **Drop and recreate the database** (or restore to a new database):

   ```bash
   docker compose exec oto-db \
     psql -U oto -c "DROP DATABASE IF EXISTS oto;"
   docker compose exec oto-db \
     psql -U oto -c "CREATE DATABASE oto OWNER oto;"
   ```

3. **Restore the dump:**

   ```bash
   docker compose exec -T oto-db \
     pg_restore -U oto -d oto \
       --no-owner \
       --no-privileges \
       --clean \
       --if-exists \
     < oto_20260329_020000.dump
   ```

   | Flag | Purpose |
   |------|---------|
   | `--no-owner` | Skip setting object ownership (uses the restoring user) |
   | `--no-privileges` | Skip restoring grant/revoke commands |
   | `--clean` | Drop existing objects before creating them |
   | `--if-exists` | Suppress errors if objects don't exist during clean |

4. **Verify data integrity** (see next section).

5. **Restart the backend:**

   ```bash
   docker compose start oto-backend
   ```

### Selective Restore

To restore only specific tables (e.g., only policies):

```bash
pg_restore -U oto -d oto \
  --table=policies \
  --table=policy_versions \
  --data-only \
  oto_20260329_020000.dump
```

### Verifying Data Integrity

After restoring, run the following checks:

```sql
-- Check row counts for key tables
SELECT 'policies' AS table_name, COUNT(*) FROM policies
UNION ALL SELECT 'policy_versions', COUNT(*) FROM policy_versions
UNION ALL SELECT 'users', COUNT(*) FROM users
UNION ALL SELECT 'groups', COUNT(*) FROM groups
UNION ALL SELECT 'policy_assignments', COUNT(*) FROM policy_assignments
UNION ALL SELECT 'audit_log', COUNT(*) FROM audit_log
UNION ALL SELECT 'system_config', COUNT(*) FROM system_config
UNION ALL SELECT 'sandboxes', COUNT(*) FROM sandboxes;

-- Verify foreign key integrity
SELECT COUNT(*) AS orphaned_assignments
FROM policy_assignments pa
LEFT JOIN policies p ON pa.policy_id = p.id
WHERE p.id IS NULL;

-- Verify RLS policies are in place
SELECT tablename, policyname, permissive, cmd
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname;

-- Verify indexes exist
SELECT tablename, indexname
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename;
```

---

## Sandbox Data Volumes

### Backup

If your deployment uses persistent sandbox data, back up the volume directory:

```bash
# Full backup
tar czf sandbox_data_$(date +%Y%m%d).tar.gz /data/

# Incremental with rsync
rsync -az --delete /data/ /var/backups/oto/sandbox-data/
```

### Restore

```bash
# Stop all sandboxes first
docker compose exec oto-backend \
  curl -X POST http://localhost:8000/api/v1/admin/sandboxes/destroy-all

# Restore data
tar xzf sandbox_data_20260329.tar.gz -C /
```

> **Note:** Sandbox data volumes are tied to specific users. Restoring data volumes only makes sense if the corresponding user and sandbox records exist in the database.

---

## Audit Log Retention

The `AUDIT_RETENTION_DAYS` environment variable controls how long audit log entries are kept in the database. A background job runs daily and deletes entries older than this threshold.

```bash
AUDIT_RETENTION_DAYS=90   # Default: 90 days
```

### Compliance Considerations

- **Before reducing retention,** ensure you have forwarded audit logs to an external system (see [Monitoring and Alerting](monitoring-alerting.md) for syslog forwarding).
- **Set to `0`** to disable automatic deletion. This will cause the audit log table to grow indefinitely -- monitor disk usage accordingly.
- **For regulated environments,** consider setting a high retention value (e.g., 365 or more) and exporting logs to long-term storage (S3 Glacier, Azure Archive Storage).

### Manual Cleanup

To manually delete old audit log entries:

```sql
DELETE FROM audit_log
WHERE created_at < NOW() - INTERVAL '90 days';
```

To check the current size of the audit log:

```sql
SELECT COUNT(*) AS total_entries,
       pg_size_pretty(pg_total_relation_size('audit_log')) AS table_size,
       MIN(created_at) AS oldest_entry,
       MAX(created_at) AS newest_entry
FROM audit_log;
```

---

## Disaster Recovery Checklist

Use this checklist to prepare for and recover from a disaster scenario.

### Preparation (Do Now)

- [ ] Automated daily database backups are configured and running.
- [ ] Backup files are copied to at least one offsite location.
- [ ] Backup restoration has been tested on a staging environment.
- [ ] Backup monitoring is in place (alerts if a backup fails or is missing).
- [ ] `.env` file and secrets are stored in a secure vault (e.g., HashiCorp Vault, AWS Secrets Manager) -- not only on the server.
- [ ] `docker-compose.yml` and deployment configuration are in version control.
- [ ] Supabase project configuration is documented (auth providers, RLS policies).
- [ ] Runbook exists and is accessible to the operations team.

### Recovery Steps

1. **Provision infrastructure.** Set up a new server or container host with Docker and Docker Compose.

2. **Restore configuration.** Copy `docker-compose.yml`, `.env`, and any custom configuration files from version control or your secrets vault.

3. **Start the database container:**
   ```bash
   docker compose up -d oto-db
   ```

4. **Restore the database** from the latest backup following the [Restore Procedure](#restore-procedure) above.

5. **Verify data integrity** using the SQL checks above.

6. **Start remaining services:**
   ```bash
   docker compose up -d
   ```

7. **Verify the application.** Log in to the dashboard, confirm policies are present, check sandbox creation works.

8. **Restore sandbox data volumes** (if applicable).

9. **Update DNS** to point to the new server.

10. **Verify monitoring and alerting** are operational.

11. **Notify users** of any data loss window (time between last backup and the incident).

### Recovery Time Estimates

| Component | Estimated Recovery Time |
|-----------|------------------------|
| Infrastructure provisioning | 15 -- 30 minutes |
| Database restore (< 1 GB) | 5 -- 10 minutes |
| Database restore (1 -- 10 GB) | 10 -- 30 minutes |
| Application startup | 2 -- 5 minutes |
| DNS propagation | 5 -- 60 minutes |
| Sandbox pool warm-up | 2 -- 10 minutes (depends on `POOL_WARMUP_SIZE`) |

---

## Supabase-Hosted Deployments

If you are using Supabase's hosted platform (not self-hosted), backups are managed by Supabase:

- **Automatic backups:** Supabase Pro and Enterprise plans include daily automatic backups with point-in-time recovery.
- **Manual backups:** Use the Supabase dashboard under **Database > Backups** to create and download manual backups.
- **Exporting data:** Use `pg_dump` with the connection string from the Supabase dashboard under **Settings > Database** for full control over the backup format.

Regardless of the Supabase backup plan, it is recommended to maintain your own offsite backups as an additional layer of protection.
