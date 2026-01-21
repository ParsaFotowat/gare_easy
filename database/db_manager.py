"""
Database manager for CRUD operations and update detection.
"""
from sqlalchemy import create_engine, and_, or_
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date, timedelta
import hashlib

from .models import Tender, Level2Data, Attachment, ScraperLog, Base
from loguru import logger


class DatabaseManager:
    """Manages database operations for tender data"""
    
    def __init__(self, connection_string: str = 'sqlite:///data/gare_easy.db'):
        """
        Initialize database manager
        
        Args:
            connection_string: SQLAlchemy connection string
        """
        if 'sqlite' in connection_string:
            import os
            # Remove prefix to get path
            path = connection_string.replace('sqlite:///', '')
            # Get directory
            directory = os.path.dirname(path)
            # Create directory if it exists (is not empty string for current dir) and doesn't exist on disk
            if directory and not os.path.exists(directory):
                try:
                    os.makedirs(directory, exist_ok=True)
                    logger.info(f"Created database directory: {directory}")
                except Exception as e:
                    logger.error(f"Failed to create database directory {directory}: {e}")

        self.engine = create_engine(
            connection_string,
            echo=False,
            pool_pre_ping=True,
            connect_args={'check_same_thread': False} if 'sqlite' in connection_string else {}
        )
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)
        logger.info(f"Database initialized: {connection_string}")
    
    @contextmanager
    def get_session(self) -> Session:
        """Context manager for database sessions"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def generate_tender_id(self, tender_data: Dict[str, Any]) -> str:
        """Generate unique tender ID from CIG or create hash"""
        cig = tender_data.get('cig', '').strip()
        if cig:
            return f"CIG_{cig}"
        url = tender_data.get('url', '')
        title = tender_data.get('title', '')
        unique_string = f"{url}_{title}"
        hash_id = hashlib.md5(unique_string.encode()).hexdigest()[:16]
        return f"HASH_{hash_id}"
    
    def upsert_tender(self, tender_data: Dict[str, Any]) -> Tuple[str, bool]:
        """
        Insert new tender or update existing one
        
        Returns:
            Tuple of (tender_id, is_new: bool)
        """
        with self.get_session() as session:
            tender_id = self.generate_tender_id(tender_data)
            existing = session.query(Tender).filter_by(id=tender_id).first()
            attachments = tender_data.pop('attachments', [])
            tender_data.pop('cig', None)  # Remove cig from data as it's not a column
            
            if existing:
                has_changes = self._check_for_changes(existing, tender_data)
                if has_changes:
                    for key, value in tender_data.items():
                        if hasattr(existing, key) and key != 'id':
                            setattr(existing, key, value)
                    existing.last_updated_at = datetime.utcnow()
                    existing.status = 'Updated'
                    existing.data_quality_score = existing.calculate_quality_score()
                    logger.info(f"Updated tender: {tender_id}")
                    session.flush()
                    for att_data in attachments:
                        self.add_attachment(session, tender_id, att_data)
                    return tender_id, False
                else:
                    logger.debug(f"No changes detected for tender: {tender_id}")
                    return tender_id, False
            else:
                tender = Tender(id=tender_id, **tender_data)
                tender.data_quality_score = tender.calculate_quality_score()
                session.add(tender)
                session.flush()
                logger.info(f"Inserted new tender: {tender_id}")
                for att_data in attachments:
                    self.add_attachment(session, tender_id, att_data)
                return tender_id, True
    
    def _check_for_changes(self, existing_tender: Tender, new_data: Dict[str, Any]) -> bool:
        """Check if tender data has changed"""
        key_fields = [
            'title', 'amount', 'deadline', 'publication_date', 
            'status', 'procedure_type', 'contracting_authority'
        ]
        for field in key_fields:
            if field in new_data:
                old_value = getattr(existing_tender, field)
                new_value = new_data[field]
                
                # Handle date/datetime comparisons
                if isinstance(old_value, datetime) and isinstance(new_value, (datetime, date)):
                    old_date = old_value.date() if isinstance(old_value, datetime) else old_value
                    new_date = new_value.date() if isinstance(new_value, datetime) else new_value
                    if old_date != new_date:
                        return True
                elif isinstance(old_value, date) and isinstance(new_value, (datetime, date)):
                    old_date = old_value
                    new_date = new_value.date() if isinstance(new_value, datetime) else new_value
                    if old_date != new_date:
                        return True
                elif old_value != new_value:
                    return True
        return False
    
    def add_attachment(self, session: Session, tender_id: str, attachment_data: Dict[str, Any]) -> Optional[Attachment]:
        """Add attachment to a tender"""
        try:
            existing = session.query(Attachment).filter_by(
                tender_id=tender_id,
                file_url=attachment_data['file_url']
            ).first()
            if existing:
                return existing
            attachment = Attachment(tender_id=tender_id, **attachment_data)
            session.add(attachment)
            logger.debug(f"Added attachment: {attachment_data['file_name']}")
            return attachment
        except Exception as e:
            logger.error(f"Error adding attachment: {e}")
            return None
    
    def update_attachment_status(self, attachment_id: int, 
                                 downloaded: bool, 
                                 local_path: Optional[str] = None,
                                 error: Optional[str] = None):
        """Update attachment download status"""
        with self.get_session() as session:
            attachment = session.query(Attachment).filter_by(id=attachment_id).first()
            if attachment:
                attachment.downloaded = 1 if downloaded else -1
                attachment.download_date = datetime.utcnow()
                attachment.local_path = local_path
                attachment.download_error = error
                logger.debug(f"Updated attachment {attachment_id} status")
    
    def add_level2_data(self, tender_id: str, level2_data: Dict[str, Any]) -> Optional[Level2Data]:
        """Add or update Level 2 data for a tender"""
        with self.get_session() as session:
            existing = session.query(Level2Data).filter_by(tender_id=tender_id).first()
            if existing:
                for key, value in level2_data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                existing.extraction_date = datetime.utcnow()
                logger.info(f"Updated Level 2 data for: {tender_id}")
                return existing
            else:
                level2 = Level2Data(tender_id=tender_id, **level2_data)
                session.add(level2)
                logger.info(f"Added Level 2 data for: {tender_id}")
                return level2
    
    def log_scraper_run(self, log_data: Dict[str, Any]) -> ScraperLog:
        """Log a scraper run"""
        with self.get_session() as session:
            log = ScraperLog(**log_data)
            session.add(log)
            logger.debug(f"Logged scraper run: {log_data['platform_name']}")
            return log
    
    # ==================== QUERY METHODS ====================
    
    def get_tender_by_id(self, tender_id: str) -> Optional[Tender]:
        """Get tender by ID"""
        with self.get_session() as session:
            return session.query(Tender).filter_by(id=tender_id).first()
    
    def get_active_tenders(self, platform: Optional[str] = None) -> List[Tender]:
        """Get all active tenders"""
        with self.get_session() as session:
            query = session.query(Tender).filter_by(status='Active')
            if platform:
                query = query.filter_by(platform_name=platform)
            return query.order_by(Tender.deadline).all()
    
    def get_tenders_by_deadline(self, days_ahead: int = 30) -> List[Tender]:
        """Get tenders with upcoming deadlines"""
        cutoff = datetime.now() + timedelta(days=days_ahead)
        with self.get_session() as session:
            return session.query(Tender).filter(
                Tender.deadline <= cutoff,
                Tender.deadline >= datetime.now(),
                Tender.status == 'Active'
            ).order_by(Tender.deadline).all()
    
    def search_tenders(self, 
                      keyword: Optional[str] = None,
                      min_amount: Optional[float] = None,
                      max_amount: Optional[float] = None,
                      category: Optional[str] = None,
                      platform: Optional[str] = None,
                      status: Optional[str] = 'Active',
                      limit: int = 100,
                      offset: int = 0) -> Tuple[List[Tender], int]:
        """Search tenders with multiple filters"""
        with self.get_session() as session:
            query = session.query(Tender)
            if keyword:
                query = query.filter(
                    or_(
                        Tender.title.ilike(f"%{keyword}%"),
                        Tender.contracting_authority.ilike(f"%{keyword}%")
                    )
                )
            if min_amount is not None:
                query = query.filter(Tender.amount >= min_amount)
            if max_amount is not None:
                query = query.filter(Tender.amount <= max_amount)
            if category:
                query = query.filter(Tender.category.ilike(f"%{category}%"))
            if platform:
                query = query.filter_by(platform_name=platform)
            if status:
                query = query.filter_by(status=status)
            total = query.count()
            results = query.order_by(Tender.deadline.desc()).limit(limit).offset(offset).all()
            return results, total
    
    def get_recent_tenders(self, days: int = 7, platform: Optional[str] = None) -> List[Tender]:
        """Get tenders added/updated in the last N days"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        with self.get_session() as session:
            query = session.query(Tender).filter(Tender.last_updated_at >= cutoff)
            if platform:
                query = query.filter_by(platform_name=platform)
            return query.order_by(Tender.last_updated_at.desc()).all()
    
    def get_tenders_without_level2(self, platform: Optional[str] = None, limit: int = 10) -> List[Tender]:
        """Get tenders that don't have Level 2 data yet"""
        with self.get_session() as session:
            query = session.query(Tender).outerjoin(Level2Data).filter(
                Level2Data.tender_id.is_(None),
                Tender.status == 'Active'
            )
            if platform:
                query = query.filter(Tender.platform_name == platform)
            return query.limit(limit).all()
    
    def get_tenders_with_undownloaded_attachments(self, platform: Optional[str] = None, limit: int = 10) -> List[Tender]:
        """Get tenders that have attachments not yet downloaded"""
        with self.get_session() as session:
            query = session.query(Tender).join(Attachment).filter(
                Attachment.downloaded == 0
            )
            if platform:
                query = query.filter(Tender.platform_name == platform)
            return query.distinct().limit(limit).all()
    
    def get_attachments_by_tender(self, tender_id: str) -> List[Attachment]:
        """Get all attachments for a tender"""
        with self.get_session() as session:
            return session.query(Attachment).filter_by(tender_id=tender_id).all()
    
    def get_undownloaded_attachments(self, tender_id: Optional[str] = None) -> List[Attachment]:
        """Get attachments that haven't been downloaded yet"""
        with self.get_session() as session:
            query = session.query(Attachment).filter_by(downloaded=0)
            if tender_id:
                query = query.filter_by(tender_id=tender_id)
            return query.all()
    
    def get_level2_data(self, tender_id: str) -> Optional[Level2Data]:
        """Get Level 2 data for a tender"""
        with self.get_session() as session:
            return session.query(Level2Data).filter_by(tender_id=tender_id).first()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self.get_session() as session:
            total_tenders = session.query(Tender).count()
            active_tenders = session.query(Tender).filter_by(status='Active').count()
            closed_tenders = session.query(Tender).filter_by(status='Closed').count()
            total_attachments = session.query(Attachment).count()
            downloaded_attachments = session.query(Attachment).filter_by(downloaded=1).count()
            level2_count = session.query(Level2Data).count()
            
            from sqlalchemy import func
            platform_stats = session.query(
                Tender.platform_name,
                func.count(Tender.id).label('count')
            ).group_by(Tender.platform_name).all()
            
            avg_quality = session.query(
                func.avg(Tender.data_quality_score)
            ).scalar() or 0
            
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_count = session.query(Tender).filter(
                Tender.last_updated_at >= week_ago
            ).count()
            
            return {
                'total_tenders': total_tenders,
                'active_tenders': active_tenders,
                'closed_tenders': closed_tenders,
                'total_attachments': total_attachments,
                'downloaded_attachments': downloaded_attachments,
                'level2_extracted': level2_count,
                'avg_data_quality': round(float(avg_quality), 2),
                'recent_7days': recent_count,
                'platform_breakdown': {name: count for name, count in platform_stats}
            }
    
    def close_expired_tenders(self) -> int:
        """Mark tenders with past deadlines as Closed"""
        with self.get_session() as session:
            expired = session.query(Tender).filter(
                Tender.deadline < datetime.now(),
                Tender.status == 'Active'
            ).all()
            count = 0
            for tender in expired:
                tender.status = 'Closed'
                count += 1
            logger.info(f"Closed {count} expired tenders")
            return count
    
    def get_scraper_logs(self, platform: Optional[str] = None, limit: int = 100) -> List[ScraperLog]:
        """Get scraper execution logs"""
        with self.get_session() as session:
            query = session.query(ScraperLog)
            if platform:
                query = query.filter_by(platform_name=platform)
            return query.order_by(ScraperLog.run_start.desc()).limit(limit).all()
    
    def get_last_scraper_run(self, platform: str) -> Optional[ScraperLog]:
        """Get the last successful scraper run for a platform"""
        with self.get_session() as session:
            return session.query(ScraperLog).filter_by(
                platform_name=platform,
                status='Success'
            ).order_by(ScraperLog.run_start.desc()).first()


if __name__ == '__main__':
    import os
    os.makedirs('data', exist_ok=True)
    db = DatabaseManager()
    stats = db.get_statistics()
    print("Database Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
