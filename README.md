# NCII Shield

Privacy-preserving system for discovering and requesting takedowns of non-consensual intimate images.

## Features

- **Zero-knowledge design** - Images are hashed client-side, never uploaded
- **Automated discovery** - Finds content across multiple search providers
- **Smart contact resolution** - Automatically identifies abuse contacts
- **Template-based notices** - Professional takedown requests with escalation
- **Full audit trail** - Complete history of all actions taken

## Tech Stack

- **Backend**: FastAPI + Celery + PostgreSQL + Redis
- **Frontend**: Next.js + TypeScript
- **Security**: Client-side hashing, zero-knowledge architecture

## Quick Start

```bash
# Setup
cp .env.example .env
docker compose up -d

# Access
Frontend: http://localhost:3001
API Docs: http://localhost:8001/docs
```

## Configuration

Configure providers via `.env` or the in-app Settings page:

```bash
RESEND_API_KEY=your-key
RESEND_FROM_EMAIL=NCII Shield <noreply@your-domain.example>
NOTICE_CONTACT_EMAIL=legal@your-domain.example
```

Email templates are in `backend/app/templates/emails/`.

## How It Works

1. **Create case** → Upload reference images (hashed client-side)
2. **Discovery** → Find matching content across search providers
3. **Confirmation** → Verify matches with visual evidence
4. **Contact resolution** → Identify or override abuse contacts
5. **Send notices** → Generate and send takedown requests
6. **Track & escalate** → Monitor responses and escalate as needed

## Development

Run tests:
```bash
docker compose exec backend pytest tests/ -v
```

Check migrations:
```bash
docker compose exec backend alembic check
```

Build frontend:
```bash
cd frontend && npm run build
```

## Updates

```bash
git pull
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

## Security

- Images never leave the browser - only hashes are uploaded
- Zero-knowledge architecture protects victim privacy
- Full audit trail of all system actions
- See [INTAKE_UI_DESCRIPTION.md](INTAKE_UI_DESCRIPTION.md) for technical details

## License

This is the community edition. See LICENSE file for details.

## Contributing

Pull requests welcome. Please ensure all tests pass before submitting.