import csv
import json
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from core.models import AuditSession
from .logic import get_session_variance_data, get_session_activity_data


def export_variance_csv(request, session_id):
    session = get_object_or_404(AuditSession, id=session_id)
    data = get_session_variance_data(session)
    sid = str(session.id)[:8]  # Fix: convert UUID to string before slicing

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="Reconciliation_{session.name}_{sid}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Barcode', 'Product Name', 'Category', 'Expected Qty', 'Actual Qty', 'Variance'])

    for item in data['variance_data']:
        writer.writerow([
            item['barcode'],
            item['product_name'],
            item['category'],
            item['expected'],
            item['actual'],
            item['variance'],
        ])

    if data['unlisted_items']:
        writer.writerow([])
        writer.writerow(['UNLISTED ITEMS (Unexpected barcodes)'])
        writer.writerow(['Barcode', 'Label', '', '', 'Actual Qty', 'Scans'])
        for item in data['unlisted_items']:
            writer.writerow([
                item.get('barcode', ''),
                item.get('unlisted_label', ''),
                '', '',
                item['total'],
                item['count'],
            ])

    return response


def export_audit_trail_csv(request, session_id):
    session = get_object_or_404(AuditSession, id=session_id)
    activity = get_session_activity_data(session)
    sid = str(session.id)[:8]  # Fix: convert UUID to string

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="AuditTrail_{session.name}_{sid}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Timestamp', 'Auditor', 'Barcode', 'Product', 'Qty Recorded', 'Is Unlisted'])

    for log in activity:
        writer.writerow([
            log['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
            log['auditor'],
            log['barcode'],
            log['product_name'],
            log['delta'],
            'YES' if log['is_unlisted'] else 'NO',
        ])

    return response


def export_adjustment_json(request, session_id):
    session = get_object_or_404(AuditSession, id=session_id)
    data = get_session_variance_data(session)

    export_data = {
        'session_id': str(session.id),
        'session_name': session.name,
        'exported_at': session.created_at.strftime('%Y-%m-%d %H:%M:%S'),  # Fix: use created_at
        'adjustments': [
            {
                'barcode': item['barcode'],
                'product': item['product_name'],
                'current_system_qty': item['expected'],
                'new_actual_qty': item['actual'],
                'adjustment_needed': item['variance'],
            }
            for item in data['variance_data'] if item['variance'] != 0
        ],
        'unlisted': [
            {
                'barcode': item.get('barcode', ''),
                'label': item.get('unlisted_label', ''),
                'found_qty': item['total'],
            }
            for item in data['unlisted_items']
        ],
    }

    return JsonResponse(export_data, json_dumps_params={'indent': 2})


def executive_summary(request, session_id):
    session = get_object_or_404(AuditSession, id=session_id)
    data = get_session_variance_data(session)

    # Category breakdown for charts
    categories = {}
    for item in data['variance_data']:
        cat = item['category'] or 'Uncategorized'
        if cat not in categories:
            categories[cat] = {'expected': 0, 'actual': 0}
        categories[cat]['expected'] += item['expected']
        categories[cat]['actual'] += item['actual']

    context = {
        'session': session,
        'data': data,
        'categories': categories,
        'activity_summary': get_session_activity_data(session)[:20],
    }

    return render(request, 'supervisor/summary_report.html', context)
