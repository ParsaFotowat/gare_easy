"""
Base scraper class with common functionality for all platform scrapers.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime, date
import re
from loguru import logger
from playwright.sync_api import sync_playwright, Page, Browser
import time

from processors.document_processor import DocumentProcessor
from processors.ai_processor import AIProcessor


class BaseScraper(ABC):
    """Abstract base class for tender platform scrapers"""
    
    def __init__(self, config: Dict[str, Any], db_manager):
        """
        Initialize scraper
        
        Args:
            config: Configuration dictionary
            db_manager: DatabaseManager instance
        """
        self.config = config
        self.db_manager = db_manager
        self.platform_name = self.get_platform_name()
        self.base_url = self.get_base_url()
        
        # Scraper settings
        self.headless = config.get('scraper', {}).get('headless', True)
        self.timeout = config.get('scraper', {}).get('timeout_seconds', 30) * 1000
        self.max_retries = config.get('scraper', {}).get('max_retries', 3)

        # Helpers
        self.document_processor = DocumentProcessor(config, db_manager)
        self.ai_processor = AIProcessor(config, db_manager)
        self.level2_enabled = config.get('level2', {}).get('enabled', True)
        
        # Statistics
        self.stats = {
            'found': 0,
            'new': 0,
            'updated': 0,
            'errors': 0,
            'attachments': 0
        }
        
        logger.info(f"Initialized {self.platform_name} scraper")
    
    @abstractmethod
    def get_platform_name(self) -> str:
        """Return the platform name identifier"""
        pass
    
    @abstractmethod
    def get_base_url(self) -> str:
        """Return the base URL for the platform"""
        pass
    
    @abstractmethod
    def scrape_tenders(self) -> List[Dict[str, Any]]:
        """
        Main scraping method - must be implemented by each platform
        
        Returns:
            List of tender dictionaries
        """
        pass
    
    def run(self) -> Dict[str, Any]:
        """
        Execute the scraping process
        
        Returns:
            Statistics dictionary
        """
        run_start = datetime.utcnow()
        logger.info(f"Starting {self.platform_name} scraper")
        
        try:
            # Run platform-specific scraping
            tenders = self.scrape_tenders()
            
            # Process each tender
            for tender_data in tenders:
                try:
                    self._process_tender(tender_data)
                except Exception as e:
                    logger.error(f"Error processing tender: {e}")
                    self.stats['errors'] += 1
            
            # Close expired tenders
            self.db_manager.close_expired_tenders()
            
            # Log successful run
            run_end = datetime.utcnow()
            self.db_manager.log_scraper_run({
                'platform_name': self.platform_name,
                'run_start': run_start,
                'run_end': run_end,
                'status': 'Success',
                'tenders_found': self.stats['found'],
                'tenders_new': self.stats['new'],
                'tenders_updated': self.stats['updated'],
                'attachments_downloaded': self.stats['attachments'],
                'errors_count': self.stats['errors']
            })
            
            logger.info(f"Scraper completed: {self.stats}")
            return self.stats
            
        except Exception as e:
            logger.error(f"Scraper failed: {e}", exc_info=True)
            run_end = datetime.utcnow()
            self.db_manager.log_scraper_run({
                'platform_name': self.platform_name,
                'run_start': run_start,
                'run_end': run_end,
                'status': 'Failed',
                'errors_count': 1,
                'error_details': str(e)
            })
            raise
    
    def _process_tender(self, tender_data: Dict[str, Any]):
        """Process and store a single tender"""
        self.stats['found'] += 1
        
        # Upsert tender to database
        tender_id, is_new = self.db_manager.upsert_tender(tender_data)
        
        if is_new:
            self.stats['new'] += 1
        else:
            # Check if it was an update
            tender = self.db_manager.get_tender_by_id(tender_id)
            if tender and tender.status == 'Updated':
                self.stats['updated'] += 1

        # Download attachments that are stored but not yet downloaded
        try:
            download_stats = self.document_processor.download_pending_attachments(tender_id)
            self.stats['attachments'] += download_stats.get('downloaded', 0)
        except Exception as e:
            logger.error(f"Attachment download failed for {tender_id}: {e}")
            self.stats['errors'] += 1

        # Run AI Level 2 extraction if enabled
        if self.level2_enabled:
            try:
                self.ai_processor.process_tender(tender_id)
            except Exception as e:
                logger.error(f"AI processing failed for {tender_id}: {e}")
                self.stats['errors'] += 1
    
    def sanitize_amount(self, amount_str: str) -> Optional[float]:
        """
        Convert Italian currency format to float
        
        Args:
            amount_str: String like "€ 1.500.000,00" or "1.500.000,00"
            
        Returns:
            Float value or None
        """
        if not amount_str or amount_str.strip() == '':
            return None
        
        try:
            # Remove currency symbols and whitespace
            cleaned = re.sub(r'[€\s]', '', amount_str)
            # Remove thousand separators (dots)
            cleaned = cleaned.replace('.', '')
            # Replace decimal comma with dot
            cleaned = cleaned.replace(',', '.')
            return float(cleaned)
        except (ValueError, AttributeError):
            logger.warning(f"Could not parse amount: {amount_str}")
            return None
    
    def parse_date(self, date_str: str) -> Optional[date]:
        """
        Parse Italian date format to date object
        
        Args:
            date_str: Date string like "31/12/2024" or "31-12-2024"
            
        Returns:
            date object or None
        """
        if not date_str or date_str.strip() == '':
            return None
        
        formats = [
            '%d/%m/%Y',
            '%d-%m-%Y',
            '%d/%m/%Y %H:%M',
            '%d-%m-%Y %H:%M',
            '%Y-%m-%d',
            '%d/%m/%y'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue
        
        logger.warning(f"Could not parse date: {date_str}")
        return None
    
    def parse_datetime(self, datetime_str: str) -> Optional[datetime]:
        """Parse datetime string"""
        if not datetime_str or datetime_str.strip() == '':
            return None
        
        formats = [
            '%d/%m/%Y %H:%M:%S',
            '%d/%m/%Y %H:%M',
            '%d-%m-%Y %H:%M:%S',
            '%d-%m-%Y %H:%M',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(datetime_str.strip(), fmt)
            except ValueError:
                continue
        
        # Try parsing as date and convert to datetime
        parsed_date = self.parse_date(datetime_str)
        if parsed_date:
            return datetime.combine(parsed_date, datetime.min.time())
        
        logger.warning(f"Could not parse datetime: {datetime_str}")
        return None
    
    def extract_cig(self, text: str) -> Optional[str]:
        """
        Extract CIG code from text
        
        Args:
            text: Text containing CIG
            
        Returns:
            CIG code or None
        """
        if not text:
            return None
        
        # CIG format: 10 alphanumeric characters
        match = re.search(r'\b([A-Z0-9]{10})\b', text.upper())
        if match:
            return match.group(1)
        
        return None
    
    def should_exclude_tender(self, tender_data: Dict[str, Any]) -> bool:
        """
        Check if tender should be excluded based on filters
        
        Args:
            tender_data: Tender information dictionary
            
        Returns:
            True if should be excluded
        """
        # Get exclusion filters from config
        exclude_types = self.config.get('filters', {}).get('exclude_types', [])
        only_open = self.config.get('filters', {}).get('only_open_tenders', True)
        
        # Check procedure type
        procedure_type = tender_data.get('procedure_type', '').lower()
        if not procedure_type:
             # If procedure_type is missing, we can't filter by it. Assuming safe to include?
             # Or maybe we should log this?
             pass

        for exclude_type in exclude_types:
            if not exclude_type: continue
            if exclude_type.lower() in procedure_type:
                logger.debug(f"Excluding tender - type: '{procedure_type}' matches '{exclude_type}'")
                return True
        
        # Check if tender is still open
        if only_open:
            deadline = tender_data.get('deadline')
            if deadline:
                now = datetime.now()
                # Ensure deadline is datetime
                if isinstance(deadline, date) and not isinstance(deadline, datetime):
                    deadline = datetime.combine(deadline, datetime.min.time())
                
                if deadline < now:
                    # Special case: if deadline is today and time is 00:00 (likely inferred from date only), keep it
                    if deadline.date() == now.date() and deadline.hour == 0 and deadline.minute == 0:
                        pass
                    else:
                        logger.debug(f"Excluding tender - deadline passed: {deadline} < {now}")
                        return True
        
        return False
    
    def wait_random(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Wait random time to avoid detection"""
        import random
        time.sleep(random.uniform(min_sec, max_sec))
    
    def create_browser(self, playwright) -> tuple[Browser, Page]:
        """Create browser and page with common settings"""
        browser = playwright.chromium.launch(
            headless=self.headless,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        
        page = context.new_page()
        page.set_default_timeout(self.timeout)
        
        return browser, page
