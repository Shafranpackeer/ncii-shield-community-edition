# NCII Shield v1 - Project Structure

## File Tree

```
ncii-shield/
├── docker-compose.yml          # Main orchestration file
├── .env.example               # Environment template
├── README.md                  # Project documentation
├── test_setup.sh             # Setup verification script
│
├── backend/
│   ├── Dockerfile            # Backend container config
│   ├── requirements.txt      # Python dependencies
│   ├── alembic.ini          # Alembic configuration
│   ├── startup.sh           # Container startup script
│   ├── create_migration.py  # Migration helper
│   │
│   ├── alembic/
│   │   ├── env.py          # Alembic environment
│   │   ├── script.py.mako  # Migration template
│   │   └── versions/
│   │       └── 001_initial_schema.py  # Initial migration
│   │
│   └── app/
│       ├── __init__.py
│       ├── main.py         # FastAPI application
│       ├── celery_app.py   # Celery configuration
│       │
│       ├── db/
│       │   ├── __init__.py
│       │   └── base.py     # Database configuration
│       │
│       └── models/
│           ├── __init__.py
│           ├── case.py           # Case model
│           ├── reference_hash.py # Reference hash model
│           ├── identifier.py     # Identifier model
│           ├── target.py         # Target model
│           ├── target_hash.py    # Target hash model
│           ├── contact.py        # Contact model
│           ├── action.py         # Action model (append-only)
│           └── audit_log.py      # Audit log model (append-only)
│
├── frontend/
│   ├── Dockerfile          # Frontend container config
│   ├── package.json        # Node dependencies
│   ├── next.config.js      # Next.js configuration
│   ├── tsconfig.json       # TypeScript configuration
│   └── pages/
│       └── index.tsx       # Main page placeholder
│
└── redis/                  # Redis AOF persistence directory (created at runtime)
```

## Database Schema

### Tables Created in Migration 001:

1. **cases**
   - id, victim_id, status (active/resolved/suspended)
   - created_at, authorization_doc

2. **reference_hashes**
   - id, case_id, phash, dhash, face_embedding
   - label, created_at
   - Indexes on phash and dhash

3. **identifiers**
   - id, case_id, type (name/handle/alias/email/phone)
   - value, created_at
   - Index on value

4. **targets**
   - id, case_id, url (unique), status
   - discovery_source, confidence_score
   - next_action_at, created_at, updated_at
   - Indexes on status and next_action_at

5. **target_hashes**
   - id, target_id, image_url
   - phash, dhash, face_embedding
   - match_against_ref_id, match_score, created_at
   - Indexes on phash and dhash

6. **contacts**
   - id, target_id, email
   - method_found, confidence, created_at

7. **actions** (append-only)
   - id, target_id, type, payload, status
   - scheduled_at, executed_at, created_at
   - created_by, error_message
   - Indexes on status and scheduled_at

8. **audit_log** (append-only)
   - id, entity_type, entity_id, action
   - old_value, new_value, user_id
   - ip_address, user_agent, created_at
   - Indexes on entity_type, entity_id, created_at

### Database Triggers:

1. **enforce_audit_log_append_only**
   - Prevents UPDATE and DELETE operations on audit_log table

2. **update_targets_updated_at**
   - Automatically updates the updated_at timestamp on targets table

### Enum Types:
- casestatus: active, resolved, suspended
- identifiertype: name, handle, alias, email, phone
- targetstatus: discovered, confirmed, false_positive, contacted, removed, escalated, resolved
- actiontype: email_initial, email_followup, email_hosting, email_registrar, manual_escalation, check_removal
- actionstatus: pending, approved, rejected, scheduled, executing, completed, failed

## Services in Docker Compose:

1. **postgres** - PostgreSQL 15 database
2. **redis** - Redis 7 with AOF persistence
3. **backend** - FastAPI application
4. **celery-worker** - Background task processor
5. **celery-beat** - Scheduled task runner
6. **frontend** - Next.js admin console

## Key Features Implemented:

✅ Zero-knowledge design (reference hashes stored, not images)
✅ Append-only audit trail with database-level enforcement
✅ Comprehensive data model for case tracking
✅ Docker Compose orchestration
✅ Automatic migration on startup
✅ Redis AOF persistence for recovery
✅ Health check endpoints

## Next Steps:

Ready to proceed with Step 2: Intake + client-side hashing implementation