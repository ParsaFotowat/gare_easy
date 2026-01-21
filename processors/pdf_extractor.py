"""
PDF text extraction and analysis module.
Handles extracting text from PDF files for Level 2 AI processing.
"""
import pdfplumber
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from loguru import logger
import re


class PDFExtractor:
    """Extracts and processes text from PDF documents"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize PDF extractor
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.max_pages = config.get('documents', {}).get('max_pdf_pages', 20)
        self.min_text_length = config.get('documents', {}).get('min_text_length', 50)
        
        # Keywords to search for in documents
        self.qualification_keywords = [
            'requisiti', 'qualificazioni', 'qualifica', 'qualifiche',
            'certificazioni', 'certificazione', 'attestati', 'attestato',
            'iscrizione', 'iscrizioni', 'albo', 'qualità', 'norme iso',
            'certificato', 'patente', 'licenza', 'abilitazione'
        ]
        
        self.evaluation_keywords = [
            'valutazione', 'criteri', 'criterio', 'punteggio', 'punti',
            'offerta', 'valutativo', 'aggiudicazione', 'priorità',
            'soglia', 'minimo', 'massimo', 'qualitativo', 'quantitativo',
            'sorteggio', 'selezione'
        ]
        
        self.process_keywords = [
            'procedimento', 'procedura', 'processo', 'fasi', 'fase',
            'modalità', 'fase di valutazione', 'commissione', 'commissario',
            'responsabile', 'svolgimento', 'calendario', 'cronoprogramma'
        ]
        
        self.delivery_keywords = [
            'consegna', 'consegne', 'tempi di consegna', 'durata', 'termine',
            'scadenza', 'esecuzione', 'realizzazione', 'deliverable',
            'luogo di consegna', 'sede di esecuzione', 'cantiere'
        ]
        
        logger.info(f"PDF extractor initialized (max {self.max_pages} pages per document)")
    
    def extract_text_from_pdf(self, pdf_path: Path, max_pages: Optional[int] = None) -> Optional[str]:
        """
        Extract all text from a PDF file
        
        Args:
            pdf_path: Path to PDF file
            max_pages: Maximum pages to extract (overrides config)
            
        Returns:
            Extracted text or None if extraction fails
        """
        if not pdf_path.exists():
            logger.warning(f"PDF file not found: {pdf_path}")
            return None
        
        max_pages = max_pages or self.max_pages
        
        try:
            extracted_text = []
            
            with pdfplumber.open(pdf_path) as pdf:
                pages_to_extract = min(len(pdf.pages), max_pages)
                logger.debug(f"Extracting from {pages_to_extract}/{len(pdf.pages)} pages: {pdf_path.name}")
                
                for i, page in enumerate(pdf.pages[:pages_to_extract]):
                    try:
                        text = page.extract_text()
                        if text and len(text.strip()) > self.min_text_length:
                            extracted_text.append(text)
                    except Exception as e:
                        logger.warning(f"Error extracting page {i+1} from {pdf_path.name}: {e}")
                        continue
            
            if extracted_text:
                full_text = '\n\n'.join(extracted_text)
                logger.debug(f"Extracted {len(full_text)} characters from {pdf_path.name}")
                return full_text
            else:
                logger.warning(f"No text extracted from {pdf_path.name}")
                return None
        
        except Exception as e:
            logger.error(f"Failed to extract text from {pdf_path}: {e}")
            return None
    
    def analyze_document(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Analyze document and extract structured information
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with analysis results
        """
        text = self.extract_text_from_pdf(pdf_path)
        
        if not text:
            return {
                'file_name': pdf_path.name,
                'success': False,
                'error': 'Could not extract text',
                'text': None,
                'qualifications': None,
                'evaluation_criteria': None,
                'process_description': None,
                'delivery_methods': None
            }
        
        # Convert to lowercase for searching
        text_lower = text.lower()
        
        # Find relevant sections
        qualifications = self._extract_section(text_lower, self.qualification_keywords)
        evaluation_criteria = self._extract_section(text_lower, self.evaluation_keywords)
        process_desc = self._extract_section(text_lower, self.process_keywords)
        delivery = self._extract_section(text_lower, self.delivery_keywords)
        
        return {
            'file_name': pdf_path.name,
            'success': True,
            'error': None,
            'text': text,
            'qualifications': qualifications,
            'evaluation_criteria': evaluation_criteria,
            'process_description': process_desc,
            'delivery_methods': delivery,
            'text_length': len(text),
            'sections_found': sum(1 for x in [qualifications, evaluation_criteria, process_desc, delivery] if x)
        }
    
    def _extract_section(self, text: str, keywords: List[str], context_lines: int = 5) -> Optional[str]:
        """
        Extract section of text containing keywords
        
        Args:
            text: Full text to search
            keywords: Keywords to look for
            context_lines: Number of lines of context to extract
            
        Returns:
            Extracted section or None
        """
        lines = text.split('\n')
        matches = []
        
        # Find lines containing keywords
        for i, line in enumerate(lines):
            for keyword in keywords:
                if keyword in line:
                    # Get surrounding context
                    start = max(0, i - context_lines)
                    end = min(len(lines), i + context_lines + 1)
                    context = '\n'.join(lines[start:end])
                    
                    if context not in matches:
                        matches.append(context)
                    break
        
        if matches:
            # Combine all matches with some deduplication
            combined = '\n\n'.join(matches)
            
            # Clean up - remove excessive whitespace
            combined = re.sub(r'\n\s*\n\s*\n+', '\n\n', combined)
            combined = combined.strip()
            
            # Limit length
            max_length = 2000
            if len(combined) > max_length:
                combined = combined[:max_length] + '...'
            
            return combined if len(combined) > 100 else None
        
        return None
    
    def extract_from_tender_attachments(self, tender_id: str, attachment_paths: List[Path]) -> Dict[str, Any]:
        """
        Extract text and analysis from all attachments for a tender
        
        Args:
            tender_id: Tender ID
            attachment_paths: List of PDF file paths
            
        Returns:
            Dictionary with combined analysis
        """
        results = {
            'tender_id': tender_id,
            'documents_processed': 0,
            'documents_failed': 0,
            'total_text_length': 0,
            'qualifications': [],
            'evaluation_criteria': [],
            'process_description': [],
            'delivery_methods': [],
            'document_analyses': []
        }
        
        for pdf_path in attachment_paths:
            if not pdf_path.suffix.lower() == '.pdf':
                continue
            
            try:
                analysis = self.analyze_document(pdf_path)
                
                if analysis['success']:
                    results['documents_processed'] += 1
                    results['total_text_length'] += analysis['text_length']
                    results['document_analyses'].append(analysis)
                    
                    # Aggregate findings
                    if analysis['qualifications']:
                        results['qualifications'].append({
                            'source': pdf_path.name,
                            'content': analysis['qualifications']
                        })
                    
                    if analysis['evaluation_criteria']:
                        results['evaluation_criteria'].append({
                            'source': pdf_path.name,
                            'content': analysis['evaluation_criteria']
                        })
                    
                    if analysis['process_description']:
                        results['process_description'].append({
                            'source': pdf_path.name,
                            'content': analysis['process_description']
                        })
                    
                    if analysis['delivery_methods']:
                        results['delivery_methods'].append({
                            'source': pdf_path.name,
                            'content': analysis['delivery_methods']
                        })
                else:
                    results['documents_failed'] += 1
                    logger.warning(f"Failed to analyze {pdf_path.name}: {analysis['error']}")
            
            except Exception as e:
                results['documents_failed'] += 1
                logger.error(f"Error processing {pdf_path}: {e}")
        
        logger.info(f"Tender {tender_id}: Processed {results['documents_processed']} PDFs, "
                   f"extracted {results['total_text_length']} chars total")
        
        return results
    
    def prepare_for_ai_processing(self, analysis: Dict[str, Any]) -> Dict[str, str]:
        """
        Prepare extracted analysis for Claude API processing
        
        Args:
            analysis: Analysis result from extract_from_tender_attachments
            
        Returns:
            Dictionary with aggregated text for each category
        """
        return {
            'required_qualifications': self._aggregate_section(analysis.get('qualifications', [])),
            'evaluation_criteria': self._aggregate_section(analysis.get('evaluation_criteria', [])),
            'process_description': self._aggregate_section(analysis.get('process_description', [])),
            'delivery_methods': self._aggregate_section(analysis.get('delivery_methods', [])),
            'raw_text': '\n\n'.join([
                doc['text'] for doc in analysis.get('document_analyses', [])
                if doc.get('text') and len(doc['text']) > 500
            ])[:50000]  # Limit to 50K chars for API
        }
    
    def _aggregate_section(self, section_list: List[Dict[str, str]]) -> Optional[str]:
        """
        Aggregate multiple section findings into single text
        
        Args:
            section_list: List of dictionaries with 'source' and 'content' keys
            
        Returns:
            Aggregated text or None
        """
        if not section_list:
            return None
        
        aggregated = []
        for item in section_list:
            source = item.get('source', 'Unknown')
            content = item.get('content', '').strip()
            if content:
                aggregated.append(f"[From {source}]\n{content}")
        
        if aggregated:
            result = '\n\n---\n\n'.join(aggregated)
            # Limit to 3000 chars per section
            if len(result) > 3000:
                result = result[:3000] + '...'
            return result
        
        return None


if __name__ == '__main__':
    # Test PDF extractor
    import yaml
    
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    extractor = PDFExtractor(config)
    
    # Test with a sample PDF if it exists
    sample_pdf = Path('data/downloads').glob('*/*.pdf')
    for pdf in sample_pdf:
        print(f"\nAnalyzing: {pdf.name}")
        analysis = extractor.analyze_document(pdf)
        print(f"Text length: {analysis['text_length']}")
        print(f"Sections found: {analysis['sections_found']}")
        if analysis['qualifications']:
            print(f"Qualifications: {analysis['qualifications'][:200]}...")
        break
