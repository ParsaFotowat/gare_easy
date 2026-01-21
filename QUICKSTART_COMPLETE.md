# 🚀 GARE EASY - Quick Start Guide

## ✅ Setup Complete!

Your Gare Easy system is ready with:
- ✅ Database layer with CRUD operations
- ✅ MEF scraper with real selectors
- ✅ Document downloader for attachments
- ✅ PDF text extraction (pdfplumber)
- ✅ Google Gemini AI for Level 2 data extraction
- ✅ Streamlit dashboard with filters and analytics
- ✅ APScheduler for 6-hour automatic updates

---

## 📋 How to Use

### Option 1: Run Single Scrape (Test)
```bash
# Windows
run_scraper_once.bat

# Or manually
python main.py --platform mef --mode once
```

This will:
1. Scrape MEF platform for tenders
2. Download attachments
3. Extract text from PDFs
4. Use Gemini AI to extract Level 2 data
5. Store everything in database

### Option 2: Run Scheduler (Production)
```bash
# Windows
run_scheduler.bat

# Or manually
python main.py --mode schedule --platform mef
```

This will:
- Run scraper every 6 hours automatically
- Keep updating tenders and checking for changes
- Run in background until you press Ctrl+C

### Option 3: View Dashboard
```bash
# Windows
run_dashboard.bat

# Or manually
streamlit run streamlit_app/app.py
```

Open browser to: http://localhost:8501

Dashboard features:
- 📊 Overview with key metrics
- 📋 Searchable tender table
- 📈 Analytics and charts
- 🔍 Detailed tender view with Level 2 data

---

## 🔧 Configuration

### Google API Key (Already Set)
Your key is in `.env`:
```
GOOGLE_API_KEY=AIzaSyDWcNEJrB-hoMeU5Fgc8nh3U5sXxlyqbqw
```

### Update Frequency
Edit `config/config.yaml`:
```yaml
scraper:
  update_interval_hours: 6  # Change to 3, 12, 24, etc.
```

### Enable/Disable AI
```yaml
level2:
  enabled: true  # Set to false to skip AI extraction
  model: gemini-pro  # Free tier model
```

---

## 📁 Project Structure

```
gare_easy/
├── main.py                  # Main entry point
├── run_dashboard.bat        # Quick start dashboard
├── run_scheduler.bat        # Quick start scheduler
├── run_scraper_once.bat     # Quick start single run
├── config/
│   └── config.yaml          # Configuration
├── database/
│   ├── db_manager.py        # CRUD operations
│   └── models.py            # SQLAlchemy models
├── scrapers/
│   ├── base_scraper.py      # Base scraper class
│   └── mef_scraper.py       # MEF platform scraper
├── processors/
│   ├── document_processor.py # Download attachments
│   ├── pdf_extractor.py     # Extract text from PDFs
│   └── ai_processor.py      # Gemini AI integration
├── scheduler/
│   └── job_scheduler.py     # APScheduler wrapper
├── streamlit_app/
│   └── app.py               # Dashboard UI
└── data/
    ├── gare_easy.db         # SQLite database
    └── downloads/           # Downloaded PDFs
```

---

## 🎯 Scoring Status

### Implemented (85+ points)
- ✅ **MEF Platform** (50 points) - Complete with real selectors
- ✅ **Database Layer** (10 points) - CRUD + upsert + change detection
- ✅ **Document Downloader** (10 points) - Download attachments to organized folders
- ✅ **Level 2 Extraction** (15 points) - Gemini AI for qualifications, criteria, etc.
- ✅ **Streamlit Dashboard** (10 points) - Filters, metrics, analytics, detail view
- ✅ **Scheduler** (10 points) - 6-hour automatic updates

### Ready to Add (100+ points)
- ⏳ **Regional Platforms** (20 points each)
  - Aria, Toscana, Empulia, Emilia, ASMeComm
  - Copy MEF scraper pattern, update selectors

---

## 🧪 Testing

### Test Database Layer
```bash
python test_database.py
```

### Test Document Processor
```bash
python test_document_processor.py
```

### Test AI Processor
```bash
python processors/ai_processor.py
```

---

## 📊 Database Schema

### Main Tables
- **tenders** - Level 1 data (title, amount, deadline, etc.)
- **level2_data** - AI-extracted data (qualifications, criteria, etc.)
- **attachments** - File metadata and download status
- **scraper_logs** - Execution history

### Key Queries
```python
# Get tenders without Level 2 data
tenders = db.get_tenders_without_level2('MEF', limit=10)

# Get undownloaded attachments
attachments = db.get_undownloaded_attachments(tender_id)

# Get statistics
stats = db.get_statistics()
```

---

## 🐛 Troubleshooting

### "No tenders in database"
Run the scraper first:
```bash
python main.py --platform mef --mode once
```

### "AI extraction failed"
Check API key:
```bash
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('GOOGLE_API_KEY'))"
```

### "Module not found"
Install dependencies:
```bash
pip install -r requirements.txt
```

### Playwright browser issues
Install browsers:
```bash
playwright install chromium
```

---

## 🎓 Next Steps

1. **Run first scrape**: `run_scraper_once.bat`
2. **Check dashboard**: `run_dashboard.bat`
3. **Start scheduler**: `run_scheduler.bat` (for production)
4. **Add more platforms**: Copy `mef_scraper.py`, update selectors

---

## 📞 Support

- Check logs in `logs/scraper.log`
- Review database with SQLite browser
- Test individual components with test files

**Ready to go! Run `run_scraper_once.bat` to start.**
