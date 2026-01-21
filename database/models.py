"""
Database models for Gare Easy tender management system.
"""
from sqlalchemy import (
    Column, String, Float, Integer, DateTime, Text, Date, 
    ForeignKey, create_engine, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Tender(Base):
    """Main tender information (Level 1 data)"""
    __tablename__ = 'tenders'
    
    # Primary identifier - CIG or generated hash
    id = Column(String(50), primary_key=True)
    
    # Core tender information
    title = Column(Text, nullable=False)
    amount = Column(Float)  # Total tender amount
    procedure_type = Column(String(100))  # Open procedure, RDO, etc.
    category = Column(String(50))  # Services, Works, Consulting
    place_of_execution = Column(String(200))
    contracting_authority = Column(Text)
    
    # Platform information
    platform_name = Column(String(50), nullable=False, index=True)
    cpv_codes = Column(Text)  # Comma-separated CPV codes
    
    # Dates
    publication_date = Column(Date, index=True)
    deadline = Column(DateTime, index=True)
    evaluation_date = Column(DateTime)
    
    # Additional details
    sector_type = Column(String(20))  # Ordinary/Special
    url = Column(Text, nullable=False)
    award_criterion = Column(String(100))  # Lowest price / MEAT
    contract_duration = Column(String(100))
    num_lots = Column(Integer)
    email = Column(String(200))
    rup_name = Column(String(200))  # Responsabile Unico di Progetto
    
    # Status tracking for update detection
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String(20), default='Active', index=True)  # Active, Closed, Updated
    
    # Data completeness indicator
    data_quality_score = Column(Float)  # 0-100, based on filled fields
    
    # Relationships
    level2_data = relationship("Level2Data", back_populates="tender", uselist=False, cascade="all, delete-orphan")
    attachments = relationship("Attachment", back_populates="tender", cascade="all, delete-orphan")
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_platform_deadline', 'platform_name', 'deadline'),
        Index('idx_status_deadline', 'status', 'deadline'),
    )
    
    def calculate_quality_score(self):
        """Calculate data completeness score (0-100)"""
        fields = [
            self.title, self.amount, self.procedure_type, self.category,
            self.place_of_execution, self.contracting_authority, self.cpv_codes,
            self.publication_date, self.deadline, self.sector_type, self.award_criterion,
            self.contract_duration, self.num_lots, self.email, self.rup_name, self.evaluation_date
        ]
        filled = sum(1 for f in fields if f is not None and str(f).strip())
        return (filled / len(fields)) * 100


class Level2Data(Base):
    """AI-extracted data from tender documents (Level 2)"""
    __tablename__ = 'level2_data'
    
    tender_id = Column(String(50), ForeignKey('tenders.id'), primary_key=True)
    
    # Extracted paragraphs
    required_qualifications = Column(Text)  # Minimum turnover, certifications, experience
    evaluation_criteria = Column(Text)  # Scoring parameters, weights, thresholds
    process_description = Column(Text)  # Application steps, envelope structure
    delivery_methods = Column(Text)  # Contract details, advances, guarantees
    required_documentation = Column(Text)  # Documents to submit, formats, signatures
    
    # Metadata
    extraction_date = Column(DateTime, default=datetime.utcnow)
    confidence_score = Column(Float)  # AI confidence in extraction
    source_documents = Column(Text)  # Comma-separated list of analyzed files
    
    # Relationship
    tender = relationship("Tender", back_populates="level2_data")


class Attachment(Base):
    """Tender documents and attachments"""
    __tablename__ = 'attachments'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    tender_id = Column(String(50), ForeignKey('tenders.id'), nullable=False, index=True)
    
    # File information
    file_name = Column(String(500), nullable=False)
    file_url = Column(Text, nullable=False)
    local_path = Column(Text)  # Path where file is stored locally
    file_size_bytes = Column(Integer)
    
    # Classification
    category = Column(String(20))  # 'Informative' or 'Compilable'
    classification_confidence = Column(Float)
    
    # Status
    downloaded = Column(Integer, default=0)  # 0=not downloaded, 1=downloaded, -1=failed
    download_date = Column(DateTime)
    download_error = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    tender = relationship("Tender", back_populates="attachments")


class ScraperLog(Base):
    """Log of scraper runs for monitoring and debugging"""
    __tablename__ = 'scraper_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform_name = Column(String(50), nullable=False, index=True)
    
    # Run details
    run_start = Column(DateTime, default=datetime.utcnow, nullable=False)
    run_end = Column(DateTime)
    status = Column(String(20))  # Success, Failed, Partial
    
    # Statistics
    tenders_found = Column(Integer, default=0)
    tenders_new = Column(Integer, default=0)
    tenders_updated = Column(Integer, default=0)
    attachments_downloaded = Column(Integer, default=0)
    level2_extracted = Column(Integer, default=0)
    
    # Error tracking
    errors_count = Column(Integer, default=0)
    error_details = Column(Text)
    
    __table_args__ = (
        Index('idx_platform_runstart', 'platform_name', 'run_start'),
    )


def create_database(connection_string: str = 'sqlite:///data/gare_easy.db'):
    """Create all tables in the database"""
    engine = create_engine(connection_string, echo=False)
    Base.metadata.create_all(engine)
    return engine


if __name__ == '__main__':
    # Create database with all tables
    import os
    os.makedirs('data', exist_ok=True)
    engine = create_database()
    print("✓ Database schema created successfully!")
    print(f"  - Tables: {', '.join(Base.metadata.tables.keys())}")
