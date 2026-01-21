"""
AI Processor for extracting Level 2 data from tender documents using Claude.
Depends on PDF extraction output to build structured Level 2 fields.
"""
import os
import json
import time
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover
    genai = None
    logger.warning("google-generativeai not installed - AI processing disabled")

from processors.pdf_extractor import PDFExtractor


class AIProcessor:
    """Processes tender documents with Claude AI to extract Level 2 data"""

    def __init__(self, config: Dict[str, Any], db_manager):
        self.config = config
        self.db_manager = db_manager
        self.pdf_extractor = PDFExtractor(config)

        self.model = config.get('level2', {}).get('model', 'gemini-2.0-flash')
        self.max_output_tokens = config.get('level2', {}).get('max_output_tokens', 3000)
        self.temperature = config.get('level2', {}).get('temperature', 0.1)

        api_key = os.getenv('GOOGLE_API_KEY') or config.get('level2', {}).get('api_key')
        if not api_key:
            logger.warning("GOOGLE_API_KEY not set - Level 2 extraction disabled")
            self.client = None
        elif not genai:
            logger.warning("google-generativeai library not available - Level 2 extraction disabled")
            self.client = None
        else:
            genai.configure(api_key=api_key)
            self.client = genai.GenerativeModel(self.model)
            logger.info("Google Gemini AI client initialized")

    def process_tender(self, tender_id: str) -> Optional[Dict[str, Any]]:
        """Extract Level 2 data for a single tender using downloaded PDFs"""
        if not self.client:
            logger.warning("AI client not available - skipping Level 2 extraction")
            return None

        attachments = self.db_manager.get_attachments_by_tender(tender_id)
        pdf_paths: List[Path] = []
        for att in attachments:
            try:
                if getattr(att, 'downloaded', 0) != 1:
                    continue
                if not att.local_path:
                    continue
                path = Path(att.local_path)
                if path.suffix.lower() != '.pdf':
                    continue
                if not path.exists():
                    logger.debug(f"PDF missing on disk: {path}")
                    continue
                pdf_paths.append(path)
            except Exception as exc:  # pragma: no cover
                logger.debug(f"Skipping attachment due to error: {exc}")
                continue

        if not pdf_paths:
            logger.info(f"No downloaded PDFs available for {tender_id}")
            return None

        analysis = self.pdf_extractor.extract_from_tender_attachments(tender_id, pdf_paths)
        if not analysis or analysis.get('documents_processed', 0) == 0:
            logger.info(f"No text extracted from PDFs for {tender_id}")
            return None

        ai_input = self.pdf_extractor.prepare_for_ai_processing(analysis)
        if not ai_input:
            logger.info(f"No AI input prepared for {tender_id}")
            return None

        response_data = self._call_gemini(ai_input)
        if not response_data:
            return None

        level2_record = {
            'required_qualifications': response_data.get('required_qualifications', 'Not Found'),
            'evaluation_criteria': response_data.get('evaluation_criteria', 'Not Found'),
            'process_description': response_data.get('process_description', 'Not Found'),
            'delivery_methods': response_data.get('delivery_methods', 'Not Found'),
            'required_documentation': response_data.get('required_documentation', 'Not Found'),
            'confidence_score': float(response_data.get('confidence_score', 0.7)),
        }

        self.db_manager.add_level2_data(tender_id, level2_record)
        logger.info(f"Level 2 data stored for {tender_id}")
        return level2_record

    def batch_process_tenders(self, platform: Optional[str] = None, limit: int = 5) -> Dict[str, int]:
        """Process multiple tenders without Level 2 data"""
        if not self.client:
            logger.warning("AI client not available - skipping batch process")
            return {'processed': 0, 'success': 0, 'failed': 0}

        stats = {'processed': 0, 'success': 0, 'failed': 0}
        tenders = self.db_manager.get_tenders_without_level2(platform=platform, limit=limit)
        logger.info(f"Batch Level 2: found {len(tenders)} tenders to process")

        for tender in tenders:
            result = self.process_tender(tender.id)
            stats['processed'] += 1
            if result:
                stats['success'] += 1
                # Rate limit protection: sleep between successful requests
                time.sleep(4) 
            else:
                stats['failed'] += 1

        logger.info(f"Batch Level 2 complete: {stats}")
        return stats

    def _call_gemini(self, ai_input: Dict[str, Optional[str]], retries=3) -> Optional[Dict[str, Any]]:
        """Send extraction request to Gemini and parse response"""
        prompt = self._build_prompt(ai_input)
        
        for attempt in range(retries):
            try:
                generation_config = genai.types.GenerationConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_output_tokens
                )
                response = self.client.generate_content(
                    prompt,
                    generation_config=generation_config
                )
                response_text = response.text
                return self._parse_response(response_text)
            except Exception as exc:
                error_str = str(exc)
                if "429" in error_str and attempt < retries - 1:
                    # Parse wait time from error message
                    wait_time = 30 # Default
                    match = re.search(r'retry in ([\d\.]+)s', error_str)
                    if match:
                        wait_time = float(match.group(1)) + 2 # Add 2s buffer
                    
                    logger.warning(f"Quota exceeded (429). Retrying in {wait_time:.1f}s... (Attempt {attempt+1}/{retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Gemini API call failed: {exc}")
                    return None
        return None

    def _build_prompt(self, ai_input: Dict[str, Optional[str]]) -> str:
        """Construct prompt with structured sections for extraction"""
        sections = []
        sections.append("You are an expert in Italian public procurement. Extract the requested fields in JSON.")
        sections.append("Return ONLY valid JSON with keys: required_qualifications, evaluation_criteria, process_description, delivery_methods, required_documentation, confidence_score (0.0-1.0). If a field is missing, set it to 'Not Found'.")
        sections.append("Focus on concrete values: scores, percentages, deadlines, ISO/ SOA certifications, payment terms, submission modalities (platform/PEC), envelope structure (Busta A/B/C), guarantees/anticipi.")
        sections.append("Use concise Italian where appropriate. Do not invent data.")

        def block(label: str, text: Optional[str]) -> str:
            if not text:
                return f"<{label}>Not Provided</{label}>"
            return f"<{label}>\n{text}\n</{label}>"

        content_blocks = [
            block('qualifications', ai_input.get('required_qualifications')),
            block('evaluation', ai_input.get('evaluation_criteria')),
            block('process', ai_input.get('process_description')),
            block('delivery', ai_input.get('delivery_methods')),
            block('raw_text', ai_input.get('raw_text')),
        ]

        prompt = "\n\n".join(sections + content_blocks)
        return prompt

    def _parse_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from Gemini response"""
        try:
            cleaned = response_text.strip()
            if cleaned.startswith('```'):
                cleaned = cleaned.strip('`')
                if cleaned.lower().startswith('json'):
                    cleaned = cleaned[4:]
            cleaned = cleaned.strip()
            data = json.loads(cleaned)

            # Ensure required keys exist
            for key in ['required_qualifications', 'evaluation_criteria', 'process_description', 'delivery_methods', 'required_documentation']:
                if key not in data:
                    data[key] = 'Not Found'
            if 'confidence_score' not in data:
                data['confidence_score'] = 0.7
            return data
        except Exception as exc:
            logger.error(f"Failed to parse Gemini response: {exc}")
            logger.debug(f"Raw response: {response_text[:500]}")
            return None


if __name__ == '__main__':  # pragma: no cover
    import yaml
    from dotenv import load_dotenv

    load_dotenv()

    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    from database.db_manager import DatabaseManager
    db = DatabaseManager()

    processor = AIProcessor(config, db)
    if processor.client:
        print("AI Processor ready")
        print(f"Model: {processor.model}")
    else:
        print("AI Processor not available (set GOOGLE_API_KEY)")
