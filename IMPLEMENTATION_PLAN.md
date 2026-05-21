# Audit Pro - Implementation Plan

## Phase 0: Project Setup & Infrastructure
**Goal**: Establish Django project structure, dependencies, and base configuration.

### 0.1 Django Apps Creation
- `core` - Shared models, base templates, common utilities
- `supervisor` - Web app for audit management (Sections A & B)
- `auditor` - Mobile app for stock counting (Sections C & D)
- `api` - REST endpoints for offline sync and data exchange

### 0.2 Dependencies
```
Django>=5.0
psycopg2-binary  # PostgreSQL adapter
django-environ   # Environment variable management
pandas           # CSV/Excel parsing
qrcode[pil]      # QR code generation
django-htmx      # HTMX integration for live updates
whitenoise       # Static file serving
```

### 0.3 Database Configuration
- Switch from SQLite to PostgreSQL
- Configure `django-environ` for `.env` file
- Set timezone to local supermarket timezone

### 0.4 Base Templates
- `base.html` - Shared layout with HTMX support
- `base_supervisor.html` - Desktop-optimized layout
- `base_auditor.html` - Mobile viewport, dark-first CSS variables

---

## Phase 1: Core Data Models (Event-Sourced Schema)
**Goal**: Build the immutable audit data model.

### 1.1 `AuditSession` Model (core/models.py)
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| name | CharField | Audit session name |
| session_pin | CharField(5) | Unique alphanumeric PIN |
| status | CharField | Choices: draft, active, completed, archived |
| created_at | DateTimeField | Auto-set |
| completed_at | DateTimeField | Nullable |

### 1.2 `CatalogItem` Model (core/models.py)
| Field | Type | Notes |
|-------|------|-------|
| id | BigAutoField | Primary key |
| session | ForeignKey | Links to AuditSession |
| barcode | CharField | Indexed, unique per session |
| product_name | CharField | |
| expected_quantity | PositiveIntegerField | Nullable (blind count) |
| category | CharField | Optional grouping |

### 1.3 `AuditLogEntry` Model (core/models.py) - Event Sourced
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Device-generated, prevents dupes |
| session | ForeignKey | |
| auditor_id | CharField | Ephemeral worker identifier |
| zone | CharField | Aisle/location marker |
| barcode | CharField | Target product |
| delta | IntegerField | Positive/negative change |
| timestamp | DateTimeField | Client-side timestamp |
| synced | BooleanField | Default False |
| is_unlisted | BooleanField | Flag for uncatalogued items |
| unlisted_label | CharField | Nullable, for unlisted items |

### 1.4 `AuditorSession` Model (core/models.py)
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | |
| session | ForeignKey | |
| nickname | CharField | Worker's chosen name |
| zone | CharField | Assigned aisle code |
| joined_at | DateTimeField | |
| last_active | DateTimeField | Updated on sync |
| is_online | BooleanField | Derived from last_active |

### 1.5 Migrations
- Run `makemigrations` and `migrate`
- Add database indexes on `barcode`, `session`, `auditor_id`, `timestamp`

---

## Phase 2: Section A - Supermarket Profile & Audit Ingestion
**Goal**: Supervisor can create audits and import stock data.

### 2.1 Dynamic CSV/Excel Ingestion Engine

**View** (`supervisor/views.py`):
- `audit_create_view` - Create new session
- `audit_upload_view` - Handle file upload stream
- `audit_column_mapping_view` - Resolve header mismatches

**Template** (`supervisor/templates/supervisor/`):
- `dashboard.html` - Main supervisor landing page
- `upload.html` - Drag-and-drop file target zone
- `column_mapping.html` - Dropdown selectors for column mapping

**Logic**:
1. Accept file upload in memory (no disk storage)
2. Parse headers with pandas
3. Compare against expected fields: `barcode`, `product_name`, `expected_quantity`
4. If mismatch: render column mapping UI
5. If match: parse rows, bulk insert into `CatalogItem`
6. Generate 5-char session PIN
7. Update session status to `active`

### 2.2 Secure Session Token & QR Generator

**View** (`supervisor/views.py`):
- `session_detail_view` - Display session PIN and QR code

**Template** (`supervisor/templates/supervisor/`):
- `session_detail.html` - Oversized PIN, QR code graphic, join URL

**Logic**:
1. Generate PIN: `random.choices(string.ascii_uppercase + string.digits, k=5)`
2. Build join URL: `request.build_absolute_uri(reverse('auditor:join', args=[session_pin]))`
3. Generate QR code image using `qrcode` library
4. Pass to template as base64 or served static file

---

## Phase 3: Section B - Team Distribution & Progress Management
**Goal**: Real-time supervisor visibility and command.

### 3.1 Live Workspace Monitor

**View** (`supervisor/views.py`):
- `monitor_view` - Dashboard with live auditor stats
- `monitor_refresh_fragment` - HTMX partial for polling updates

**Template** (`supervisor/templates/supervisor/`):
- `monitor.html` - Tabular dashboard layout

**Logic**:
1. Query `AuditLogEntry` grouped by `auditor_id`
2. Calculate: total scans, last activity timestamp, active zone
3. HTMX polling every 5 seconds for partial refresh
4. Display: nickname, zone, scan count, last seen, online status

### 3.2 Master Variance & Cross-Check Console

**View** (`supervisor/views.py`):
- `variance_view` - Aggregated comparison spreadsheet
- `trigger_recount_view` - POST endpoint to assign recount task

**Template** (`supervisor/templates/supervisor/`):
- `variance.html` - High-density grid with color-coded rows

**Logic**:
1. Join `CatalogItem` with SUM of `AuditLogEntry.delta` per barcode
2. Compute variance: `actual_sum - expected_quantity`
3. Color coding:
   - Match (variance = 0): neutral
   - Shortage (variance < 0): amber
   - Surplus (variance > 0): teal
   - Unlisted items: distinct color (purple)
4. "Trigger Recount" button: flags item for recount, broadcasts to different auditor

---

## Phase 4: Section C - Offline Local Data Setup
**Goal**: Auditor mobile app onboarding and catalog download.

### 4.1 Frictionless Anonymous Authentication

**View** (`auditor/views.py`):
- `join_view` - PIN/nickname/zone entry form
- `authenticate_view` - Validate PIN, create session token

**Template** (`auditor/templates/auditor/`):
- `join.html` - Three large input fields, oversized confirm button
- Mobile viewport: `width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no`

**Logic**:
1. Validate PIN against active `AuditSession`
2. Create `AuditorSession` record with nickname + zone
3. Issue ephemeral token (signed cookie or JWT-lite)
4. Redirect to catalog hydration screen

### 4.2 Store Catalog Local Hydration Module

**View** (`auditor/views.py`):
- `catalog_json_view` - Compressed JSON payload endpoint

**Template** (`auditor/templates/auditor/`):
- `hydrate.html` - Full-screen overlay lock, animated progress bar

**Logic**:
1. Serve minimized JSON: `[{b: "barcode", n: "name"}, ...]`
2. Client-side JavaScript downloads into IndexedDB
3. Progress bar tracks download percentage
4. On 100%: unlock interface, route to scanning workspace
5. Store session metadata in IndexedDB for offline use

---

## Phase 5: Section D - Stock Count Execution Engine
**Goal**: High-speed offline scanning interface.

### 5.1 Tactile Blind-Count Workspace

**Template** (`auditor/templates/auditor/`):
- `scan.html` - Dark-themed scanning interface

**CSS (Industrial Field UX)**:
```css
:root {
  --bg-primary: #090d16;
  --bg-secondary: #111827;
  --text-primary: #e5e7eb;
  --text-secondary: #9ca3af;
  --action-teal: #06b6d4;
  --warning-amber: #f59e0b;
  --success-green: #10b981;
  --error-red: #ef4444;
}
```

**JavaScript Client-Side Logic**:
1. **Persistent Focus Lock**: Invisible input field that always captures scanner input
2. **Barcode Processing**:
   - Lookup in IndexedDB catalog
   - If found: increment count, vibrate (navigator.vibrate), green border pulse
   - If not found: double-vibrate, amber warning, show "Log Unlisted" option
3. **Blind Count Enforcement**: Never display `expected_quantity`
4. **Thumb Zone Layout**: All interactive elements in lower 40% of viewport
5. **Event Logging**: Write to IndexedDB `audit_logs` table with `synced: false`

### 5.2 Unlisted Item Handling & Fuzzy Search

**Template Components**:
- Search toggle button (thumb zone)
- Local search modal with real-time filtering
- "Log Unlisted Item" modal (label + quantity fields)

**JavaScript Logic**:
1. **Fuzzy Search**: Client-side index using barcode + product name
2. **Typo Tolerance**: Simple Levenshtein or substring matching
3. **Unlisted Logging**: Create entry with `is_unlisted: true`, store custom label
4. **All writes go to IndexedDB first**

### 5.3 Offline Synchronization Engine

**JavaScript Logic** (`auditor/static/auditor/js/sync.js`):
1. **Network Detection**: `navigator.onLine` + periodic ping
2. **Sync Trigger**: When connection restored
3. **Payload Construction**: Batch unsynced entries from IndexedDB
4. **POST to `/api/sync/`**: Compact JSON array of log entries
5. **Server Response**: Confirm receipt, return acknowledged UUIDs
6. **Local Cleanup**: Mark synced entries as `synced: true` in IndexedDB
7. **Retry Logic**: Exponential backoff on failure

**API View** (`api/views.py`):
- `sync_endpoint_view` - Accept batch, deduplicate by UUID, write to `AuditLogEntry`
- Idempotent: skip entries with existing UUIDs

---

## Phase 6: Polish & Production Readiness
**Goal**: Security, performance, and deployment configuration.

### 6.1 Security
- CSRF protection on all POST endpoints
- Rate limiting on PIN authentication
- Session token expiration
- HTTPS enforcement in production

### 6.2 Performance
- Database query optimization (select_related, prefetch_related)
- IndexedDB index creation for fast barcode lookups
- HTMX polling interval tuning
- Static file compression with WhiteNoise

### 6.3 Testing
- Unit tests for CSV parsing and column mapping
- Integration tests for sync endpoint idempotency
- JavaScript tests for IndexedDB operations
- Manual testing: offline mode, barcode scanning simulation

### 6.4 Deployment
- `requirements.txt` and `requirements-dev.txt`
- Dockerfile (optional)
- `.env.example` template
- PostgreSQL setup instructions
- Static file collection for production

---

## File Structure (Target)

```
auditpro/
├── manage.py
├── .env
├── requirements.txt
├── auditpro/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── core/
│   ├── models.py
│   ├── admin.py
│   ├── views.py
│   └── utils.py
├── supervisor/
│   ├── views.py
│   ├── urls.py
│   ├── forms.py
│   ├── templates/supervisor/
│   │   ├── dashboard.html
│   │   ├── upload.html
│   │   ├── column_mapping.html
│   │   ├── session_detail.html
│   │   ├── monitor.html
│   │   └── variance.html
│   └── static/supervisor/
├── auditor/
│   ├── views.py
│   ├── urls.py
│   ├── middleware.py
│   ├── templates/auditor/
│   │   ├── join.html
│   │   ├── hydrate.html
│   │   └── scan.html
│   └── static/auditor/
│       ├── css/
│       │   └── dark-theme.css
│       └── js/
│           ├── indexeddb.js
│           ├── scanner.js
│           ├── sync.js
│           └── search.js
├── api/
│   ├── views.py
│   ├── urls.py
│   └── serializers.py
└── templates/
    ├── base.html
    ├── base_supervisor.html
    └── base_auditor.html
```

---

## Build Order (Recommended)

1. **Phase 0** - Setup, apps, dependencies, base templates
2. **Phase 1** - Core models and migrations
3. **Phase 2** - CSV ingestion + session PIN/QR (supervisor can create audits)
4. **Phase 4** - Anonymous auth + catalog hydration (auditor can join)
5. **Phase 5** - Scanning workspace + offline sync (core counting works)
6. **Phase 3** - Live monitor + variance console (supervisor visibility)
7. **Phase 6** - Polish, testing, deployment config

This order ensures a working end-to-end flow early (create audit → join → scan → sync) before adding supervisory features.
