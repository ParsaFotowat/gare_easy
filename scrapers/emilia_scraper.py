"""
Emilia-Romagna Platform Scraper - Intercent-ER
Priority: 20 points

URL: https://intercenter.regione.emilia-romagna.it/bandi-e-strumenti-di-acquisto/bandi-intercenter/bandi-e-procedure-di-gara
"""
from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright, Page
from bs4 import BeautifulSoup
from loguru import logger
import time
import re
from datetime import datetime

from .base_scraper import BaseScraper


class EmiliaScraper(BaseScraper):
    """Scraper for Intercent-ER (Emilia-Romagna) platform"""
    
    def get_platform_name(self) -> str:
        return "Emilia"
    
    def get_base_url(self) -> str:
        return "https://intercenter.regione.emilia-romagna.it"
    
    def scrape_tenders(self) -> List[Dict[str, Any]]:
        tenders = []
        
        with sync_playwright() as p:
            browser, page = self.create_browser(p)
            
            try:
                # Intercent-ER list page
                url = f"{self.base_url}/bandi-e-strumenti-di-acquisto/bandi-intercenter/bandi-e-procedure-di-gara"
                logger.info(f"Navigating to {url}")
                page.goto(url, wait_until='networkidle', timeout=30000)
                
                # Check cookie banner
                try:
                    page.locator("button:has-text('Accetta solo i cookies tecnici')").click(timeout=2000)
                except:
                    pass
                
                html = page.inner_html('body')
                soup = BeautifulSoup(html, 'html.parser')
                
                # The page has sections. We are interested in "Bandi Intercent-ER APERTI"
                # But HTML structure might be just a list of divs
                # Based on fetch_webpage: ### [Link](Url) ... Published ...
                
                # Find all tender items (usually contained in some article container)
                # We'll look for headings h3 which contain the links
                items = soup.find_all('h3')
                
                for item in items:
                    try:
                        link = item.find('a')
                        if not link:
                            continue
                            
                        title = link.get_text(strip=True)
                        href = link.get('href')
                        full_url = href if href.startswith('http') else f"{self.base_url}{href}"
                        
                        # Metadata is usually in the next sibling (paragraph)
                        # "Pubblicato il:23-12-2025 Scadenza partecipazione:02-02-2026 Stato: APERTO"
                        meta_node = item.find_next_sibling()
                        meta_text = meta_node.get_text(strip=True) if meta_node else ""
                        
                        # Parse dates and status
                        tender_info = {
                            'title': title,
                            'url': full_url,
                            'platform_name': self.platform_name,
                            'contracting_authority': 'Regione Emilia-Romagna' # Default
                        }
                        
                        # Status
                        if 'APERTO' in meta_text or 'IN CORSO' in meta_text:
                            tender_info['status'] = 'Active'
                        elif 'CHIUSO' in meta_text:
                            tender_info['status'] = 'Closed'
                        else:
                            tender_info['status'] = 'Active'

                        # Dates
                        # Pubblicato il:DD-MM-YYYY
                        pub_match = re.search(r'Pubblicato il\s*:\s*(\d{2}-\d{2}-\d{4})', meta_text)
                        if pub_match:
                            # Use parse_datetime to ensure datetime object (sets time to midnight)
                            tender_info['publication_date'] = self.parse_datetime(pub_match.group(1).replace('-', '/'))
                            
                        # Scadenza partecipazione:DD-MM-YYYY
                        dead_match = re.search(r'Scadenza partecipazione\s*:\s*(\d{2}-\d{2}-\d{4})', meta_text)
                        if dead_match:
                            tender_info['deadline'] = self.parse_datetime(dead_match.group(1).replace('-', '/'))
                        
                        if self.should_exclude_tender(tender_info):
                            continue
                            
                        # Visit detail page for CIG, Amount, etc
                        new_page = page.context.new_page()
                        try:
                            detail_data = self._scrape_detail(new_page, tender_info)
                            tenders.append(detail_data)
                            self.stats['found'] += 1
                        except Exception as e:
                            logger.error(f"Error scraping detail for {title}: {e}")
                            # Add partial data
                            tenders.append(tender_info)
                        finally:
                            new_page.close()
                            
                        self.wait_random(0.5, 1.0)
                        
                    except Exception as e:
                        logger.warning(f"Error parsing item: {e}")
                        self.stats['errors'] += 1
                
                logger.info(f"Found {len(tenders)} tenders on Emilia platform")

            except Exception as e:
                logger.error(f"Error during Emilia scraping: {e}", exc_info=True)
                raise
            finally:
                browser.close()
                
        return tenders

    def _scrape_detail(self, page: Page, base_data: Dict[str, Any]) -> Dict[str, Any]:
        url = base_data.get('url')
        page.goto(url, wait_until='networkidle', timeout=30000)
        
        html = page.inner_html('body')
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text()
        
        data = base_data.copy()
        
        # CIG
        cig_match = re.search(r'CIG\s*:?\s*(\w+)', text, re.IGNORECASE)
        if cig_match:
            data['cig'] = cig_match.group(1)
            
        # Amount
        # "Importo a base d'asta: € 1.200.000,00"
        amount_match = re.search(r'Importo.*(?:€|Eur)\s*([\d.,]+)', text, re.IGNORECASE)
        if amount_match:
            data['amount'] = self.sanitize_amount(amount_match.group(1))
            
        # Place of execution
        place_match = re.search(r'(?:Luogo|Sede)\s*(?:di esecuzione)?\s*[:\.]?\s*([^\n]+)', text, re.IGNORECASE)
        if place_match:
            data['place_of_execution'] = place_match.group(1).strip()
        else:
            data['place_of_execution'] = "Emilia-Romagna" # Default

        # CPV
        cpv_match = re.search(r'CPV\s*[:\.]?\s*(\d{8})', text, re.IGNORECASE)
        if cpv_match:
            data['cpv_codes'] = cpv_match.group(1)
            
        # Award criterion
        award_match = re.search(r'(?:Criterio|Aggiudicazione)\s*[:\.]?\s*([^\n]+)', text, re.IGNORECASE)
        if award_match:
            data['award_criterion'] = award_match.group(1).strip()
            
        # Category (Inferred from title)
        title_lower = data['title'].lower()
        if 'lavori' in title_lower or 'costruzione' in title_lower or 'ristrutturazione' in title_lower or 'manutenzione' in title_lower:
            data['category'] = 'Works'
        elif 'fornitura' in title_lower or 'forniture' in title_lower or 'acquisto' in title_lower or 'materiali' in title_lower or 'beni' in title_lower:
            data['category'] = 'Supplies'
        else:
            data['category'] = 'Services'
        
        # Procedure type (inferred from title)
        if 'affidamento diretto' in title_lower:
            data['procedure_type'] = 'Affidamento diretto'
        elif 'negoziata' in title_lower:
            data['procedure_type'] = 'Procedura negoziata'
        else:
            data['procedure_type'] = data.get('procedure_type', 'Procedura aperta')
        
        return data
