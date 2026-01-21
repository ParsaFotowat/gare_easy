"""
MEF Platform Scraper - Ministry of Economy and Finance
Priority: 50 points - COMPLETE FIRST

URL: https://www.acquistinretepa.it/opencms/opencms/vetrina_bandi.html
"""
from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright, Page
from bs4 import BeautifulSoup
from loguru import logger
import time
import re
from datetime import datetime

from .base_scraper import BaseScraper


class MEFScraper(BaseScraper):
    """Scraper for MEF (acquistinretepa.it) platform"""
    
    def get_platform_name(self) -> str:
        return "MEF"
    
    def get_base_url(self) -> str:
        return "https://www.acquistinretepa.it"
    
    def scrape_tenders(self) -> List[Dict[str, Any]]:
        """
        Scrape all tenders from MEF platform
        
        Returns:
            List of tender dictionaries with Level 1 data
        """
        tenders = []
        
        with sync_playwright() as p:
            browser, page = self.create_browser(p)
            
            try:
                logger.info(f"Navigating to MEF tender listing page")
                page.goto(f"{self.base_url}/opencms/opencms/vetrina_bandi.html", 
                         wait_until='networkidle', timeout=30000)
                
                # Wait for the tender list to load - MEF uses h3 headings for tender titles
                page.wait_for_selector('h3', timeout=30000)
                logger.info("Page loaded successfully")
                
                # Scrape all tenders from the main page
                tenders.extend(self._scrape_tender_list(page))
                
                # Handle pagination if present
                tenders.extend(self._handle_pagination(page))
                
                logger.info(f"Found {len(tenders)} total tenders on MEF platform")
                
            except Exception as e:
                logger.error(f"Error during MEF scraping: {e}", exc_info=True)
                raise
            finally:
                browser.close()
        
        return tenders
    
    def _scrape_tender_list(self, page: Page) -> List[Dict[str, Any]]:
        """
        Scrape tenders from the current page
        
        Args:
            page: Playwright page object
            
        Returns:
            List of tender dictionaries
        """
        tenders = []
        
        try:
            html = page.inner_html('body')
            soup = BeautifulSoup(html, 'html.parser')
            
            # MEF tenders are displayed as h3 headings with links
            # Pattern: <h3><a href="/opencms/opencms/scheda_bando.html?idBando=...">Title</a></h3>
            tender_headings = soup.find_all('h3')
            
            logger.info(f"Found {len(tender_headings)} tender headings on current page")
            
            for idx, heading in enumerate(tender_headings):
                try:
                    # Extract link from heading
                    link = heading.find('a')
                    if not link:
                        continue
                    
                    title = link.get_text(strip=True)
                    detail_url = link.get('href', '')
                    
                    # Make URL absolute
                    if detail_url and not detail_url.startswith('http'):
                        detail_url = f"{self.base_url}{detail_url}"
                    
                    if not detail_url:
                        continue
                    
                    # Extract metadata from the text following the heading
                    # It contains: dates, CIG, category, instrument, status
                    metadata_text = heading.find_next().get_text() if heading.find_next() else ''
                    
                    # Basic info for row
                    tender_info = {
                        'title': title,
                        'url': detail_url,
                        'platform_name': self.platform_name
                    }
                    
                    # Extract basic fields from metadata
                    tender_info['cig'] = self.extract_cig(metadata_text)
                    
                    # Parse dates: "Attivo dal DD/MM/YYYY al DD/MM/YYYY"
                    date_match = re.search(r'Attivo dal\s+(\d{1,2}/\d{1,2}/\d{4})\s*al\s+(\d{1,2}/\d{1,2}/\d{4})', metadata_text)
                    if date_match:
                        tender_info['publication_date'] = self.parse_date(date_match.group(1))
                        tender_info['deadline'] = self.parse_date(date_match.group(2))
                    
                    # Extract instrument type (AQ, SDA, MePA, CONVENZIONI, etc.)
                    instrument_match = re.search(r'Strumento:\s*(\w+)', metadata_text)
                    if instrument_match:
                        tender_info['procedure_type'] = instrument_match.group(1)
                    
                    # Status (Bando attivo)
                    if 'Bando attivo' in metadata_text:
                        tender_info['status'] = 'Active'
                    elif 'Bando chiuso' in metadata_text or 'Chiuso' in metadata_text:
                        tender_info['status'] = 'Closed'
                    
                    # Open detail page for full data
                    new_page = page.context.new_page()
                    try:
                        full_data = self._scrape_tender_detail(new_page, tender_info)
                        
                        if not self.should_exclude_tender(full_data):
                            tenders.append(full_data)
                            logger.debug(f"Scraped tender: {full_data.get('title', 'Unknown')[:60]}")
                            self.stats['found'] += 1
                    finally:
                        new_page.close()
                    
                    # Polite delay between requests
                    self.wait_random(0.5, 1.5)
                
                except Exception as e:
                    logger.error(f"Error processing tender {idx}: {e}")
                    self.stats['errors'] += 1
                    continue
        
        except Exception as e:
            logger.error(f"Error scraping tender list: {e}")
        
        return tenders
    
    def _scrape_category(self, page: Page, category_name: str) -> List[Dict[str, Any]]:
        """
        DEPRECATED: This method is kept for compatibility but not used.
        Use _scrape_tender_list instead.
        """
        logger.warning(f"_scrape_category is deprecated, use _scrape_tender_list")
        return []
    
    def _handle_pagination(self, page: Page) -> List[Dict[str, Any]]:
        """
        Handle pagination to scrape all tenders across pages
        
        Args:
            page: Playwright page object
            
        Returns:
            List of tenders from additional pages
        """
        tenders = []
        
        try:
            # Look for pagination controls - MEF shows "1 - 20 di 29 risultati" with next page link
            while True:
                # Try to find "Next" button
                next_link = page.locator('a:has-text("Successivo")').or_(
                    page.locator('a:has-text("Next")')
                )
                
                if not next_link or not next_link.is_visible():
                    logger.info("No more pages to scrape")
                    break
                
                logger.info("Moving to next page")
                
                # Click next page
                next_link.click()
                
                # Wait for page to load
                page.wait_for_load_state('networkidle')
                time.sleep(1)
                
                # Scrape tenders from this page
                page_tenders = self._scrape_tender_list(page)
                tenders.extend(page_tenders)
                
                logger.info(f"Scraped {len(page_tenders)} tenders from page")
        
        except Exception as e:
            logger.error(f"Error handling pagination: {e}")
        
        return tenders
    
    def _extract_row_data(self, row) -> Optional[Dict[str, Any]]:
        """
        DEPRECATED: This method is kept for compatibility but not used.
        Tender data is now extracted directly in _scrape_tender_list.
        """
        return None
    
    def _scrape_tender_detail(self, page: Page, base_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scrape full tender details from detail page
        
        Args:
            page: Playwright page object
            base_data: Basic data from list page (includes 'url')
            
        Returns:
            Complete tender data dictionary
        """
        url = base_data.get('url')
        logger.debug(f"Scraping detail page: {url}")
        
        try:
            page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Wait for content to load
            page.wait_for_selector('h1', timeout=10000)
            
            html = page.inner_html('body')
            soup = BeautifulSoup(html, 'html.parser')
            
            # Initialize with base data
            tender_data = base_data.copy()
            
            # MEF detail page structure analysis:
            # The page contains metadata in structured <dt>/<dd> or label/value pairs
            # Let's look for key information
            
            # Extract text content for parsing
            page_text = soup.get_text()
            
            # Category - look for "Categoria", "Oggetto", "Merceologia"
            # Default to extracting from title if not found
            category_match = re.search(r'(?:Categoria|Merceologia)\s*:?\s*([^\n]+)', page_text, re.IGNORECASE)
            if category_match:
                tender_data['category'] = category_match.group(1).strip()
            # If still None, try to guess from title or other fields
            if not tender_data.get('category'):
               title = tender_data.get('title', '').lower()
               if 'lavori' in title or 'realizzazione' in title or 'costruzione' in title:
                   tender_data['category'] = 'Works'
               elif 'fornitura' in title or 'acquisto' in title:
                   tender_data['category'] = 'Supplies'
               elif 'servizi' in title or 'manutenzione' in title:
                   tender_data['category'] = 'Services'
               else:
                   tender_data['category'] = 'Services' # Default fallback due to service-heavy nature of MEF

            
            # Procedure type - look for "Procedura" or "Tipo di procedura"
            proc_match = re.search(r'(?:Procedura|Tipo di procedura)\s*:?\s*([^\n]+)', page_text, re.IGNORECASE)
            if proc_match:
                tender_data['procedure_type'] = proc_match.group(1).strip()
            
            # Place of execution - look for "Luogo" or "Luogo di esecuzione"
            place_match = re.search(r'(?:Luogo|Luogo di esecuzione)\s*:?\s*([^\n]+)', page_text, re.IGNORECASE)
            if place_match:
                tender_data['place_of_execution'] = place_match.group(1).strip()
            
            # Contracting authority - look for "Stazione appaltante" or "Ente" (excluding "Ente di appartenenza")
            auth_match = re.search(r'(?:Stazione appaltante|Ente(?!\s+di\s+appartenenza))\s*:?\s*([^\n]+)', page_text, re.IGNORECASE)
            if auth_match:
                val = auth_match.group(1).strip()
                if "appartenenza" not in val.lower():
                     tender_data['contracting_authority'] = val
            
            # Amount - look for "Valore", "Importo"
            amount_match = re.search(r'(?:Importo|Valore|Stima)\s*(?:a base d\'asta|complessivo|presunto)?\s*[:\.]?\s*(?:€|EUR)?\s*([\d\.\,]+)', page_text, re.IGNORECASE)
            if amount_match:
                amount_str = amount_match.group(1)
                # Clean amount string
                amount_clean = amount_str.replace('.', '').replace(',', '.')
                try:
                    tender_data['amount'] = float(amount_clean)
                except:
                    pass

            # CPV codes - look for "CPV" codes (format: 12345678)
            cpv_matches = re.findall(r'(?:CPV|cpv)\s*[:\-]?\s*(\d{8})', page_text)
            if cpv_matches:
                tender_data['cpv_codes'] = ', '.join([m.strip() for m in cpv_matches[:3]])  # Take first 3
            
            # Sector type - look for "Ordinario" or "Speciale"
            sector_match = re.search(r'(?:Settore|Ordinario|Speciale)\s*:?\s*(Ordinario|Speciale)', page_text, re.IGNORECASE)
            if sector_match:
                tender_data['sector_type'] = sector_match.group(1)
            
            # Evaluation date / Public session date - look for "Seduta pubblica"
            eval_match = re.search(r'Seduta pubblica\s*:?\s*(\d{1,2}/\d{1,2}/\d{4}(?:\s+\d{1,2}:\d{2})?)', page_text, re.IGNORECASE)
            if eval_match:
                tender_data['evaluation_date'] = self.parse_datetime(eval_match.group(1))
            
            # Award criterion - look for "Criterio di aggiudicazione"
            award_match = re.search(r'(?:Criterio|Aggiudicazione)\s*:?\s*([^\n]+)', page_text, re.IGNORECASE)
            if award_match:
                tender_data['award_criterion'] = award_match.group(1).strip()
            
            # Contract duration - look for "Durata" or "Durata del contratto"
            duration_match = re.search(r'(?:Durata|Durata del contratto)\s*:?\s*([^\n]+)', page_text, re.IGNORECASE)
            if duration_match:
                tender_data['contract_duration'] = duration_match.group(1).strip()
            
            # Number of lots - look for "Lotti" or "Numero di lotti"
            lots_match = re.search(r'(?:Lotti|Numero di lotti)\s*:?\s*(\d+)', page_text, re.IGNORECASE)
            if lots_match:
                tender_data['num_lots'] = int(lots_match.group(1))
            
            # Email - look for mailto links or email patterns
            email_elem = soup.find('a', href=lambda h: h and h.startswith('mailto:'))
            if email_elem:
                email = email_elem.get_text(strip=True)
                tender_data['email'] = email
            else:
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', page_text)
                if email_match:
                    tender_data['email'] = email_match.group(0)
            
            # RUP name - look for "RUP" or "Responsabile Unico del Procedimento"
            rup_match = re.search(r'(?:RUP|Responsabile Unico del Procedimento)\s*:?\s*([^\n]+)', page_text, re.IGNORECASE)
            if rup_match:
                tender_data['rup_name'] = rup_match.group(1).strip()
            
            # Extract CIG if not already found
            if not tender_data.get('cig'):
                tender_data['cig'] = self.extract_cig(page_text)
            
            # Extract attachments
            attachments = self._extract_attachments(soup, page, tender_data.get('cig', 'unknown'))
            tender_data['attachments'] = attachments
            
            # Calculate data quality score
            tender_data['data_quality_score'] = self._calculate_quality_score(tender_data)
            
            return tender_data
        
        except Exception as e:
            logger.error(f"Error scraping detail page {url}: {e}")
            tender_data = base_data.copy()
            tender_data['data_quality_score'] = self._calculate_quality_score(tender_data)
            return tender_data
    
    def _calculate_quality_score(self, tender_data: Dict[str, Any]) -> float:
        """
        Calculate data completeness score (0-100)
        
        Args:
            tender_data: Tender data dictionary
            
        Returns:
            Quality score percentage
        """
        important_fields = [
            'title', 'amount', 'procedure_type', 'category',
            'place_of_execution', 'contracting_authority', 'cpv_codes',
            'publication_date', 'deadline', 'award_criterion',
            'email', 'rup_name'
        ]
        
        filled = sum(1 for field in important_fields if tender_data.get(field))
        return (filled / len(important_fields)) * 100
    
    def _extract_attachments(self, soup: BeautifulSoup, page: Page, cig: str) -> List[Dict[str, Any]]:
        """
        Extract attachment information from tender detail page
        
        Args:
            soup: BeautifulSoup object of detail page
            page: Playwright page (for additional navigation if needed)
            cig: CIG code for organizing downloads
            
        Returns:
            List of attachment dictionaries
        """
        attachments = []
        
        try:
            # MEF has a "Documentazione" section with downloadable files
            # Look for links with file extensions
            all_links = soup.find_all('a')
            
            file_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip', '.rar', '.txt', '.rtf']
            
            for link in all_links:
                href = link.get('href', '')
                file_name = link.get_text(strip=True)
                
                # Check if this looks like a document link
                if not href or not any(ext in href.lower() for ext in file_extensions):
                    continue
                
                # Make URL absolute
                if href and not href.startswith('http'):
                    href = f"{self.base_url}{href}"
                
                # Skip if no file name
                if not file_name or file_name == href:
                    file_name = href.split('/')[-1]
                
                # Classify attachment
                category = self._classify_attachment(file_name)
                
                attachments.append({
                    'file_name': file_name,
                    'file_url': href,
                    'category': category,
                    'classification_confidence': 0.7
                })
            
            logger.debug(f"Found {len(attachments)} attachments")
        
        except Exception as e:
            logger.error(f"Error extracting attachments: {e}")
        
        return attachments
    
    def _classify_attachment(self, file_name: str) -> str:
        """
        Classify attachment as Informative or Compilable
        
        Args:
            file_name: Name of the file
            
        Returns:
            'Informative' or 'Compilable'
        """
        compilable_keywords = self.config.get('documents', {}).get('compilable_keywords', [])
        
        file_lower = file_name.lower()
        
        for keyword in compilable_keywords:
            if keyword.lower() in file_lower:
                return 'Compilable'
        
        return 'Informative'

