# Bill Viewer Web Application

A web interface for browsing scraped bills and configuring new scrape jobs.

## Architecture

- **Backend**: Flask API (`web/api/`)
- **Frontend**: React + TypeScript + TailwindCSS (`web/frontend/`)
- **Database**: MySQL 

## Setup

### Backend

1. Install Python dependencies:
   ```bash
   pip install -r web/requirements.txt
   ```

2. Ensure your `.env` file contains the database credentials:
   ```
   host_name=localhost
   user_name=your_user
   password=your_password
   database_name=your_database
   db_type= "SQLite" or "MySQL"
   ```

3. Start the Flask server:
   ```bash
   python -m web.api.app
   ```
   The API will be available at http://localhost:5000

### Frontend

1. Install Node.js dependencies:
   ```bash
   cd web/frontend
   npm install
   ```

2. Start the development server:
   ```bash
   npm run dev
   ```
   The frontend will be available at http://localhost:5173

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/jurisdictions` | GET | List unique domains from scraped bills |
| `/api/bills` | GET | List bills with optional `?jurisdiction=` filter |
| `/api/bills/<id>` | GET | Get single bill with full text |
| `/api/scrapes` | GET | List all scrape jobs |
| `/api/scrapes` | POST | Create and start a new scrape job |
| `/api/scrapes/<job_id>` | GET | Get job status and results |
| `/api/health` | GET | Health check |

## Features

### Browse Bills
- Filter bills by jurisdiction
- Paginated list view
- Full text detail view

### New Scrape
- Enter search terms (one per line)
- Select jurisdictions from predefined list
- Set optional date range
- Jobs run asynchronously in background
- Note that the juridsticitions we allow to be scraped are hardcoded

### Job Status
- Real-time status updates (polling)
- View results when complete
- See error logs on failure

## Production Deployment

For production, build the frontend and serve it with the Flask app:

```bash
cd web/frontend
npm run build
```

Then configure Flask to serve the built files from `web/frontend/dist/`.
