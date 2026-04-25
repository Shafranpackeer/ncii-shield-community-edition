# Expected Migration Output

When you run `docker compose up`, the backend service will automatically execute the migrations. Here's what you should see:

## Migration Log Output:

```
backend-1         | Waiting for PostgreSQL to be ready...
backend-1         | PostgreSQL is ready. Running migrations...
backend-1         | INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
backend-1         | INFO  [alembic.runtime.migration] Will assume transactional DDL.
backend-1         | INFO  [alembic.runtime.migration] Running upgrade  -> 001, Initial schema with all tables
backend-1         | Starting FastAPI application...
backend-1         | INFO:     Will watch for changes in these directories: ['/app']
backend-1         | INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
backend-1         | INFO:     Started reloader process [1] using StatReload
backend-1         | INFO:     Started server process [8]
backend-1         | INFO:     Waiting for application startup.
backend-1         | INFO:     Application startup complete.
```

## What the Migration Creates:

1. **5 Enum Types**
   - casestatus, identifiertype, targetstatus, actiontype, actionstatus

2. **8 Tables with Indexes**
   - All tables created with proper foreign key relationships
   - Indexes on frequently queried columns (phash, dhash, status, etc.)

3. **2 PostgreSQL Functions**
   - prevent_audit_log_modification() - Enforces append-only on audit_log
   - update_updated_at_column() - Auto-updates timestamps

4. **2 Database Triggers**
   - enforce_audit_log_append_only - Blocks UPDATE/DELETE on audit_log
   - update_targets_updated_at - Auto-updates targets.updated_at

## Verification Commands:

Check migration status:
```bash
docker compose exec backend alembic current
```

Expected output:
```
001 (head)
```

List all tables:
```bash
docker compose exec postgres psql -U ncii_user -d ncii_shield -c '\dt'
```

Expected output:
```
            List of relations
 Schema |       Name       | Type  |   Owner
--------+-----------------+-------+-----------
 public | actions         | table | ncii_user
 public | alembic_version | table | ncii_user
 public | audit_log       | table | ncii_user
 public | cases           | table | ncii_user
 public | contacts        | table | ncii_user
 public | identifiers     | table | ncii_user
 public | reference_hashes| table | ncii_user
 public | target_hashes   | table | ncii_user
 public | targets         | table | ncii_user
```

Test append-only trigger:
```bash
docker compose exec postgres psql -U ncii_user -d ncii_shield -c "INSERT INTO audit_log (entity_type, entity_id, action) VALUES ('test', 1, 'created');"
docker compose exec postgres psql -U ncii_user -d ncii_shield -c "UPDATE audit_log SET action = 'modified' WHERE id = 1;"
```

Expected error:
```
ERROR:  Updates not allowed on audit_log table
```