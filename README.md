# Abnormal File Vault

A secure file hosting application with per-user deduplication, validated search & filtering, and per-user API rate limits and storage quotas.

- **Backend:** Django 4.2 + Django REST Framework, SQLite, local file storage
- **Frontend:** React 19 + Vite + Tailwind CSS v3 + [shadcn/ui](https://ui.shadcn.com) (Radix UI, lucide icons)

---

## 🚀 Quick Start

### Prerequisites
- Python **3.11** (the pinned Django/Pillow versions target 3.11)
- Node.js **20+**
- (Optional) Docker & Docker Compose

### Run locally without Docker

Use two terminals: one for the backend, one for the frontend. In IntelliJ, open the Terminal tool window (`Alt+F12`) and use two tabs.

**Terminal 1: backend**

```powershell
# Windows (PowerShell)
cd backend
py -3.11 -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # allows the venv activate script
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

```bash
# macOS / Linux
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

API: **http://localhost:8000/api/files/**

**Terminal 2: frontend**

```bash
cd frontend
npm install
npm run dev
```

App: **http://localhost:3000**

The frontend calls `http://localhost:8000/api` by default. To point it elsewhere, set `VITE_API_URL` (or `REACT_APP_API_URL`) before `npm run dev`.

### Run with Docker

```bash
docker-compose up --build
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000

---

## ✨ Features

### 1. File deduplication
- Every upload is hashed with **SHA-256**, read in chunks so large files never sit in memory.
- **Per-user deduplication:** when a user uploads content they already have, it becomes a *reference* row (with its own name and upload time) pointing at the *original*. The bytes are stored once.
- **Not across users, on purpose:** deduplicating across users would reveal to user B that user A already holds a given file (a cross-tenant information leak).
- **Safe deletes:**
  - Deleting a reference keeps the stored file.
  - Deleting an original promotes the oldest reference to be the new original, so every other copy keeps working.
  - The file on disk is removed only when its last copy is deleted, and only after the database transaction commits.
- **Race-safe:** a partial unique index on `(user_id, file_hash) WHERE is_reference = false` stops two simultaneous identical uploads from both becoming originals; the losing upload retries as a reference.
- Stats report logical vs. physical bytes and the percentage saved.

### 2. Search & filtering
- Search by name (case-insensitive), file type, size range, upload date range, "duplicates only", plus sort order.
- Query parameters are validated by a DRF serializer (`files/filters.py`), so bad input returns `400` with a per-field message instead of a `500`.
- Composite indexes lead with `user_id`, since every query is scoped to one user: `(user_id, -uploaded_at)`, `(user_id, original_filename)`, `(user_id, file_type)`, `(user_id, size)`, `(user_id, is_reference)`.
- The file list uses a constant number of queries (`select_related` avoids N+1). Stats come from a single aggregate query.
- `icontains` with a leading wildcard can't use a B-tree index. On PostgreSQL, add a `pg_trgm` GIN index on `name` for large datasets.

### 3. Call & storage limits (per user)
- **User identification:** every request carries a `UserId` header, checked by a DRF authentication class (`files/authentication.py`).
- **Rate limiting** (`files/throttling.py`):
  - A sliding-window counter per user (default **2 calls/second**), applied to every endpoint as a DRF throttle.
  - It avoids the double burst a fixed window allows at window boundaries, and rejected calls don't use up the allowance.
- **Storage quota** (`files/services.py`):
  - Each user can store up to **10 MB** by default. Only bytes actually stored count, so duplicates are free.
  - The quota is checked before anything is written to disk, and again inside the database transaction, so two simultaneous uploads can't both slip under the limit.
- Limits are configurable with environment variables (see [Limits](#limits)).
- Counters live in Django's cache. With several server processes, point `CACHES` at Redis so they share one counter.

### 4. Frontend (shadcn/ui)
- **Dashboard:**
  - Cards for file count, duplicates, space saved and storage used.
  - A quota bar that turns amber at 75% and red at 90%.
- **Upload:** drag-and-drop (several files at once), with toasts for uploaded, duplicate, and quota-exceeded.
- **Filters:** sidebar with name, type, size (KB), date range, duplicates-only and sort order. Results update as you type (debounced).
- **File table:**
  - Badges mark duplicates and shared copies.
  - Download, and delete with a confirmation dialog that explains what happens to other copies.
  - Pagination.
- **User switcher:** sets the `UserId` header. When the API answers `429 Call Limit Reached`, the app waits and retries automatically.
- **Responsive:** less important columns hide on small screens.
- **No native binaries:**
  - Rollup and esbuild run as their official WebAssembly builds (npm `overrides` in `frontend/package.json`), and Tailwind v3 is pure JavaScript.
  - So the app also runs on Windows machines where Smart App Control blocks unsigned `.node`/`.exe` files.
- Add more shadcn components with `npx shadcn@latest add <component>` (configured in `frontend/components.json`).

---

## 📚 API

Every request must send a **`UserId` header** (e.g. `UserId: user1`). Users see only their own files; anyone else's IDs return `404`. Requests without the header get `401 {"error": "UserId header is required"}`.

| Method & path | Description |
|---|---|
| `GET /api/files/` | List your files (paginated; filters below) |
| `POST /api/files/` | Upload a file (multipart field `file`); returns `201` with the file object plus `is_duplicate` |
| `GET /api/files/{id}/` | File details |
| `GET /api/files/{id}/download/` | Download a file |
| `DELETE /api/files/{id}/` | Delete a file (shared copies handled safely) |
| `GET /api/files/storage_stats/` (alias `/stats/`) | Your storage, savings and quota |
| `GET /api/files/file_types/` | Distinct MIME types among your files |

### Query parameters for `GET /api/files/`

All optional and combinable. Invalid values return `400` with a per-field message.

- `search`: case-insensitive partial match on the filename
- `file_type`: MIME type, e.g. `application/pdf`. Also accepts a list (`image/png,application/pdf`) or a category (`image`)
- `min_size` / `max_size`: size range in bytes (inclusive)
- `start_date` / `end_date`: ISO 8601 with timezone, e.g. `2025-01-31T10:00:00Z` or `2025-01-31T15:30:00+05:30` (URL-encode `+` as `%2B`). A bare date also works; a date-only `end_date` includes that whole day
- `duplicates_only`: `true` to show only content uploaded more than once
- `ordering`: `uploaded_at`, `original_filename`, `size`, `file_type`; prefix `-` for descending
- `page`: page number (50 files per page)

Older parameter names are still accepted: `mime_type`, `date_from`, `date_to`.

Example:

```bash
curl -H "UserId: user1" "http://localhost:8000/api/files/?search=report&file_type=application/pdf&min_size=1000&start_date=2025-01-01T00:00:00Z"
```

### Response format

`GET /api/files/` (200 OK):

```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "file": "http://localhost:8000/api/files/1/download/",
      "original_filename": "report.pdf",
      "file_type": "application/pdf",
      "size": 1048576,
      "uploaded_at": "2025-01-31T10:00:00Z",
      "user_id": "user1",
      "file_hash": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
      "reference_count": 2,
      "is_reference": false,
      "original_file": null
    }
  ]
}
```

- `reference_count`: how many uploads share this content (the original included). A reference reports its original's count.
- `is_reference` / `original_file`: whether this upload is a duplicate, and the ID of the upload it shares storage with.
- `file`: download URL. Send the same `UserId` header to fetch it.

`GET /api/files/storage_stats/` (200 OK):

```json
{
  "user_id": "user1",
  "total_storage_used": 1048576,
  "original_storage_used": 2097152,
  "storage_savings": 1048576,
  "savings_percentage": 50.0
}
```

It also returns `storage_limit`, `storage_remaining`, `total_files`, `unique_files` and `duplicate_entries`.

### Limits

| Limit | Default | Environment variable | When exceeded |
|---|---|---|---|
| API calls per user | 2 per second | `RATE_LIMIT_CALLS`, `RATE_LIMIT_WINDOW_SECONDS` | `429 {"error": "Call Limit Reached"}` + `Retry-After` |
| Storage per user | 10 MB | `USER_STORAGE_LIMIT_BYTES` | `429 {"error": "Storage Quota Exceeded"}` |

Example (PowerShell): `$env:RATE_LIMIT_CALLS="20"; python manage.py runserver`

---

## 💾 Where files are stored

| What | Where |
|---|---|
| Uploaded file contents | `backend/media/uploads/`, under random names (`<uuid>.<ext>`) so user-supplied filenames never touch the disk |
| File metadata (owner, name, size, type, hash, which stored file it uses, duplicate flag) | SQLite database `backend/db.sqlite3`, table `files_filemetadata` |
| With Docker | Database: `backend/db.sqlite3`. Uploads: the `media_files` Docker volume |

A duplicate upload adds a database row pointing at the existing stored file, so nothing new is written to disk. The `media/` folder is **not** served publicly: downloads go through `/api/files/{id}/download/`, which checks ownership.

To list which stored file belongs to which upload:

```bash
cd backend
python manage.py shell -c "from files.models import FileMetadata as F; [print(f.user_id, '|', f.original_filename, '->', f.file_path, '(duplicate)' if f.is_reference else '') for f in F.objects.all()]"
```

---

## 🧪 Tests

```bash
cd backend
python manage.py test files
# or with Docker
docker-compose run --rm backend python manage.py test files
```

52 tests cover:
- the API contract (exact response fields and pagination shape)
- deduplication, and deleting files that share stored content
- search & filters, including invalid input
- the rate limit (with a controllable clock)
- the storage quota
- per-user isolation

---

## 🗂️ Project structure

```
backend/
  filevault/            Django settings and URLs
  files/
    models.py           FileMetadata (originals and duplicate references)
    services.py         upload / dedup / delete / stats logic
    filters.py          validated search & filter parameters
    authentication.py   UserId header authentication
    throttling.py       per-user sliding-window rate limit
    exceptions.py       consistent {"error": "..."} responses
    views.py            REST API (DRF ViewSet)
    migrations/
    tests/
frontend/
  src/
    components/ui/      shadcn/ui components
    components/         StatsPanel, FileUpload, FileFilters, FileList
    services/api.js     API client (UserId header, rate-limit retry)
    lib/                cn() helper, formatting
  tailwind.config.js, postcss.config.js, vite.config.js, components.json
docker-compose.yml
```

---

## 📦 Creating the submission package

```bash
./create_submission.sh            # macOS / Linux / Git Bash on Windows
```

This creates `<username>_<YYYYMMDD>.zip` in the project root, without `node_modules`, `venv`, uploads or the local database. To choose the name, set `SUBMISSION_NAME`, e.g. `SUBMISSION_NAME=jdoe ./create_submission.sh`.

---

## 🛠️ Troubleshooting

- **"An Application Control policy has blocked this file" (Windows):** delete `frontend/node_modules` and `frontend/package-lock.json`, then run `npm install` again. The WebAssembly overrides only take effect on a fresh install.
- **`Activate.ps1 cannot be loaded`:** run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in the same terminal first.
- **`429 Call Limit Reached` while testing by hand:** that's the limit working. Raise it with `RATE_LIMIT_CALLS` (see [Limits](#limits)).
- **Port in use:** run `python manage.py runserver 8001`, and start the frontend with `VITE_API_URL=http://localhost:8001/api`.
- **Reset everything:** delete `backend/db.sqlite3` and `backend/media/`, then run `python manage.py migrate`.

Deployment guides: [DEPLOYMENT.md](DEPLOYMENT.md), [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md).
