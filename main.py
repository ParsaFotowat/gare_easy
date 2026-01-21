"""
Main entry point for Gare Easy tender scraper.
"""
import os
import sys
import argparse
import yaml
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from database import DatabaseManager, create_database
from scrapers import MEFScraper, ToscanaScraper, EmiliaScraper, AriaScraper
from processors import DocumentProcessor, AIProcessor
from scheduler import TenderScheduler


def setup_logging(log_file: str = "logs/scraper.log"):
    """Configure logging"""
    os.makedirs('logs', exist_ok=True)
    
    # Remove default logger
    logger.remove()
    
    # Add console logger
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # Add file logger
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="100 MB",
        retention="30 days",
        compression="zip"
    )
    
    logger.info("="*60)
    logger.info("GARE EASY - Public Procurement Tender Scraper")
    logger.info("="*60)


def load_config(config_path: str = "config/config.yaml") -> dict:
    """Load configuration from YAML file"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    logger.info(f"Configuration loaded from {config_path}")
    return config


def initialize_database(config: dict) -> DatabaseManager:
    """Initialize database"""
    db_path = config['database']['path']
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Create database schema
    create_database(f"sqlite:///{db_path}")
    
    # Initialize manager
    db_manager = DatabaseManager(f"sqlite:///{db_path}")
    
    # Show statistics
    stats = db_manager.get_statistics()
    logger.info(f"Database ready: {stats['total_tenders']} tenders, {stats['active_tenders']} active")
    
    return db_manager


def run_scraper(scraper_class, config: dict, db_manager: DatabaseManager, download_docs: bool = True, extract_level2: bool = True):
    """Run a specific platform scraper"""
    
    # Initialize scraper
    scraper = scraper_class(config, db_manager)
    platform_name = scraper.platform_name
    logger.info(f"Starting {platform_name} scraper")
    
    # Run scraper
    stats = scraper.run()
    
    logger.info(f"{platform_name} scraping complete:")
    logger.info(f"  Found: {stats['found']}")
    logger.info(f"  New: {stats['new']}")
    logger.info(f"  Updated: {stats['updated']}")
    logger.info(f"  Errors: {stats['errors']}")
    
    # Download documents
    if download_docs and (stats['new'] > 0 or stats['updated'] > 0): # Check updated too
        logger.info("Downloading attachments...")
        doc_processor = DocumentProcessor(config, db_manager)
        
        # Get tenders that need documents
        with db_manager.get_session() as session:
            from database.models import Tender, Attachment
            
            tenders = session.query(Tender).filter(
                Tender.platform_name == platform_name,
                Tender.status == 'Active'
            ).limit(20).all()  # Process in batches
            
            for tender in tenders:
                # Get attachments that haven't been downloaded
                attachments = session.query(Attachment).filter(
                    Attachment.tender_id == tender.id,
                    Attachment.downloaded == 0
                ).all()
                
                if attachments:
                    attachment_dicts = [{
                        'file_name': att.file_name,
                        'file_url': att.file_url,
                        'category': att.category
                    } for att in attachments]
                    
                    doc_processor.process_tender_attachments(tender.id, attachment_dicts)
    
    # Extract Level 2 data
    if extract_level2 and (stats['new'] > 0 or stats['updated'] > 0):
        logger.info("Extracting Level 2 data...")
        ai_processor = AIProcessor(config, db_manager)
        level2_stats = ai_processor.batch_process_tenders(limit=10)
        logger.info(f"Level 2 extraction: {level2_stats}")
    
    return stats


def run_all_scrapers(config: dict, db_manager: DatabaseManager, mode='once'):
    """Run all scrapers sequentially"""
    # MEF
    try:
        run_scraper(MEFScraper, config, db_manager)
    except Exception as e:
        logger.error(f"MEF Scraper failed: {e}")

    # Toscana
    try:
        run_scraper(ToscanaScraper, config, db_manager)
    except Exception as e:
        logger.error(f"Toscana Scraper failed: {e}")

    # Emilia
    try:
        run_scraper(EmiliaScraper, config, db_manager)
    except Exception as e:
        logger.error(f"Emilia Scraper failed: {e}")

    # Aria
    try:
        run_scraper(AriaScraper, config, db_manager)
    except Exception as e:
        logger.error(f"Aria Scraper failed: {e}")


def run_scheduled_mode(config: dict, db_manager: DatabaseManager):
    """Run scraper in scheduled mode (every 6 hours)"""
    logger.info("Starting scheduler mode (6-hour updates)")
    
    # Initialize scheduler
    scheduler = TenderScheduler(config)
    
    # Create scraper function
    def scrape_all():
        logger.info("Scheduled scraper run starting...")
        run_all_scrapers(config, db_manager)
        logger.info("Scheduled scraper run completed")
    
    # Add scraper job
    scheduler.add_scraper_job(scrape_all, "all_platforms")
    
    # Start scheduler
    scheduler.start()
    
    # Keep alive
    scheduler.keep_alive()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Gare Easy - Public Procurement Tender Scraper")
    
    parser.add_argument(
        '--platform',
        choices=['mef', 'aria', 'toscana', 'empulia', 'emilia', 'asmecomm', 'all'],
        default='mef',
        help='Platform to scrape (default: mef)'
    )
    
    parser.add_argument(
        '--mode',
        choices=['once', 'schedule'],
        default='once',
        help='Run mode: once (single run) or schedule (every 6 hours)'
    )
    
    parser.add_argument(
        '--no-docs',
        action='store_true',
        help='Skip document download'
    )
    
    parser.add_argument(
        '--no-level2',
        action='store_true',
        help='Skip Level 2 data extraction'
    )
    
    parser.add_argument(
        '--init-db',
        action='store_true',
        help='Initialize/reset database'
    )
    
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Setup logging
    setup_logging()
    
    # Load configuration
    config = load_config()
    
    # Initialize database
    db_manager = initialize_database(config)
    
    # Initialize database schema if requested
    if args.init_db:
        logger.info("Database initialized")
        return
    
    # Run based on mode
    if args.mode == 'schedule':
        run_scheduled_mode(config, db_manager)
    else:
        # Run once
        download = not args.no_docs
        level2 = not args.no_level2
        
        if args.platform == 'all':
            run_all_scrapers(config, db_manager)
        else:
            if args.platform == 'mef':
                run_scraper(MEFScraper, config, db_manager, download, level2)
            elif args.platform == 'toscana':
                run_scraper(ToscanaScraper, config, db_manager, download, level2)
            elif args.platform == 'emilia':
                run_scraper(EmiliaScraper, config, db_manager, download, level2)
            elif args.platform == 'aria':
                run_scraper(AriaScraper, config, db_manager, download, level2)
            else:
                logger.warning(f"Platform {args.platform} not implemented yet")
    
    logger.info("Scraper execution complete")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
