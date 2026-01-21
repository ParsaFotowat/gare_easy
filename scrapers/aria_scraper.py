"""
Aria (Lombardia) Platform Scraper - Sintel
Priority: 20 points

URL: https://www.sintel.regione.lombardia.it/eprocdata/arcaSearch.xhtml
"""
from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright, Page
from bs4 import BeautifulSoup
from loguru import logger
import time
import re
from datetime import datetime

from .base_scraper import BaseScraper


class AriaScraper(BaseScraper):
    """Scraper for Aria S.p.A. (Sintel) platform"""
    
    def get_platform_name(self) -> str:
        return "Aria"
    
    def get_base_url(self) -> str:
        return "https://www.sintel.regione.lombardia.it"
    
    def scrape_tenders(self) -> List[Dict[str, Any]]:
        tenders = []
        
        with sync_playwright() as p:
            browser, page = self.create_browser(p)
            
            try:
                # Aria / Sintel List Page
                url = f"{self.base_url}/eprocdata/arcaSearch.xhtml"
                logger.info(f"Navigating to {url}")
                page.goto(url, wait_until='networkidle', timeout=30000)
                
                # Check for cookies (if any)
                try:
                    page.locator("button:has-text('Accetto')").click(timeout=2000)
                except:
                    pass
                
                # Wait for table
                # The main table is usually usually id="resultTable" or similar in JSF
                page.wait_for_selector('table', timeout=15000)
                
                while True:
                    page_tenders = self._scrape_page(page)
                    tenders.extend(page_tenders)
                    
                    # Pagination
                    # Look for "Successiva" or ">"
                    # In JSF primefaces dataTable, usually a pager with class "ui-paginator-next"
                    next_btn = page.locator('.ui-paginator-next:not(.ui-state-disabled)')
                    
                    if next_btn.count() > 0 and next_btn.is_visible():
                        logger.info("Moving to next page")
                        next_btn.click()
                        # Wait for table update - simplistic way is sleep or wait for loading mask
                        time.sleep(2) 
                        page.wait_for_load_state('networkidle')
                    else:
                        break
                
                logger.info(f"Found {len(tenders)} total tenders on Aria platform")
                
            except Exception as e:
                logger.error(f"Error during Aria scraping: {e}", exc_info=True)
                raise
            finally:
                browser.close()
        
        return tenders

    def _scrape_page(self, page: Page) -> List[Dict[str, Any]]:
        tenders = []
        html = page.inner_html('body')
        soup = BeautifulSoup(html, 'html.parser')
        
        # Select rows. Usually tbody > tr using standard Primefaces/JSF classes
        rows = soup.select('table tbody tr')
        logger.info(f"Found {len(rows)} rows on current page")
        
        for row in rows:
            try:
                cols = row.find_all('td')
                if len(cols) < 4:
                    continue
                
                # Heuristic mapping based on observed Sintel structure
                # Col 0: ID / CIG
                # Col 1: Oggetto (Title + Link)
                # Col 2: Tipo (Procedure Type)
                # Col 3: Stazione Appaltante (Authority)
                # Col 4: Stato (Status)
                # Col 5: Importo (Amount) - Sometimes hidden or in different col
                # Col 6: Scadenza (Deadline)
                
                # CIG - Extract from first column
                cig_raw = cols[0].get_text(strip=True)
                # Often the CIG is the ARIA ID like "ARIA_2025_312_F" - use this as CIG
                cig = cig_raw if cig_raw else None
                
                # Title and Link - Col 1
                link_col = cols[1]
                link = link_col.find('a')
                if not link:
                    title = link_col.get_text(strip=True)
                    href = ""
                else:
                    title = link.get_text(strip=True)
                    href = link.get('href', '')

                # Full URL handle
                full_url = f"{self.base_url}/eprocdata/{href}" if 'http' not in href else href
                if 'javascript' in href or not href:
                     # Fallback to search page if detailed link is JS
                     full_url = f"{self.base_url}/eprocdata/arcaSearch.xhtml"

                # Get raw text from column 2 for analysis
                raw_col2 = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                
                # If Title is empty, try to extract from Col 2 (common issue in Sintel)
                if not title and raw_col2:
                    # Format often: "ARIA_CODE - Actual Title" or just "Actual Title"
                    if " - " in raw_col2:
                        parts = raw_col2.split(" - ", 1)
                        # Use the part after dash as title
                        title = parts[1].strip()
                    else:
                        title = raw_col2
                
                # Clean up title - remove incomplete sentences at end (indicated by lack of period)
                if title:
                    # If title ends mid-sentence (no period but has comma or space), it's likely truncated
                    # Keep it as-is but note this is common in Aria exports
                    title = title.strip()
                
                # Procedure Type detection
                # Check Col 2 text for procedure keywords
                proc_type = "Procedura aperta"  # Default
                search_text = (raw_col2 + " " + title).lower()
                
                if 'affidamento diretto' in search_text:
                    proc_type = "Affidamento diretto"
                elif 'procedura negoziata' in search_text or 'negoziata' in search_text:
                    proc_type = "Procedura negoziata"
                elif 'procedura aperta' in search_text or 'aperta' in search_text:
                    proc_type = "Procedura aperta"
                elif 'manifestazione' in search_text:
                    proc_type = "Manifestazione di interesse"
                elif 'richiesta' in search_text:
                    proc_type = "Richiesta di offerta"
                
                # Category detection from title keywords
                category = self._infer_category(title + " " + raw_col2)

                # Authority
                authority = cols[3].get_text(strip=True) if len(cols) > 3 else "Regione Lombardia"
                
                # Status
                status_text = cols[4].get_text(strip=True) if len(cols) > 4 else "Active"
                status = 'Active'
                if 'chius' in status_text.lower() or 'conclus' in status_text.lower():
                    status = 'Closed'
                
                # Amount
                amount = None
                if len(cols) > 5:
                    amount_text = cols[5].get_text(strip=True)
                    if '€' in amount_text or ',' in amount_text:
                         amount = self.sanitize_amount(amount_text)

                # Deadline
                deadline = None
                if len(cols) > 6:
                    deadline_text = cols[6].get_text(strip=True)
                    try:
                        deadline = self.parse_datetime(deadline_text)
                    except:
                        pass
                
                should_exclude = self.should_exclude_tender({'status': status, 'deadline': deadline})
                
                if not should_exclude:
                    tenders.append({
                        'title': title,
                        'url': full_url,
                        'cig': cig, 
                        'status': status,
                        'deadline': deadline,
                        'contracting_authority': authority,
                        'amount': amount,
                        'procedure_type': proc_type,
                        'category': category,
                        'place_of_execution': 'Lombardia',
                        'platform_name': self.platform_name,
                        'publication_date': datetime.now().date()
                    })
                    self.stats['found'] += 1
                    
            except Exception as e:
                logger.warning(f"Error parsing row: {e}")
                self.stats['errors'] += 1
                
        return tenders
    
    def _infer_category(self, text: str) -> str:
        """Infer tender category from text content"""
        if not text:
            return "Services"
        
        text_lower = text.lower()
        
        # Works keywords
        works_keywords = ['lavori', 'costruzione', 'ristrutturazione', 'manutenzione', 'edificio', 
                         'infrastruttura', 'strade', 'edile', 'impianto']
        if any(kw in text_lower for kw in works_keywords):
            return "Works"
        
        # Supplies keywords
        supplies_keywords = ['fornitura', 'forniture', 'acquisto', 'materiali', 'attrezzature',
                            'dispositivi', 'apparecchiature', 'beni', 'prodotti', 'medicazioni',
                            'farmaci', 'arredi', 'ausili']
        if any(kw in text_lower for kw in supplies_keywords):
            return "Supplies"
        
        # Services is default
        return "Services"
