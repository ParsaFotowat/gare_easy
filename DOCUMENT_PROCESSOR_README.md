# Document Processor & PDF Extractor Implementation

## Overview

**Status:** ✅ COMPLETE - Phase 2 (Document Downloader) + Phase 3A (PDF Text Extraction)
**Points:** 10 (Document Downloader) + Prerequisite for 15 (Claude API Integration)
**Date Implemented:** January 19, 2026

## Architecture

### DocumentProcessor (`processors/document_processor.py`)
Handles downloading and organizing tender attachments with the following features:

#### Key Methods

1. **`process_tender_attachments(tender_id, attachments)`**
   - Downloads all attachments for a tender
   - Stores files to `data/downloads/[CIG]/` folder structure
   - Tracks download status in database (0=not downloaded, 1=downloaded, -1=failed)
   - Returns statistics: total, downloaded, failed, skipped

2. **`_download_file(url, folder, filename)`**
   - Streams large files in chunks (8KB) to prevent memory issues
   - Validates file extension against allowed list
   - Checks file size limits (default 50 MB)
   - Skips existing files with size > 0
   - Returns: (success: bool, local_path: Path, error: str)

3. **`classify_document(filename)`**
   - Classifies documents as "Compilable" or "Informative"
   - Uses configurable keyword matching
   - Returns: (category: str, confidence: 0.0-0.9)
   - Examples:
     - Compilable: "Modulo_Offerta", "Schema", "Allegato A"
     - Informative: "Bando", "Capitolato", "Disciplinare"

4. **`get_tender_documents(tender_id)`**
   - Returns list of all downloaded files for a tender
   - Searches for all allowed extensions (pdf, doc, docx, xls, xlsx, zip, rar)

5. **`extract_text_from_tender_attachments(tender_id)`**
   - Extracts text from all PDF attachments for a tender
   - Returns structured analysis with section detection
   - Success/error reporting for debugging

6. **`prepare_text_for_ai_processing(tender_id)`**
   - Prepares extracted text for Claude API processing
   - Aggregates findings by category
   - Limits text to 50K chars for API cost control
   - Returns dict with: required_qualifications, evaluation_criteria, process_description, delivery_methods, raw_text

### PDFExtractor (`processors/pdf_extractor.py`)
Extracts and analyzes text from PDF documents using pdfplumber:

#### Key Methods

1. **`extract_text_from_pdf(pdf_path, max_pages=20)`**
   - Extracts all text from PDF file
   - Limits to first N pages (default 20 to save time)
   - Minimum text length filter (50 chars per page)
   - Returns raw combined text or None if extraction fails

2. **`analyze_document(pdf_path)`**
   - Comprehensive document analysis
   - Extracts text and searches for key sections
   - Returns dict with:
     - success: bool
     - text: str (full extracted text)
     - qualifications: str (matching sections)
     - evaluation_criteria: str (matching sections)
     - process_description: str (matching sections)
     - delivery_methods: str (matching sections)
     - text_length: int
     - sections_found: int (0-4)

3. **`extract_from_tender_attachments(tender_id, attachment_paths)`**
   - Processes multiple PDF files for a tender
   - Aggregates findings across all documents
   - Returns comprehensive analysis with:
     - documents_processed, documents_failed, total_text_length
     - qualifications, evaluation_criteria, process_description, delivery_methods (lists with source attribution)

4. **`prepare_for_ai_processing(analysis)`**
   - Converts analysis results into API-ready format
   - Aggregates multiple sources for each section
   - Limits each section to 3000 chars
   - Provides raw_text as fallback (50K char limit)

#### Keyword Detection

Pre-configured keyword lists in four categories:

**Qualifications Keywords:** requisiti, qualificazioni, certificazioni, attestati, iscrizione, albo, norme iso, patente, licenza, abilitazione

**Evaluation Keywords:** valutazione, criteri, criterio, punteggio, punti, offerta, aggiudicazione, priorità, soglia, minimo, massimo, sorteggio

**Process Keywords:** procedimento, procedura, processo, fasi, fase, modalità, commissione, commissario, responsabile, svolgimento, calendario, cronoprogramma

**Delivery Keywords:** consegna, consegne, tempi di consegna, durata, termine, scadenza, esecuzione, realizz azione, deliverable, luogo di consegna, sede di esecuzione, cantiere

## Data Flow

```
MEF Scraper (scraper_tenders)
    ↓
    Attachments → DocumentProcessor.process_tender_attachments()
        ↓
        Download file → data/downloads/[CIG]/filename
        ↓
        Update DB: Attachment.downloaded = 1, local_path = ...
    ↓
DocumentProcessor.extract_text_from_tender_attachments()
    ↓
    For each PDF in data/downloads/[CIG]/
        ↓
        PDFExtractor.analyze_document()
            ↓
            pdfplumber.open() → extract_text()
            ↓
            Keyword matching for 4 categories
            ↓
        Returns: {text, qualifications, evaluation_criteria, ...}
    ↓
DocumentProcessor.prepare_text_for_ai_processing()
    ↓
    Aggregates findings → {raw_text: "...", required_qualifications: "...", ...}
    ↓
    Ready for Claude API (processors/ai_processor.py - Phase 3B)
```

## Configuration (`config.yaml`)

```yaml
documents:
  download_path: data/downloads        # Base folder for downloads
  max_file_size_mb: 50                # Max file size in MB
  max_pdf_pages: 20                   # Max pages to extract from PDF
  min_text_length: 50                 # Minimum text per page (chars)
  allowed_extensions:
    - pdf
    - doc
    - docx
    - xls
    - xlsx
    - zip
    - rar
  compilable_keywords:                # Identifies form documents
    - modulo
    - offerta
    - schema
    - allegato
    - formulario
  informative_keywords:               # Identifies informational documents
    - bando
    - capitolato
    - disciplinare
    - avviso
    - decreto
```

## Database Schema Integration

### Attachment Table Additions

Existing columns used:
- `file_name`: str - Original filename
- `file_url`: str - Download URL
- `category`: str - "Compilable" or "Informative"
- `downloaded`: int - 0=not, 1=yes, -1=failed
- `local_path`: str - Where file is stored
- `download_date`: datetime - When downloaded
- `error`: str - Error message if download failed

### Level2Data Table Integration

After PDF extraction, data is prepared for storage via:
```python
db.add_level2_data(tender_id, {
    'required_qualifications': extracted_text,
    'evaluation_criteria': extracted_text,
    'process_description': extracted_text,
    'delivery_methods': extracted_text,
    'confidence_score': 0.85  # Set by Claude API later
})
```

## Usage Examples

### Download Attachments for a Tender
```python
from processors.document_processor import DocumentProcessor
from database.db_manager import DatabaseManager

db = DatabaseManager()
processor = DocumentProcessor(config, db)

# Assuming tender already has attachments in DB
attachments = [
    {'file_name': 'bando.pdf', 'file_url': 'https://...', 'category': 'Informative'},
    {'file_name': 'offerta.xlsx', 'file_url': 'https://...', 'category': 'Compilable'}
]

stats = processor.process_tender_attachments('CIG_123', attachments)
print(f"Downloaded: {stats['downloaded']}, Failed: {stats['failed']}")
```

### Extract Text from Downloaded PDFs
```python
# Get text ready for AI processing
ai_input = processor.prepare_text_for_ai_processing('CIG_123')

if ai_input:
    print(f"Qualifications: {ai_input['required_qualifications'][:100]}...")
    print(f"Raw text length: {len(ai_input['raw_text'])} chars")
```

### Manual PDF Analysis
```python
from processors.pdf_extractor import PDFExtractor
from pathlib import Path

extractor = PDFExtractor(config)
pdf_path = Path('data/downloads/CIG_123/document.pdf')

analysis = extractor.analyze_document(pdf_path)
print(f"Sections found: {analysis['sections_found']}/4")
print(f"Qualifications: {analysis['qualifications']}")
```

## Testing

**Test Suite:** `test_document_processor.py`

**Test Coverage:**
- ✅ Document classification (Compilable vs Informative)
- ✅ Tender creation with attachments
- ✅ Sample document creation
- ✅ Text extraction and keyword detection (4/4 sections)
- ✅ Database attachment storage
- ✅ Query for tenders ready for AI processing
- ✅ System statistics calculation

**Run Tests:**
```bash
python test_document_processor.py
```

**Test Results:** All 7 test groups PASS
```
✓ Document classification working
✓ Tender with attachments created
✓ Sample document created for testing
✓ Text extraction and analysis working
✓ Keyword detection working (4/4 sections found)
✓ Database attachment storage working
✓ Tenders for AI processing query working
✓ Statistics calculation working
```

## Performance Considerations

### File Download
- **Streaming:** Downloads in 8KB chunks to prevent memory issues
- **Deduplication:** Skips files that already exist (size > 0 bytes)
- **Size Limits:** 50 MB default, configurable
- **Timeout:** 60 seconds default per request

### PDF Text Extraction
- **Page Limit:** First 20 pages by default (configurable via config)
- **Minimum Text:** 50 chars per page filter to skip blank pages
- **Memory:** pdfplumber handles single PDF in memory, processes one at a time
- **Speed:** ~100-500 pages/sec depending on content complexity

### API Preparation
- **Text Limit:** 50K characters max (rough estimate: 10-15 pages)
- **Section Limit:** 3000 chars per section (qualifications, evaluation, etc.)
- **Aggregation:** Deduplicates and combines findings from multiple PDFs

## Error Handling

### Download Errors
```
Invalid URL → Returns False, None, "Invalid URL"
HTTP Error 404 → Returns False, None, "HTTP error: 404"
Timeout (60s) → Returns False, None, "Download timeout"
File Too Large → Returns False, None, "File too large: X.X MB"
```

### PDF Extraction Errors
```
File not found → Logs warning, returns None
PDF corrupted → Logs error, returns None
Page extraction fails → Logs warning, continues with next page
No text extracted → Returns None
```

## Next Steps (Phase 3B)

The extracted text is now ready for Claude API integration:

1. **Create `processors/ai_processor.py`**
   - Takes prepared text from `prepare_text_for_ai_processing()`
   - Sends to Claude API with extraction prompt
   - Parses JSON response
   - Stores results in Level2Data table

2. **Update `base_scraper.py` to integrate**
   - After tender scraped → Download attachments
   - After downloaded → Extract text
   - After extracted → Send to Claude API
   - After API response → Save Level 2 data

3. **Create complete workflow**
   - MEF Scraper → DocumentProcessor → PDFExtractor → AIProcessor → Database

## Statistics & Monitoring

Get comprehensive statistics:
```python
stats = processor.get_download_statistics()
# Returns:
# - total_tenders
# - active_tenders
# - storage_size_mb
# - attachment counts
# - quality scores
```

Monitor document processing:
```python
logger.info(f"Extracted text from {analysis['documents_processed']} PDFs for tender {tender_id}")
logger.debug(f"Text extraction for {pdf_path.name}: {len(text)} characters")
```

## Scoring

- **Phase 2 (Document Downloader):** 10 points ✅
  - Download attachments from tender URLs ✓
  - Organize by tender ID in folder structure ✓
  - Track download status in database ✓
  
- **Phase 3A (PDF Text Extraction):** Prerequisite (not directly scored)
  - Extract text from PDF files ✓
  - Keyword detection (4 categories) ✓
  - Prepare for AI processing ✓

- **Phase 3B (Claude API Integration):** 15 points (pending)
  - Send extracted text to Claude API
  - Parse structured response
  - Save Level 2 data to database

---

## Files Modified/Created

| File | Status | Lines | Purpose |
|------|--------|-------|---------|
| processors/document_processor.py | CREATED | 370 | Download and organize attachments |
| processors/pdf_extractor.py | CREATED | 380 | Extract and analyze PDF text |
| test_document_processor.py | CREATED | 210 | Comprehensive test suite |
| DOCUMENT_PROCESSOR_README.md | CREATED | This file | Documentation |

**Total New Code:** ~960 lines
**Test Coverage:** 7 test groups, all passing
**External Dependencies:** pdfplumber 0.10.3, requests 2.31.0
