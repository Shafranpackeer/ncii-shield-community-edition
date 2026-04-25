# NCII Shield v1

Privacy-preserving system for discovering and requesting takedowns of non-consensual intimate images.

## Architecture

- **Backend**: FastAPI + Celery + Redis (AOF) + PostgreSQL
- **Frontend**: Next.js admin console
- **Security**: zero-knowledge reference-image design with client-side hashing

## Data Model

The system implements:

- `cases` - main case tracking
- `reference_hashes` - client-side hashed reference images: pHash, dHash, face embeddings
- `identifiers` - names, handles, aliases, emails, phones for discovery
- `targets` - discovered URLs and lifecycle status
- `target_hashes` - hashes computed from scraped candidate images
- `review_thumbnails` - temporary thumbnails from scraped-side evidence only
- `contacts` - extracted or manually overridden abuse contacts
- `actions` - outbound action intents, drafts, approvals, sends, and escalation rungs
- `audit_log` - append-only audit trail with trigger enforcement

## Quick Start

1. Copy environment variables:

   ```bash
   cp .env.example .env
   ```

2. Start the stack:

   ```bash
   docker compose up -d
   ```

3. Check migration status:

   ```bash
   docker compose exec backend alembic current
   docker compose exec backend alembic check
   ```

4. Access the app:

   - Frontend: http://localhost:3001
   - Backend API: http://localhost:8001
   - API Docs: http://localhost:8001/docs

## Provider Configuration

Do not commit real provider keys. Put them in `.env` or set them from the in-app Settings page.

```bash
RESEND_API_KEY=
RESEND_FROM_EMAIL=NCII Shield <noreply@your-domain.example>
NOTICE_CONTACT_EMAIL=
NOTICE_WEBSITE=https://your-domain.example
```

If `NOTICE_WEBSITE` is left blank, the backend derives the footer domain from `RESEND_FROM_EMAIL` automatically. If neither is present, the notice footer stays white-label and omits the website line.

The Settings page lets you edit runtime values for:

- Resend
- White-label notice fields
- Discovery provider keys

Each field includes a link to the provider's official setup page.

Template files live under `backend/app/templates/emails/`, grouped by escalation step and variant. Each template has a `subject.txt.j2` and `body.txt.j2` file.

## Workflow

1. Create a case in the admin UI.
2. Hash reference images in the browser; originals are discarded and never sent to the server.
3. Add identifiers and manual URLs.
4. Run discovery and review discovered targets.
5. Run confirmation to scrape candidate pages and compare scraped images against stored hashes.
6. Review confirmation evidence and confirm or reject targets.
7. Resolve contacts or add a manual contact override.
8. Generate a draft takedown notice from the template library.
9. Admin approves or rejects every outbound action. Approval sends through Resend when configured; otherwise the local outbox records delivery metadata.
10. Escalation rungs are scheduled in the database and recovered by the recovery worker.
11. Use the timeline tab for audit history, kill switch to suspend a case, or resolve the case.

## Build Status

- Step 1: Data model and Alembic migrations complete.
- Step 2: Intake and client-side hashing complete.
- Step 3: Persistence/recovery skeleton complete.
- Step 4: Discovery module and review queue complete for local/VPS MVP.
- Step 5: Server-side hashing and confirmation complete for local/VPS MVP.
- Step 6: Contact resolution complete with deterministic fallback and manual override.
- Step 7: Email generation complete with template-only rendering.
- Step 8: Send/track complete with Resend webhook tracking and local fallback.
- Step 9: Escalation scheduler complete.
- Step 10: Admin UI case lifecycle screens complete.
- Step 11: Verification complete.

## Verification

```bash
docker compose exec backend pytest tests/ -v --tb=short
docker compose exec backend alembic check
cd frontend && npm run build
```

Current verified status:

- Backend tests: `45 passed, 1 skipped`
- Alembic drift check: clean
- Frontend production build: passes

The skipped backend test is the opt-in worker crash process test. Run it only in an environment with reliable standalone Celery worker signal handling:

```bash
RUN_CELERY_CRASH_TEST=true docker compose exec backend pytest tests/integration/test_recovery.py::TestCeleryWorkerRecovery::test_worker_crash_recovery -v
```

## Updating

When you pull a newer GitHub version:

1. `git pull`
2. `docker compose up -d --build`
3. `docker compose exec backend alembic upgrade head`
4. Refresh the browser and check the footer for the current version/update note

## Client-Side Hashing

Reference images are hashed client-side in the admin browser before upload. The server stores only pHash, dHash, face embedding, label, and timestamp. See [INTAKE_UI_DESCRIPTION.md](INTAKE_UI_DESCRIPTION.md) for implementation details.
