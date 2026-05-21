# Audit Pro

Industrial stock counting system for high-speed, collaborative physical inventory audits in low-connectivity retail environments.

## Quick Start

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start development server
python manage.py runserver
```

Visit `http://localhost:8000/supervisor/` to create your first audit session.

## Architecture

### Supervisor Web App (`/supervisor/`)
- Create audit sessions
- Upload CSV/Excel stock lists with automatic column mapping
- Generate session PINs and QR codes for auditor onboarding
- Live monitor with HTMX polling (5s refresh)
- Variance console with color-coded discrepancies and recount triggers

### Auditor Mobile App (`/auditor/`)
- Anonymous join via 5-character session PIN
- Full catalog download to IndexedDB for offline operation
- Dark-first interface with thumb-zone ergonomics
- Blind-count workspace (expected quantities hidden)
- Persistent focus lock for Bluetooth scanner input
- Multisensory feedback (vibration + visual pulses)
- Fuzzy search for damaged/missing barcodes
- Unlisted item logging
- Automatic background sync when connectivity resumes

### API (`/api/`)
- Idempotent sync endpoint for offline log uploads
- Catalog retrieval for mobile hydration
- Recount task queue

## Data Model

Event-sourced: every count adjustment is an immutable `AuditLogEntry` with a UUID, timestamp, and delta value. Final counts are computed by summing all matching entries.

## Running with Docker

```bash
docker-compose up --build
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

```
DEBUG=True
SECRET_KEY=your-secret-key
DATABASE_URL=postgres://user:pass@host:5432/auditpro
TIMEZONE=Africa/Lagos
ALLOWED_HOSTS=localhost,127.0.0.1
```

## Testing

```bash
python manage.py test
```

## Production Deployment

1. Set `DEBUG=False`
2. Use PostgreSQL (`DATABASE_URL=postgres://...`)
3. Set a strong `SECRET_KEY`
4. Configure `ALLOWED_HOSTS`
5. Run `python manage.py collectstatic`
6. Use gunicorn or uwsgi as WSGI server
7. Serve behind nginx with HTTPS
