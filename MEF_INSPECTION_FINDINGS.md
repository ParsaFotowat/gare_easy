# MEF Website Inspection - Findings & Selectors

**Date**: January 19, 2026
**URL**: https://www.acquistinretepa.it/opencms/opencms/vetrina_bandi.html
**Status**: ✅ Inspection Complete - Scraper Updated

---

## 📋 Page Structure Analysis

### Tender List Structure
```
<h3>
  <a href="/opencms/opencms/scheda_bando.html?idBando=XXXXX">
    Tender Title Text
  </a>
</h3>
<p>
  Metadata text containing:
  - Publication date: "Attivo dal DD/MM/YYYY al DD/MM/YYYY"
  - Bando number: "N. bando XXXXXXX"
  - Sigef code: "Cod. Sigef XXXX"
  - Instrument: "Strumento: AQ|SDA|MePA|CONVENZIONI"
  - Status: "Bando attivo" or "Bando chiuso"
  - Categories: Category tags
</p>
```

### Key Selectors Identified

#### Tender List Page (`vetrina_bandi.html`)
- **Tender headings**: `h3` tags containing `<a>` link
- **Link pattern**: `/opencms/opencms/scheda_bando.html?idBando=<ID>`
- **Metadata**: Text following heading contains all structured data
- **Pagination**: "Successivo" or "Next" button for navigation

#### Tender Detail Page (`scheda_bando.html?idBando=XXX`)
- **Structure**: Dynamic page with metadata in text format
- **Data location**: Primarily in page text content (not structured HTML)
- **Key patterns**:
  - Amount: `Importo|Valore` followed by €XXX
  - Procedure: `Procedura|Tipo di procedura` 
  - Place: `Luogo|Luogo di esecuzione`
  - Authority: `Stazione appaltante|Ente`
  - CPV: `CPV:\s*[\d\s]+`
  - Sector: `Ordinario|Speciale`
  - Duration: `Durata|Durata del contratto`
  - Lots: `Lotti|Numero di lotti`
  - RUP: `RUP|Responsabile Unico del Procedimento`
  - Session: `Seduta pubblica`
  - Criterion: `Criterio|Aggiudicazione`

#### File Downloads
- **Location**: Links throughout detail page with file extensions
- **Extensions**: .pdf, .doc, .docx, .xls, .xlsx, .zip, .rar, .txt, .rtf
- **Classification**: Modulo/Modello/Domanda/Form → Compilable, others → Informative

---

## 📊 Real Data Examples

### Sample Tender 1: Vehicles
```
Title: Veicoli
Publication: 12/01/2026 - 19/12/2095
Bando #: 5895209
Sigef Code: (none)
Instrument: AQ
Status: Active
Categories: Veicoli, mobilità e trasporti
```

### Sample Tender 2: Micro-logistics
```
Title: Micro-logistica in ambito sanitario (ID 2890)
Publication: 23/12/2025 - 10/02/2026
Bando #: 5903720
Sigef Code: 2890
Instrument: AQ
Status: Active
Categories: Sanità, Ricerca e Welfare
```

---

## 🔧 Scraper Updates Made

### Changes to `scrapers/mef_scraper.py`

1. **Selector updates**:
   - Changed from looking for `#post_call_position` table (doesn't exist)
   - Now searches for `h3` headings containing tender links ✅
   - Uses regex patterns to extract metadata from text content ✅

2. **Method refactoring**:
   - Removed `_scrape_category()` - not applicable to MEF structure
   - Added `_scrape_tender_list()` - processes tender headings on current page
   - Added `_handle_pagination()` - navigates through page results
   - Simplified `_scrape_tender_detail()` - uses regex extraction instead of CSS selectors
   - Updated `_extract_attachments()` - looks for file extension links

3. **Data extraction improvements**:
   - Uses regex patterns for flexible text matching (handles Italian labels)
   - Case-insensitive matching for field names
   - Graceful degradation - continues if some fields not found
   - Quality score calculation based on populated fields

4. **Robustness**:
   - Better error handling with try-catch blocks
   - Logging at each step for debugging
   - Statistics tracking (found, new, updated, errors)
   - Polite delays between requests

---

## ✅ Testing Checklist

- [ ] Run scraper on MEF website without errors
- [ ] Extract 10+ tenders successfully
- [ ] All Level 1 fields populated or marked "Not Found"
- [ ] Data quality score > 60% on average
- [ ] Pagination works (if > 20 tenders)
- [ ] Attachment URLs extracted
- [ ] CIG codes properly identified
- [ ] Dates parsed correctly (Italian format DD/MM/YYYY)
- [ ] Database upsert logic working (no duplicates)

---

## 🚀 Next Steps

1. **Phase 1 (Level 1 Data)**: 15 points
   - Database upsert logic ✓ (database/db_manager.py)
   - MEF scraper running ✓ (this file)
   - Test on real data

2. **Phase 2 (Attachment Downloads)**: 10 points
   - Download manager (processors/document_processor.py)
   - Store PDFs in data/downloads/[CIG]/ folder
   - Track download status in database

3. **Phase 3 (Level 2 Data)**: 15 points
   - PDF text extraction (pdfplumber)
   - Claude API integration (processors/ai_processor.py)
   - Extract: requirements, evaluation criteria, process description

4. **Phase 4 (UI)**: 10 points
   - Streamlit dashboard
   - Filters, sorting, detail view
   - Attachment downloads

5. **Phase 5 (Scheduler)**: 10 points
   - APScheduler 6-hour job
   - Run full scrape cycle
   - Log execution and statistics

---

## 📝 Notes

- MEF platform uses **semi-structured data** - metadata is text, not HTML attributes
- **Date format**: Always DD/MM/YYYY
- **Amount format**: €X.XXX,XX (European format) → needs conversion to float
- **CIG codes**: 10-character alphanumeric codes
- **Pagination**: Simple "next" button pattern
- **Dynamic content**: Minimal JS - most data is in initial HTML

---

## 🔗 Related Files

- Main scraper: `scrapers/mef_scraper.py` (updated)
- Database models: `database/models.py`
- Database manager: `database/db_manager.py`
- Main entry point: `main.py`
- Config: `config/config.yaml`

