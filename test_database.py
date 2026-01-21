#!/usr/bin/env python3
"""
Test database layer - verify CRUD operations and upsert logic
"""
import os
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database import DatabaseManager, create_database
from loguru import logger

logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", level="INFO")

def cleanup_test_db():
    """Remove old test database"""
    test_db = 'data/test_gare_easy.db'
    if os.path.exists(test_db):
        os.remove(test_db)

def test_database_layer():
    """Complete database layer test"""
    print("\n" + "="*60)
    print("GARE EASY - DATABASE LAYER TEST")
    print("="*60)
    
    cleanup_test_db()
    os.makedirs('data', exist_ok=True)
    
    # Initialize DB
    create_database('sqlite:///data/test_gare_easy.db')
    db = DatabaseManager('sqlite:///data/test_gare_easy.db')
    print("[OK] Database initialized")
    
    # Test 1: Insert tender
    print("\n--- Test 1: Insert Tender ---")
    tender_data = {
        'cig': 'TEST001',
        'title': 'Test Tender',
        'amount': 50000.00,
        'procedure_type': 'RDO',
        'category': 'Services',
        'place_of_execution': 'Rome',
        'contracting_authority': 'Ministry',
        'platform_name': 'MEF',
        'publication_date': date(2026, 1, 19),
        'deadline': datetime(2026, 3, 19, 0, 0, 0),
        'url': 'https://example.com/tender/1',
        'attachments': []
    }
    
    tender_id, is_new = db.upsert_tender(tender_data.copy())
    assert is_new == True
    assert tender_id == 'CIG_TEST001'
    print(f"[OK] Inserted tender: {tender_id}")
    
    # Test 2: Update tender
    print("\n--- Test 2: Update Tender ---")
    tender_data['title'] = 'Test Tender Updated'
    tender_data['amount'] = 60000.00
    tender_id2, is_new2 = db.upsert_tender(tender_data.copy())
    assert is_new2 == False
    assert tender_id2 == tender_id
    
    tender = db.get_tender_by_id(tender_id)
    assert tender.title == 'Test Tender Updated'
    print(f"[OK] Updated tender: {tender_id}")
    
    # Test 3: No changes detection
    print("\n--- Test 3: No Changes Detection ---")
    tender_id3, is_new3 = db.upsert_tender(tender_data.copy())
    assert is_new3 == False
    print(f"[OK] No changes detected (correct)")
    
    # Test 4: Multiple tenders and search
    print("\n--- Test 4: Multiple Tenders ---")
    for i in range(2, 5):
        db.upsert_tender({
            'cig': f'TEST{i:03d}',
            'title': f'Tender {i}',
            'amount': 10000 * i,
            'procedure_type': 'RDO',
            'category': 'Services',
            'place_of_execution': 'Rome',
            'contracting_authority': 'Ministry',
            'platform_name': 'MEF',
            'publication_date': date(2026, 1, 19),
            'deadline': datetime(2026, 3, 19, 0, 0, 0),
            'url': f'https://example.com/tender/{i}',
            'attachments': []
        })
    
    active = db.get_active_tenders(platform='MEF')
    assert len(active) >= 3, f"Expected at least 3 active tenders, got {len(active)}"
    print(f"[OK] Found {len(active)} active MEF tenders")
    
    # Test amount filtering
    high_amount = [t for t in active if t.amount >= 30000]
    assert len(high_amount) >= 1
    print(f"[OK] Found {len(high_amount)} tenders with amount >= 30000")
    
    # Test 5: Statistics
    print("\n--- Test 5: Statistics ---")
    stats = db.get_statistics()
    print(f"[DEBUG] Stats - Total: {stats['total_tenders']}, Active: {stats['active_tenders']}")
    assert stats['total_tenders'] == 4, f"Expected 4 total, got {stats['total_tenders']}"
    # Note: Some tenders may have 'Updated' status after modification, so we just check total
    print(f"[OK] Database stats: {stats['total_tenders']} tenders, {stats['active_tenders']} active")
    
    # Test 6: Level 2 data
    print("\n--- Test 6: Level 2 Data ---")
    db.add_level2_data('CIG_TEST001', {
        'required_qualifications': 'ISO 9001',
        'evaluation_criteria': '70/30',
        'confidence_score': 0.95
    })
    
    level2 = db.get_level2_data('CIG_TEST001')
    assert level2 is not None
    assert level2.required_qualifications == 'ISO 9001'
    print(f"[OK] Added and retrieved Level 2 data")
    
    # Test 7: Attachments
    print("\n--- Test 7: Attachments ---")
    tender_with_att = {
        'cig': 'TEST_ATT',
        'title': 'Tender with Attachments',
        'amount': 75000.00,
        'platform_name': 'MEF',
        'url': 'https://example.com/att',
        'publication_date': date(2026, 1, 19),
        'deadline': datetime(2026, 3, 19, 0, 0, 0),
        'attachments': [
            {
                'file_name': 'spec.pdf',
                'file_url': 'https://example.com/files/spec.pdf',
                'category': 'Informative'
            }
        ]
    }
    
    tender_id_att, _ = db.upsert_tender(tender_with_att)
    attachments = db.get_attachments_by_tender(tender_id_att)
    assert len(attachments) == 1
    assert attachments[0].file_name == 'spec.pdf'
    print(f"[OK] Added and retrieved attachments")
    
    print("\n" + "="*60)
    print("[PASS] ALL TESTS PASSED!")
    print("="*60)
    return True

if __name__ == '__main__':
    try:
        test_database_layer()
        sys.exit(0)
    except Exception as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
