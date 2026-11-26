# Quick Start Guide

## Fastest Way to Run the Application

### Using Docker (Recommended - Easiest)

1. **Ensure Docker is running on your system**

2. **Start all services with one command**
   ```bash
   docker-compose up --build
   ```

3. **Wait for services to start** (first time may take 2-3 minutes to build)

4. **Access the application**
   - Frontend: Open http://localhost:3000 in your browser
   - Backend API: http://localhost:8000/api/files/

5. **That's it!** You can now upload files and test deduplication.

### Testing Deduplication

1. Upload a file (e.g., a PDF or image)
2. Upload the **same file again** (even with a different name)
3. Notice:
   - A toast says a duplicate was detected
   - The new row has a **Duplicate** badge and the original shows **2 copies**
   - "Space saved" in the statistics goes up, while "Storage used" doesn't

### Testing Search & Filtering

1. Upload several files of different types
2. Use the search bar to find files by name
3. Try filtering by:
   - File size (min/max KB)
   - MIME type (e.g., "image", "pdf")
   - Date range
   - Check "Only show duplicated content" to see only duplicated files

### Switching users

Each user only sees their own files. Type another ID in the **User ID** box in the header and click **Switch user**.

## Troubleshooting

### Port Already in Use
If you get port conflicts:
- Backend (8000): Stop any Django servers running
- Frontend (3000): Stop any React servers running
- Or modify ports in `docker-compose.yml`

### Docker Issues
```bash
# If containers don't start properly
docker-compose down
docker-compose up --build

# To see logs
docker-compose logs backend
docker-compose logs frontend
```

### Database Migration
If you see database errors:
```bash
docker-compose exec backend python manage.py migrate
```

## Stopping the Application

Press `Ctrl+C` in the terminal, or:
```bash
docker-compose down
```

To also remove volumes (clears uploaded files):
```bash
docker-compose down -v
```

