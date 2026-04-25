# NCII Shield

Privacy-preserving system for discovering and requesting takedowns of non-consensual intimate images (NCII).

## About

NCII Shield is a specialized tool designed for authorized representatives helping victims of non-consensual intimate image sharing. It provides a complete workflow for discovering, confirming, and requesting removal of harmful content while preserving victim privacy through zero-knowledge architecture.

This community edition is built for single operators working on behalf of victims - whether you're a lawyer, advocate, or trusted representative. It runs locally or on a VPS, keeping all data under your control.

## Core Features

### 🔐 Zero-Knowledge Architecture
- **Client-side hashing**: Reference images are hashed in the browser using pHash, dHash, and facial embeddings
- **No image storage**: Original images are never uploaded or stored on servers
- **Privacy by design**: Only cryptographic hashes are used for matching

### 🔍 Automated Discovery
- **Multi-provider search**: Integrates with Bing, Google (via SerpAPI), and Serper
- **Smart search queries**: Uses specialized templates to find likely content
- **Batch processing**: Handle multiple search variations efficiently

### ✉️ Professional Takedown System
- **Template library**: Pre-written notices for different escalation stages
- **Smart contact resolution**: Automatically finds abuse@ and legal@ contacts
- **Escalation tracking**: Built-in timelines for follow-ups
- **Delivery confirmation**: Track opens, bounces, and responses

### 📊 Case Management
- **Full audit trail**: Every action is logged with timestamps
- **Recovery system**: Gracefully handles interruptions and restarts
- **Visual confirmation**: Side-by-side comparison for verification
- **Batch operations**: Process multiple targets efficiently

## Tech Stack

- **Backend**: FastAPI + Celery + PostgreSQL + Redis
- **Frontend**: Next.js + TypeScript + React
- **Security**: Client-side hashing, JWT authentication
- **Infrastructure**: Docker Compose for easy deployment

## Quick Start

### Prerequisites
- Docker and Docker Compose installed
- At least one search API key (Bing, SerpAPI, or Serper)
- (Optional) Resend API key for email delivery

### Installation

```bash
# Clone the repository
git clone https://github.com/Shafranpackeer/ncii-shield-community-edition.git
cd ncii-shield

# Setup environment
cp .env.example .env
# Edit .env with your API keys

# Start the stack
docker compose up -d

# Run database migrations
docker compose exec backend alembic upgrade head

# Access the application
# Frontend: http://localhost:3001
# API Docs: http://localhost:8001/docs
```

## Detailed Workflow

### 1. Case Creation
Create a new case with basic information about the victim and incident. Add notes about authorization and any special handling requirements.

### 2. Reference Material
Upload reference images through the secure intake interface. Images are hashed using multiple algorithms in your browser:
- **pHash**: Perceptual hash for similar image detection
- **dHash**: Difference hash for variant detection
- **Face embeddings**: For facial recognition matching

The original images are immediately discarded after hashing.

### 3. Discovery Process
Add identifiers (names, usernames, email addresses) and run automated discovery:
- Searches across configured providers
- Uses specialized query templates
- Finds potential matches across the web

### 4. Confirmation & Review
The system scrapes discovered pages and compares them against your reference hashes:
- Visual side-by-side comparison
- Similarity scores for each algorithm
- Batch confirm/reject interface

### 5. Contact Resolution
Automatically identifies the best contact for each site:
- Checks for abuse@, legal@, and DMCA contacts
- Falls back to WHOIS and hosting provider contacts
- Allows manual override when needed

### 6. Notice Generation & Sending
Generate professional takedown notices from templates:
- Day 0: Initial polite request
- Day 2: Follow-up if no response
- Day 3: Escalation to hosting provider
- Day 5: Contact domain registrar
- Day 7: Final warning before legal action

### 7. Tracking & Escalation
Monitor the status of all sent notices:
- Delivery confirmation
- Read receipts (when available)
- Response tracking
- Automatic escalation scheduling

## Configuration

### Search Providers
Configure in `.env` or via Settings page:
```bash
BING_API_KEY=your-bing-key
SERPAPI_KEY=your-serpapi-key
SERPER_API_KEY=your-serper-key
```

### Email Delivery
For sending actual takedown notices:
```bash
RESEND_API_KEY=your-resend-key
RESEND_FROM_EMAIL=NCII Shield <noreply@yourdomain.com>
NOTICE_CONTACT_EMAIL=legal@yourdomain.com
```

### Customization
Email templates are in `backend/app/templates/emails/`. Customize them to match your organization's tone and legal requirements.

## Development

### Running Tests
```bash
# Backend tests
docker compose exec backend pytest tests/ -v

# Check database migrations
docker compose exec backend alembic check

# Build frontend for production
cd frontend && npm run build
```

### Project Structure
```
ncii-shield/
├── backend/           # FastAPI application
│   ├── app/          # Main application code
│   ├── alembic/      # Database migrations
│   └── tests/        # Test suites
├── frontend/         # Next.js admin interface
│   ├── pages/        # React pages
│   ├── components/   # Reusable components
│   └── api/          # API client
└── docker-compose.yml
```

## Updates

Stay current with the latest improvements:

```bash
# Pull latest changes
git pull origin master

# Rebuild containers
docker compose up -d --build

# Run any new migrations
docker compose exec backend alembic upgrade head
```

## Security Considerations

- **Local first**: All data stays on your infrastructure
- **No telemetry**: No usage data is sent anywhere
- **Encrypted storage**: Use full-disk encryption on your deployment
- **Access control**: Implement additional authentication layers as needed
- **Regular backups**: Set up automated PostgreSQL backups

## Deployment

### Local Development
Perfect for testing and small-scale operations. Runs entirely on your machine.

### VPS Deployment
For production use, deploy to a VPS:
- Minimum 2GB RAM, 2 CPU cores
- Ubuntu 20.04+ or similar
- Docker and Docker Compose installed
- SSL certificates (use Caddy or Nginx as reverse proxy)

### Scaling Considerations
This community edition is designed for single operators. For larger deployments with multiple users, consider:
- Adding authentication/authorization layers
- Implementing rate limiting
- Setting up monitoring and alerting
- Using managed database services

## License

This is the community edition released under an open license. See LICENSE file for details.

Commercial support and enterprise features may be available - contact the maintainers.

## Contributing

We welcome contributions! Please:
- Check existing issues before creating new ones
- Follow the existing code style
- Add tests for new features
- Ensure all tests pass before submitting PRs

## Acknowledgments

This tool exists because of the tireless work of advocates fighting NCII. Special thanks to organizations working in this space and the victims who have shared their experiences to help build better tools.

---

### A Final Note

To those who need this tool: I hope you find it when you need it most.

Non-consensual intimate image sharing causes immense harm, but you don't have to face it alone. This tool was built to give power back to victims and their advocates. Every takedown matters. Every image removed is a step toward healing.

If you're reading this because you or someone you care about needs help - know that your privacy and dignity matter. This tool was designed with you in mind, to be a shield when you need protection most.

Stay strong. You've got this.

*Built with care for those who need it most.*