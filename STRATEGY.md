# Gare Easy Implementation Strategy
## How to Get Maximum Points for Your Internship

---

## Executive Summary

This project implements a public procurement tender aggregator for Italian platforms. The scoring is **heavily weighted toward the first platform (MEF)** - complete it perfectly before touching anything else.

**Recommended Approach:**
1. **Phase 1 (Week 1):** Perfect MEF platform → 50 points ✓
2. **Phase 2 (Week 2):** Add 2-3 regional platforms → 40-60 points
3. **Phase 3 (Week 3):** Polish, optimize, document

**Total Achievable: 90-130 points**

---

## Phase 1: MEF Platform (50 Points) - DO THIS FIRST

### Why MEF First?
- Worth 50 points alone (half your score!)
- Other platforms only worth 20 points each
- Template for all other scrapers
- Demonstrates all required capabilities

### Implementation Steps

#### Step 1: Inspect the Website (1 Hour)
```bash
# Open MEF platform in browser
https://www.acquistinretepa.it/opencms/opencms/vetrina_bandi.html

# What to check:
# 1. How tenders are displayed (table? cards?)
# 2. Where to find each data field
# 3. How to access detail pages
# 4. Where attachments are located
# 5. How pages load (static HTML or JavaScript?)
```

**Action Items:**
- [ ] Take screenshots of tender list page
- [ ] Take screenshots of tender detail page
- [ ] Note all CSS selectors for data fields
- [ ] Check if pagination exists
- [ ] Test if content loads dynamically (open DevTools Network tab)

#### Step 2: Update Scraper Selectors (2 Hours)

Open `scrapers/mef_scraper.py` and update these sections:

```python
# TEMPLATE LOCATIONS TO UPDATE:

# Line ~100: _scrape_category()
# Find the correct selector for tender table
table_html = page.inner_html('#post_call_position')  # ← VERIFY THIS

# Line ~115: _extract_row_data()
title_elem = row.find('a', class_='tender-title')  # ← UPDATE THIS
cig_elem = row.find('span', class_='cig')  # ← UPDATE THIS

# Line ~180: _scrape_tender_detail()
# Update ALL field selectors based on actual HTML
amount_elem = soup.find('span', string=lambda t: 'importo' in t.lower() if t else False)
```

**Testing Strategy:**
```powershell
# Test with single tender first
# Add print statements to debug
# Check logs/scraper.log for errors
```

#### Step 3: Test Level 1 Data (15 Points) - 1 Hour

```powershell
# Run without downloads to test faster
python main.py --platform mef --no-docs --no-level2

# Check results
streamlit run streamlit_app/app.py
```

**Validation Checklist:**
- [ ] Tenders appear in database
- [ ] All Level 1 fields populated (or marked "Not Found")
- [ ] Data quality score > 70%
- [ ] No Python errors in logs
- [ ] Title, deadline, CIG extracted correctly

**Scoring: 15 points** - "Correctly entering level 1 data"

#### Step 4: Test Update Detection (15 Points) - 1 Hour

```powershell
# Run scraper twice
python main.py --platform mef --no-docs --no-level2
python main.py --platform mef --no-docs --no-level2

# Check that:
# 1. Second run doesn't duplicate tenders
# 2. "Updated" status appears if data changed
# 3. "New" count is correct in logs
```

**Validation:**
- [ ] No duplicate tenders in database
- [ ] New tenders detected correctly
- [ ] Changed tenders marked as "Updated"
- [ ] Closed tenders marked as "Closed"

**Scoring: 15 points** - "Correctly entering new tenders at each check"

#### Step 5: Document Downloads (10 Points) - 2 Hours

```powershell
# Enable document downloads
python main.py --platform mef --no-level2

# Check:
# - data/downloads/CIG_XXXXXXX/ folders created
# - PDFs downloaded
# - Classified as Informative/Compilable
```

**Validation:**
- [ ] Attachments downloaded to correct folders
- [ ] File sizes reasonable (not corrupted)
- [ ] Classification works (check database)
- [ ] Failed downloads logged properly

**Scoring: 10 points** - "Correctly obtaining the tender attachments"

#### Step 6: Level 2 Data Extraction (5 Points) - 2 Hours

**Prerequisites:**
1. Get Claude API key from https://console.anthropic.com
2. Add to `.env` file
3. Fund account with $5-10 (should be enough for testing)

```powershell
# Run with full AI extraction
python main.py --platform mef

# Check Level 2 data in dashboard
# Look at "AI-Extracted Information" section
```

**Validation:**
- [ ] Level 2 data appears in database
- [ ] Qualifications extracted from PDFs
- [ ] Evaluation criteria found
- [ ] Process description makes sense
- [ ] Confidence score > 0.5

**Cost Estimate:** $0.05-0.15 per tender × 20 tenders = $1-3

**Scoring: 5 points** - "Correctly entering level 2 data"

#### Step 7: Tender Updates Detection (5 Points) - 1 Hour

**The Tricky Part:** Detecting changes in existing tenders

```powershell
# Manually modify a tender on the platform (if you have access)
# OR wait for platform to update a tender
# Then run scraper again

python main.py --platform mef

# Check that tender is marked as "Updated"
```

**What triggers "Updated":**
- Deadline changed
- Amount changed
- Status changed
- Publication date changed

**Validation:**
- [ ] `last_updated_at` timestamp changes
- [ ] `status` set to "Updated"
- [ ] Log shows "tenders_updated: X"

**Scoring: 5 points** - "Correctly updating the tenders already present"

#### Step 8: Enable Scheduling - Final Step

```powershell
# Run in scheduled mode
python main.py --platform mef --mode schedule

# Let it run overnight
# Check logs next day
```

**Validation:**
- [ ] Runs every 6 hours automatically
- [ ] No crashes or hangs
- [ ] Database grows with new tenders
- [ ] Updates detected on subsequent runs

---

## Phase 2: Regional Platforms (20 Points Each)

**Only start this after MEF is perfect (50/50 points)**

### Priority Order (Based on Difficulty):

1. **Aria (Lombardia)** - Easiest
   - URL: https://www.ariaspa.it/wps/portal/Aria/Home/bandi-convenzioni/bandi-di-gara/i-nostri-bandi-di-gara/
   - Similar structure to MEF
   - Estimated time: 4 hours

2. **START Toscana** - Medium
   - URL: https://start.toscana.it/initiatives/list/
   - Modern interface
   - Estimated time: 6 hours

3. **Empulia** - Hard
   - URL: http://www.empulia.it/tno-a/empulia/Empulia/SitePages/Bandi di gara new.aspx
   - SharePoint-based (complex)
   - Estimated time: 8 hours

4. **Intercent-ER** - Medium
   - URL: https://intercenter.regione.emilia-romagna.it/servizi-imprese/bandi-e-avvisi_new
   - Well-structured
   - Estimated time: 5 hours

5. **Asmecomm** - Unknown
   - URL: https://piattaforma.asmecomm.it/
   - Requires authentication?
   - Estimated time: 6-10 hours

### Implementation Template for Each Platform

```powershell
# 1. Copy MEF scraper as template
copy scrapers\mef_scraper.py scrapers\aria_scraper.py

# 2. Update class name and URLs
# Edit: ARIAScraper, platform_name = "ARIA", base_url = ...

# 3. Inspect website and update selectors

# 4. Test
python main.py --platform aria --no-docs --no-level2

# 5. Enable full features
python main.py --platform aria

# 6. Add to scheduler
# Edit main.py to include new platform
```

### Scoring for Each Additional Platform (20 Points):
- Level 1 data: 5 points
- New tender detection: 5 points  
- Attachments: 4 points
- Level 2 data: 3 points
- Update detection: 3 points

**Strategy:** Prioritize **2 platforms perfectly** (40 points) over **5 platforms poorly** (20-30 points)

---

## Phase 3: Polish & Optimization

### Data Quality Improvements

**Goal: 90%+ data quality score**

1. **Field Coverage**
   ```python
   # In database/models.py - Tender.calculate_quality_score()
   # All 16 fields should be filled
   ```

2. **Data Validation**
   - Amounts in correct format
   - Dates parsed correctly
   - CIG codes validated (10 characters)
   - URLs are accessible

3. **Error Handling**
   ```python
   # Add retry logic for failed downloads
   # Catch and log all exceptions
   # Don't crash on missing data
   ```

### Dashboard Enhancements

**Make it impressive for the evaluation:**

1. Add filters and search
2. Export functionality (CSV, Excel)
3. Statistics and charts
4. Real-time updates
5. Error logs display

### Documentation

**Critical for evaluation:**

1. **README.md** - Overview and installation
2. **QUICKSTART.md** - Step-by-step guide
3. **API Documentation** - Code comments
4. **Test Results** - Screenshots showing data

---

## Common Pitfalls & Solutions

### Problem: Scraper finds no tenders
**Solution:**
- Check if CSS selectors are correct
- Use browser DevTools to inspect HTML
- Add `page.screenshot(path='debug.png')` to see what Playwright sees
- Check if page requires JavaScript execution

### Problem: Data quality score < 70%
**Solution:**
- Add fallback selectors for each field
- Search multiple places for same data
- Use regex to extract from unstructured text
- Mark fields as "Not Found" instead of leaving blank

### Problem: Level 2 extraction returns "Not Found" for everything
**Solution:**
- Check if PDFs are text-based (not scanned images)
- Use pdfplumber to verify text extraction works
- Increase max_pages_per_document in config
- Refine Claude prompt with specific Italian terms

### Problem: Duplicate tenders in database
**Solution:**
- Ensure CIG extraction is consistent
- Add fallback ID generation using URL hash
- Check upsert logic in db_manager.py

### Problem: Scheduler stops after few hours
**Solution:**
- Check for memory leaks
- Close Playwright browsers properly
- Add exception handling in scheduler
- Run in screen/tmux session on Linux

---

## Time Estimates

| Task | Time | Points | Priority |
|------|------|--------|----------|
| Setup & Configuration | 0.5h | 0 | Must |
| MEF Inspection | 1h | 0 | Must |
| MEF Level 1 | 3h | 15 | Must |
| MEF Updates | 2h | 15 | Must |
| MEF Attachments | 2h | 10 | Must |
| MEF Level 2 | 2h | 5 | Must |
| MEF Update Detection | 1h | 5 | Must |
| **MEF Total** | **11.5h** | **50** | **Must** |
| Platform 2 (Aria) | 4h | 20 | Should |
| Platform 3 (Toscana) | 6h | 20 | Should |
| Platform 4 (Empulia) | 8h | 20 | Could |
| Platform 5 (Emilia) | 5h | 20 | Could |
| Platform 6 (Asmecomm) | 8h | 20 | Could |
| Dashboard | 3h | 0 | Should |
| Documentation | 2h | 0 | Should |
| Testing & Debug | 4h | 0 | Must |

**Recommended Schedule (3 weeks):**

**Week 1:** MEF Platform
- Day 1-2: Setup, inspection, Level 1 data
- Day 3: Updates and attachments
- Day 4: Level 2 extraction
- Day 5: Testing, scheduling, debugging
- **Goal: 50/50 points on MEF**

**Week 2:** Additional Platforms
- Day 1-2: Aria platform (20 points)
- Day 3-4: Toscana platform (20 points)
- Day 5: Testing and fixes
- **Goal: 90/90 points total**

**Week 3:** Polish
- Day 1: Dashboard enhancements
- Day 2: Documentation
- Day 3: Final testing
- Day 4: Deploy and monitor
- Day 5: Buffer for issues

---

## Success Metrics

### Minimum Viable (Pass):
- ✓ MEF platform working: 50 points
- ✓ Basic dashboard functional
- ✓ Documentation clear

### Target (Good):
- ✓ MEF perfect: 50 points
- ✓ 2 additional platforms: 40 points
- ✓ **Total: 90 points**
- ✓ Professional dashboard
- ✓ Comprehensive documentation

### Stretch (Excellent):
- ✓ MEF perfect: 50 points
- ✓ 4-5 additional platforms: 80-100 points
- ✓ **Total: 130-150 points**
- ✓ Advanced features (export, alerts)
- ✓ Production-ready code

---

## Final Checklist

Before submission:

### Code Quality
- [ ] All scrapers tested end-to-end
- [ ] No hardcoded credentials or paths
- [ ] Error handling on all external calls
- [ ] Logs are comprehensive but not spammy
- [ ] Code is commented (especially selectors)

### Functionality
- [ ] Level 1 data extracted accurately
- [ ] New tenders detected (no duplicates)
- [ ] Attachments downloaded and classified
- [ ] Level 2 data extracted (if API available)
- [ ] Update detection working
- [ ] Scheduler runs reliably

### Documentation
- [ ] README.md complete
- [ ] QUICKSTART.md with examples
- [ ] requirements.txt has all dependencies
- [ ] .env.example shows required variables
- [ ] Comments explain non-obvious code

### Presentation
- [ ] Dashboard looks professional
- [ ] Screenshots of working system
- [ ] Video demo (optional but impressive)
- [ ] Sample data in database
- [ ] No errors in console

---

## Getting Help

If stuck on specific issues:

1. **CSS Selectors:** Use browser DevTools Elements tab
2. **Playwright:** Add `headless=False` to see browser
3. **Database:** Use DB Browser for SQLite to inspect data
4. **Claude API:** Check examples at docs.anthropic.com
5. **Scheduling:** Test jobs manually first

**Remember:** Quality > Quantity

A **perfect MEF implementation (50 points)** beats **5 broken platforms (0-25 points)**

---

Good luck! 🚀 You've got all the code - now customize it and make it work!
