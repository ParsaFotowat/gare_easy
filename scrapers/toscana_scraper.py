"""
Toscana Platform Scraper - START
Priority: 20 points

URL: https://start.toscana.it/initiatives/list/
"""
from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright, Page
from bs4 import BeautifulSoup
from loguru import logger
import time
import re
from datetime import datetime

from .base_scraper import BaseScraper


class ToscanaScraper(BaseScraper):
    """Scraper for START Toscana platform"""
    
    def get_platform_name(self) -> str:
        return "Toscana"
    
    def get_base_url(self) -> str:
        return "https://start.toscana.it"
    
    def scrape_tenders(self) -> List[Dict[str, Any]]:
        """
        Scrape all tenders from START Toscana platform
        """
        tenders = []
        
        with sync_playwright() as p:
            browser, page = self.create_browser(p)
            
            try:
                # START Toscana URL
                url = f"{self.base_url}/initiatives/list/"
                logger.info(f"Navigating to {url}")
                page.goto(url, wait_until='networkidle', timeout=30000)
                
                # Check for "Accetta solo i cookies tecnici"
                try:
                    page.locator("button:has-text('Accetta solo i cookies tecnici')").click(timeout=2000)
                except:
                    pass
                
                # Wait for table
                page.wait_for_selector('table', timeout=10000)
                
                # Scrape pages
                while True:
                    page_tenders = self._scrape_page(page)
                    tenders.extend(page_tenders)
                    
                    # Next page?
                    next_btn = page.locator('a:has-text("Successivo")')
                    if next_btn.count() > 0 and next_btn.first.is_visible():
                        logger.info("Moving to next page")
                        next_btn.first.click()
                        page.wait_for_load_state('networkidle')
                        time.sleep(1)
                    else:
                        break
                        
                logger.info(f"Found {len(tenders)} total tenders on Toscana platform")
                
            except Exception as e:
                logger.error(f"Error during Toscana scraping: {e}", exc_info=True)
                raise
            finally:
                browser.close()
        
        return tenders

    def _scrape_page(self, page: Page) -> List[Dict[str, Any]]:
        tenders = []
        html = page.inner_html('body')
        soup = BeautifulSoup(html, 'html.parser')
        
        # Rows in the table
        rows = soup.select('table tbody tr')
        logger.info(f"Found {len(rows)} rows on current page")
        
        for row in rows:
            try:
                # Toscana table structure based on observation:
                # Cols: Type | Description | Category | CIG | Amount | Status | Deadline
                cols = row.find_all('td')
                if len(cols) < 7:
                    continue
                
                # Title and Authority are often in the second column (Description)
                desc_col = cols[1]
                title_link = desc_col.find('a')
                if not title_link:
                    continue
                
                title = title_link.get_text(strip=True)
                href = title_link.get('href')
                full_url = f"{self.base_url}{href}" if href.startswith('/') else href
                
                # Authority is often text before the link or separate div?
                # Usually text in col 1 is like "AUTHORITY - CODE - TITLE"
                full_text = desc_col.get_text(strip=True)
                
                # Extract Authority (heuristic: text before first dash or break)
                authority = "Regione Toscana" # Default
                if '-' in full_text:
                    authority = full_text.split('-')[0].strip()
                
                # CIG
                cig = cols[3].get_text(strip=True)
                
                # Amount
                amount_str = cols[4].get_text(strip=True)
                amount = self.sanitize_amount(amount_str)
                
                # Status
                status_text = cols[5].get_text(strip=True)
                if 'corso' in status_text.lower():
                    status = 'Active'
                elif 'chius' in status_text.lower() or 'scadut' in status_text.lower():
                    status = 'Closed'
                else:
                    status = 'Active' # Default
                    
                # Deadline
                deadline_str = cols[6].get_text(strip=True)
                deadline = self.parse_datetime(deadline_str)
                
                # Category
                category_text = cols[2].get_text(strip=True)
                category = self._map_category(category_text)
                
                # Procedure & Place - Not typically in main table, but we can default or guess
                proc_type = "Procedura aperta" # Most common
                place = "Toscana" # Implicit
                
                # Try to find procedure in description if available
                if "affidamento diretto" in title.lower():
                    proc_type = "Affidamento diretto"
                elif "negoziata" in title.lower():
                    proc_type = "Procedura negoziata"

                should_exclude = self.should_exclude_tender({'status': status, 'deadline': deadline})

                if not should_exclude:
                     tenders.append({
                        'title': title,
                        'url': full_url,
                        'cig': cig,
                        'amount': amount,
                        'status': status,
                        'deadline': deadline,
                        'contracting_authority': authority,
                        'category': category,
                        'procedure_type': proc_type,
                        'place_of_execution': place,
                        'platform_name': self.platform_name,
                        'publication_date': datetime.now().date() # Usually not in table
                    })
                     self.stats['found'] += 1
                
            except Exception as e:
                logger.warning(f"Error parsing row: {e}")
                self.stats['errors'] += 1
                
        return tenders

    def _map_category(self, text: str) -> str:
        text = text.lower()
        if 'lavori' in text: return 'Works'
        if 'scrivici' in text or 'forniture' in text: return 'Supplies' # "forniture"
        if 'servizi' in text: return 'Services'
        return 'Services'
