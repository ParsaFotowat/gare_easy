"""
Document processor for downloading and managing tender attachments.
Scores: 10 points (MEF) + 4 points per additional platform
"""
import os
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger
from .pdf_extractor import PDFExtractor


class DocumentProcessor:
    """Handles downloading and organizing tender documents"""
    
    def __init__(self, config: Dict[str, Any], db_manager):
        """
        Initialize document processor
        
        Args:
            config: Configuration dictionary
            db_manager: DatabaseManager instance
        """
        self.config = config
        self.db_manager = db_manager
        
        # Settings
        self.download_path = Path(config.get('documents', {}).get('download_path', 'data/downloads'))
        self.max_file_size = config.get('documents', {}).get('max_file_size_mb', 50) * 1024 * 1024
        self.allowed_extensions = config.get('documents', {}).get('allowed_extensions', [
            'pdf', 'doc', 'docx', 'xls', 'xlsx', 'zip', 'rar'
        ])
        self.timeout = config.get('scraper', {}).get('download_timeout', 60)
        
        # Create base download directory
        self.download_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Document processor initialized: {self.download_path}")
        
        # Initialize PDF extractor
        self.pdf_extractor = PDFExtractor(config)
    
    def process_tender_attachments(self, tender_id: str, attachments: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Download all attachments for a tender
        
        Args:
            tender_id: Tender ID
            attachments: List of attachment dictionaries
            
        Returns:
            Statistics dictionary
        """
        stats = {
            'total': len(attachments),
            'downloaded': 0,
            'failed': 0,
            'skipped': 0
        }
        
        # Create tender-specific folder
        tender_folder = self.download_path / self._sanitize_filename(tender_id)
        tender_folder.mkdir(parents=True, exist_ok=True)
        
        for attachment in attachments:
            try:
                # Store attachment metadata in database first
                attachment_obj = self.db_manager.add_attachment(tender_id, {
                    'file_name': attachment['file_name'],
                    'file_url': attachment['file_url'],
                    'category': attachment.get('category', 'Informative'),
                    'classification_confidence': attachment.get('classification_confidence', 0.5)
                })
                
                # Download file
                success, local_path, error = self._download_file(
                    attachment['file_url'],
                    tender_folder,
                    attachment['file_name']
                )
                
                # Update attachment status in database
                if success:
                    self.db_manager.update_attachment_status(
                        attachment_obj.id,
                        downloaded=True,
                        local_path=str(local_path)
                    )
                    stats['downloaded'] += 1
                    logger.debug(f"Downloaded: {attachment['file_name']}")
                else:
                    self.db_manager.update_attachment_status(
                        attachment_obj.id,
                        downloaded=False,
                        error=error
                    )
                    stats['failed'] += 1
                    logger.warning(f"Failed to download: {attachment['file_name']} - {error}")
            
            except Exception as e:
                logger.error(f"Error processing attachment {attachment.get('file_name')}: {e}")
                stats['failed'] += 1
        
        logger.info(f"Attachment processing complete for {tender_id}: {stats}")
        return stats
    
    def _download_file(self, url: str, folder: Path, filename: str) -> tuple[bool, Optional[Path], Optional[str]]:
        """
        Download a single file
        
        Args:
            url: File URL
            folder: Destination folder
            filename: File name
            
        Returns:
            Tuple of (success, local_path, error_message)
        """
        try:
            # Validate URL
            if not url or not url.startswith('http'):
                return False, None, "Invalid URL"
            
            # Check file extension
            ext = self._get_file_extension(filename)
            if ext and ext not in self.allowed_extensions:
                return False, None, f"Extension {ext} not allowed"
            
            # Generate safe filename
            safe_filename = self._sanitize_filename(filename)
            local_path = folder / safe_filename
            
            # Skip if already exists
            if local_path.exists():
                file_size = local_path.stat().st_size
                if file_size > 0:
                    logger.debug(f"File already exists: {safe_filename}")
                    return True, local_path, None
            
            # Download with streaming to handle large files
            logger.debug(f"Downloading: {url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, stream=True, timeout=self.timeout)
            response.raise_for_status()
            
            # Check file size from headers
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > self.max_file_size:
                return False, None, f"File too large: {int(content_length) / 1024 / 1024:.1f} MB"
            
            # Download in chunks
            downloaded_size = 0
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # Check size limit during download
                        if downloaded_size > self.max_file_size:
                            local_path.unlink()  # Delete partial file
                            return False, None, "File size exceeded during download"
            
            logger.debug(f"Downloaded {downloaded_size / 1024:.1f} KB: {safe_filename}")
            return True, local_path, None
        
        except requests.exceptions.Timeout:
            return False, None, "Download timeout"
        except requests.exceptions.HTTPError as e:
            return False, None, f"HTTP error: {e.response.status_code}"
        except requests.exceptions.RequestException as e:
            return False, None, f"Request error: {str(e)}"
        except Exception as e:
            return False, None, f"Unexpected error: {str(e)}"
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Create safe filename by removing/replacing invalid characters
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        # Replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Remove leading/trailing spaces and dots
        filename = filename.strip('. ')
        
        # Limit length
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:195] + ext
        
        return filename
    
    def _get_file_extension(self, filename: str) -> Optional[str]:
        """Get file extension without dot"""
        ext = os.path.splitext(filename)[1]
        return ext[1:].lower() if ext else None
    
    def get_tender_documents(self, tender_id: str) -> List[Path]:
        """
        Get list of downloaded documents for a tender
        
        Args:
            tender_id: Tender ID
            
        Returns:
            List of Path objects
        """
        tender_folder = self.download_path / self._sanitize_filename(tender_id)
        
        if not tender_folder.exists():
            return []
        
        # Get all files
        files = []
        for ext in self.allowed_extensions:
            files.extend(tender_folder.glob(f"*.{ext}"))
        
        return sorted(files)
    
    def classify_document(self, filename: str) -> tuple[str, float]:
        """
        Classify document as Informative or Compilable
        
        Args:
            filename: Document filename
            
        Returns:
            Tuple of (category, confidence)
        """
        filename_lower = filename.lower()
        
        # Get keywords from config
        compilable_keywords = self.config.get('documents', {}).get('compilable_keywords', [])
        informative_keywords = self.config.get('documents', {}).get('informative_keywords', [])
        
        # Check compilable keywords
        compilable_score = sum(1 for kw in compilable_keywords if kw.lower() in filename_lower)
        
        # Check informative keywords
        informative_score = sum(1 for kw in informative_keywords if kw.lower() in filename_lower)
        
        if compilable_score > informative_score:
            confidence = min(0.9, 0.5 + (compilable_score * 0.2))
            return 'Compilable', confidence
        elif informative_score > compilable_score:
            confidence = min(0.9, 0.5 + (informative_score * 0.2))
            return 'Informative', confidence
        else:
            # Default to Informative with low confidence
            return 'Informative', 0.5
    
    def get_download_statistics(self) -> Dict[str, Any]:
        """Get statistics about downloaded documents"""
        stats = self.db_manager.get_statistics()
        
        # Calculate storage size
        total_size = 0
        for folder in self.download_path.iterdir():
            if folder.is_dir():
                for file in folder.rglob('*'):
                    if file.is_file():
                        total_size += file.stat().st_size
        
        stats['storage_size_mb'] = total_size / 1024 / 1024
        
        return stats

    def download_pending_attachments(self, tender_id: str) -> Dict[str, int]:
        """Download attachments stored in DB that are not yet downloaded"""
        stats = {'total': 0, 'downloaded': 0, 'failed': 0, 'skipped': 0}

        tender_folder = self.download_path / self._sanitize_filename(tender_id)
        tender_folder.mkdir(parents=True, exist_ok=True)

        pending = self.db_manager.get_undownloaded_attachments(tender_id)
        stats['total'] = len(pending)

        for att in pending:
            try:
                success, local_path, error = self._download_file(att.file_url, tender_folder, att.file_name)
                if success:
                    self.db_manager.update_attachment_status(att.id, True, str(local_path), None)
                    stats['downloaded'] += 1
                else:
                    self.db_manager.update_attachment_status(att.id, False, error=error)
                    stats['failed'] += 1
            except Exception as exc:
                logger.error(f"Error downloading {att.file_name}: {exc}")
                self.db_manager.update_attachment_status(att.id, False, error=str(exc))
                stats['failed'] += 1

        logger.info(f"Downloaded {stats['downloaded']} of {stats['total']} attachments for {tender_id}")
        return stats
    
    def extract_text_from_tender_attachments(self, tender_id: str) -> Dict[str, Any]:
        """
        Extract and analyze text from all downloaded attachments for a tender
        
        Args:
            tender_id: Tender ID
            
        Returns:
            Dictionary with extracted information
        """
        # Get downloaded files for this tender
        pdf_files = self.get_tender_documents(tender_id)
        
        if not pdf_files:
            logger.warning(f"No PDF documents found for tender {tender_id}")
            return {
                'tender_id': tender_id,
                'success': False,
                'error': 'No PDF documents found',
                'analysis': None
            }
        
        try:
            # Extract from all PDFs
            analysis = self.pdf_extractor.extract_from_tender_attachments(tender_id, pdf_files)
            
            logger.info(f"Extracted text from {analysis['documents_processed']} PDFs for tender {tender_id}")
            
            return {
                'tender_id': tender_id,
                'success': True,
                'error': None,
                'analysis': analysis
            }
        
        except Exception as e:
            logger.error(f"Error extracting text from tender {tender_id}: {e}")
            return {
                'tender_id': tender_id,
                'success': False,
                'error': str(e),
                'analysis': None
            }
    
    def prepare_text_for_ai_processing(self, tender_id: str) -> Optional[Dict[str, str]]:
        """
        Extract text from tender attachments and prepare for Claude API processing
        
        Args:
            tender_id: Tender ID
            
        Returns:
            Dictionary with structured text for AI, or None if no text extracted
        """
        extraction_result = self.extract_text_from_tender_attachments(tender_id)
        
        if not extraction_result['success']:
            logger.warning(f"Could not extract text from {tender_id}: {extraction_result['error']}")
            return None
        
        analysis = extraction_result['analysis']
        
        # Prepare for AI processing
        ai_input = self.pdf_extractor.prepare_for_ai_processing(analysis)
        
        # Add raw text if no structured sections found
        if not any([ai_input['required_qualifications'], ai_input['evaluation_criteria'], 
                    ai_input['process_description'], ai_input['delivery_methods']]):
            logger.debug(f"No structured sections found for {tender_id}, using raw text")
        
        return ai_input if ai_input['raw_text'] else None


if __name__ == '__main__':
    # Test document processor
    import yaml
    
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    from database.db_manager import DatabaseManager
    db = DatabaseManager()
    
    processor = DocumentProcessor(config, db)
    print(f"Document processor ready. Download path: {processor.download_path}")
