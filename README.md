# NCII Shield Community Edition

NCII Shield Community Edition is a local-first admin console for authorized case work. It helps a single operator manage intake, discovery, confirmation, contact resolution, notice drafts, approvals, tracking, and recovery in one place.

This is the lite version of the project. It is intentionally small in scope: single operator, local/VPS deployment, and a clean path to update from GitHub when a newer build is available.

## What it does

- Stores cases in Postgres.
- Hashes reference images in the browser before upload.
- Runs discovery from configured search providers.
- Scrapes candidate pages for confirmation evidence.
- Resolves contacts from the target site, domain, and provider fallback.
- Generates templated notices for each escalation step.
- Tracks sent notices, delivery state, opens, bounces, and replies when configured.
- Keeps an audit trail and recovery path for restarts.

## What it does not do in v1

- No victim portal.
- No multi-admin workflow.
- No billing.
- No counter-notice automation.
- No regulator filing automation.
- No dark web crawling.

## Quick Start

1. Copy the environment template:

   ```bash
   cp .env.example .env
   ```

2. Fill in the services you want to use:

   - database
   - Redis
   - discovery API keys
   - Resend API key if you want outbound email

3. Start the stack:

   ```bash
   docker compose up -d --build
   ```

4. Run migrations:

   ```bash
   docker compose exec backend alembic upgrade head
   ```

5. Open the app:

   - Frontend: http://localhost:3001
   - Backend API: http://localhost:8001
   - API docs: http://localhost:8001/docs

## How To Use It

### 1. Create a case

Open the dashboard and create a new case.

### 2. Add intake data

Add the victim identifier, authorization note, identifiers, and any URLs already known.

### 3. Hash reference images

Drop reference images into the intake flow. Hashing happens in the browser first, and originals are discarded after hashing.

### 4. Run discovery

Discovery finds candidate URLs from the configured search providers and dork templates.

### 5. Review confirmation

Scrape-side evidence is matched against the stored hashes. Confirm or reject targets from the case page.

### 6. Resolve contacts

The app checks likely site pages and fallback contacts, then stores the best contact on the target.

### 7. Draft and send notices

The notice body comes from the template library. Approvals are still operator-gated.

### 8. Track what happens next

Sent notices, opens, bounces, replies, and escalation state show up on the case page and in the timeline.

## Settings

Use the Settings page to manage runtime values for:

- Resend
- Discovery provider keys

The UI shows links to the provider docs for each field.

## Templates

Notice templates live under `backend/app/templates/emails/`.

Each escalation step has its own folder and variant set, for example:

- `day0_initial`
- `day2_followup`
- `day3_hosting`
- `day5_registrar`
- `day7_final_warning`
- `day7_verification`

Each template includes:

- `subject.txt.j2`
- `body.txt.j2`

## Lite Version And Updates

This repository is the lite/community build.

- It is designed to be usable as-is for local or VPS deployments.
- Future improvements will land as updates in the GitHub repo.
- When you need the newest version, pull from GitHub and rebuild the stack.
- The next update should be there when you need it most.

Update steps:

```bash
git pull
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

## Verification

These are the checks that have been passing in the live stack:

```bash
docker compose exec backend pytest tests -q
docker compose exec backend alembic check
cd frontend && npm run build
```

## Notes

- Do not commit real provider keys.
- Keep `.env` local.
- The repo export is sanitized for GitHub and omits live secrets.
