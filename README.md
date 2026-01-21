# Gare Easy - Public Procurement Tender Aggregator

## Project Overview
This system aggregates public procurement tenders from multiple Italian platforms into a unified database with automatic updates every 6 hours.

## Architecture

### Scoring Strategy (Focus on Points)
1. **MEF Platform First (50 points)** - Complete before touching other platforms
2. **Level 1 Data (15 points)** - Basic tender information
3. **Update Detection (15 points)** - Detect new tenders at each check
4. **Attachments (10 points)** - Download and classify documents
5. **Level 2 Data (5 points)** - AI-extracted qualifications/criteria
6. **Tender Updates (5 points)** - Detect changes in existing tenders

### Tech Stack
- **Database**: SQLite (easy deployment) with migration path to PostgreSQL
- **Scraping**: Playwright (handles modern dynamic JavaScript sites)
- **PDF Processing**: pdfplumber + pypdf
- **AI Processing**: Anthropic Claude API (Level 2 data extraction)
- **Scheduler**: APScheduler (6-hour update cycle)
- **Frontend**: Streamlit
- **Python**: 3.10+

## Project Structure
```
gare_easy/
├── config/
│   ├── config.yaml           # Configuration settings
│   └── platforms.yaml        # Platform-specific scraping rules
├── database/
│   ├── __init__.py
│   ├── models.py             # Database schema and ORM models
│   └── db_manager.py         # Database operations
├── scrapers/
│   ├── __init__.py
│   ├── base_scraper.py       # Abstract base scraper
│   ├── mef_scraper.py        # MEF platform scraper (Priority 1)
│   ├── aria_scraper.py       # Aria regional platform
│   ├── toscana_scraper.py    # Toscana START platform
│   ├── empulia_scraper.py    # Empulia platform
│   ├── emilia_scraper.py     # Emilia-Romagna Intercent-ER
│   └── asmecomm_scraper.py   # Multi-entity platform
├── processors/
│   ├── __init__.py
│   ├── document_processor.py # PDF download and classification
│   └── ai_processor.py       # Claude API for Level 2 data
├── scheduler/
│   ├── __init__.py
│   └── job_scheduler.py      # APScheduler configuration
├── streamlit_app/
│   ├── app.py                # Main Streamlit application
│   └── components/           # Reusable UI components
├── data/
│   ├── downloads/            # Downloaded tender documents
│   └── gare_easy.db          # SQLite database
├── logs/
│   └── scraper.log
├── tests/
│   └── test_scrapers.py
├── requirements.txt
├── .env.example
└── main.py                   # Entry point for scraper
```

## Installation

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Set up environment variables
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

## Configuration

Edit `config/config.yaml`:
```yaml
database:
  type: sqlite
  path: data/gare_easy.db

scraper:
  update_interval_hours: 6
  max_retries: 3
  timeout_seconds: 30
  headless: true

platforms:
  priority:
    - mef  # 50 points - complete first
    - aria
    - toscana
    - empulia
    - emilia
    - asmecomm

documents:
  download_path: data/downloads
  max_file_size_mb: 50
```

## Usage

### Run Initial Scrape
```bash
python main.py --platform mef --mode initial
```

### Start Scheduled Updates (Every 6 Hours)
```bash
python main.py --schedule
```

### Launch Streamlit Dashboard
```bash
streamlit run streamlit_app/app.py
```

## Development Roadmap

### Phase 1: MEF Platform (Target: 50 points)
- [x] Database schema
- [ ] MEF scraper - Level 1 data
- [ ] Update detection logic
- [ ] Attachment download
- [ ] Level 2 data extraction
- [ ] Testing and validation

### Phase 2: Additional Platforms (20 points each)
- [ ] Aria (Lombardia)
- [ ] START Toscana
- [ ] Empulia
- [ ] Intercent-ER Emilia-Romagna
- [ ] Asmecomm

### Phase 3: Frontend & Monitoring
- [ ] Streamlit dashboard
- [ ] Search and filtering
- [ ] Statistics and analytics
- [ ] Export functionality

## Key Features

### Update Detection
The system uses CIG (Codice Identificativo Gara) as the primary key to detect:
- **New tenders**: CIG not in database
- **Updated tenders**: CIG exists but `last_update_date` or other fields changed
- **Closed tenders**: Deadline passed or status changed

### Document Classification
Attachments are automatically categorized:
- **Informative**: Regulations, technical specs, drawings
- **Compilable**: Application forms, declaration templates

### Level 2 Data Extraction
Claude AI processes tender documents to extract:
- Required qualifications (turnover, certifications, experience)
- Evaluation criteria (scoring weights, thresholds)
- Process description (application steps, envelope structure)
- Delivery methods (payments, guarantees, advances)
- Required documentation (formats, signatures)

## Monitoring

Check logs:
```bash
tail -f logs/scraper.log
```

Database stats:
```sql
SELECT platform_name, COUNT(*) as total, 
       SUM(CASE WHEN status='Active' THEN 1 ELSE 0 END) as active
FROM tenders 
GROUP BY platform_name;
```

## Troubleshooting

### Playwright Issues
```bash
playwright install --force chromium
```

### Database Lock (SQLite)
If you see "database is locked", ensure only one scraper instance is running.

### Missing Data
Check `status` field in database - should be 'Complete' for fully scraped tenders.

## License
This is an internship assignment project for Gare Easy - Bando Easy GdA Section.
