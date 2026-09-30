import uuid
from django.test import TestCase
from core.models import AuditSession, CatalogItem, AuditLogEntry, AuditorSession
from core.utils import parse_uploaded_file, detect_column_mapping, apply_mapping_and_parse


class AuditSessionModelTest(TestCase):
    def test_creates_session_with_pin(self):
        session = AuditSession.objects.create(name='Test Audit')
        self.assertEqual(len(session.session_pin), 5)
        self.assertEqual(session.status, 'draft')

    def test_pin_is_unique(self):
        s1 = AuditSession.objects.create(name='Audit 1')
        s2 = AuditSession.objects.create(name='Audit 2')
        self.assertNotEqual(s1.session_pin, s2.session_pin)

    def test_str_representation(self):
        session = AuditSession.objects.create(name='Night Audit')
        self.assertIn('Night Audit', str(session))
        self.assertIn(session.session_pin, str(session))


class CatalogItemModelTest(TestCase):
    def setUp(self):
        self.session = AuditSession.objects.create(name='Test')

    def test_create_catalog_item(self):
        item = CatalogItem.objects.create(
            session=self.session,
            barcode='123456',
            product_name='Test Product',
            expected_quantity=10,
        )
        self.assertEqual(item.barcode, '123456')
        self.assertEqual(item.expected_quantity, 10)

    def test_unique_barcode_per_session(self):
        CatalogItem.objects.create(
            session=self.session,
            barcode='123456',
            product_name='Product A',
        )
        with self.assertRaises(Exception):
            CatalogItem.objects.create(
                session=self.session,
                barcode='123456',
                product_name='Product B',
            )


class AuditLogEntryModelTest(TestCase):
    def setUp(self):
        self.session = AuditSession.objects.create(name='Test')

    def test_create_log_entry(self):
        entry = AuditLogEntry.objects.create(
            session=self.session,
            auditor_id='John',
            barcode='123456',
            delta=5,
            timestamp='2026-01-01T00:00:00Z',
        )
        self.assertEqual(entry.delta, 5)
        self.assertFalse(entry.synced)

    def test_event_sourced_aggregation(self):
        AuditLogEntry.objects.create(
            session=self.session, auditor_id='John',
            barcode='123456', delta=10, timestamp='2026-01-01T00:00:00Z',
        )
        AuditLogEntry.objects.create(
            session=self.session, auditor_id='John',
            barcode='123456', delta=3, timestamp='2026-01-01T00:01:00Z',
        )
        from django.db.models import Sum
        total = AuditLogEntry.objects.filter(
            session=self.session, barcode='123456'
        ).aggregate(Sum('delta'))['delta__sum']
        self.assertEqual(total, 13)

    def test_unlisted_item_flag(self):
        entry = AuditLogEntry.objects.create(
            session=self.session, auditor_id='John',
            barcode='UNLISTED_001', delta=2, timestamp='2026-01-01T00:00:00Z',
            is_unlisted=True, unlisted_label='Mystery Item',
        )
        self.assertTrue(entry.is_unlisted)
        self.assertEqual(entry.unlisted_label, 'Mystery Item')


class ColumnMappingTest(TestCase):
    def test_detects_standard_headers(self):
        headers = ['item_code', 'name', 'qty', 'department']
        mapping = detect_column_mapping(headers)
        self.assertEqual(mapping['barcode'], 'item_code')
        self.assertEqual(mapping['product_name'], 'name')
        self.assertEqual(mapping['expected_quantity'], 'qty')

    def test_detects_alternative_headers(self):
        headers = ['sku', 'description', 'expected_qty']
        mapping = detect_column_mapping(headers)
        self.assertEqual(mapping['barcode'], 'sku')
        self.assertEqual(mapping['product_name'], 'description')
        self.assertEqual(mapping['expected_quantity'], 'expected_qty')

    def test_apply_mapping(self):
        rows = [
            {'item_code': '111', 'name': 'Product A', 'qty': '10'},
            {'item_code': '222', 'name': 'Product B', 'qty': '5'},
        ]
        mapping = {'barcode': 'item_code', 'product_name': 'name', 'expected_quantity': 'qty'}
        parsed = apply_mapping_and_parse(rows, mapping)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]['barcode'], '111')
        self.assertEqual(parsed[0]['expected_quantity'], 10)

    def test_apply_mapping_non_string_types(self):
        import numpy as np
        rows = [
            {'item_code': 123456789012, 'name': 'Numeric Barcode', 'qty': 15.0},
            {'item_code': 9876.0, 'name': 100, 'qty': '25'},
            {'item_code': np.nan, 'name': 'Missing Barcode', 'qty': 10},
            {'item_code': '333', 'name': None, 'qty': np.nan},
        ]
        mapping = {'barcode': 'item_code', 'product_name': 'name', 'expected_quantity': 'qty'}
        parsed = apply_mapping_and_parse(rows, mapping)
        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0]['barcode'], '123456789012')
        self.assertEqual(parsed[0]['product_name'], 'Numeric Barcode')
        self.assertEqual(parsed[0]['expected_quantity'], 15)

        self.assertEqual(parsed[1]['barcode'], '9876')
        self.assertEqual(parsed[1]['product_name'], '100')
        self.assertEqual(parsed[1]['expected_quantity'], 25)

        self.assertEqual(parsed[2]['barcode'], '333')
        self.assertEqual(parsed[2]['product_name'], '')
        self.assertIsNone(parsed[2]['expected_quantity'])
