from django.db.models import Sum, Count, Max
from core.models import CatalogItem, AuditLogEntry

def get_session_variance_data(session):
    """
    Centralized logic to calculate variance data for a session.
    Returns a dictionary with variance_data, unlisted_items, and summary stats.
    """
    log_sums = AuditLogEntry.objects.filter(session=session).values('barcode').annotate(
        actual_total=Sum('delta')
    )
    actual_map = {item['barcode']: item['actual_total'] for item in log_sums}

    catalog_items = CatalogItem.objects.filter(session=session)
    
    variance_data = []
    total_expected = 0
    total_actual = 0
    
    for item in catalog_items:
        actual_sum = actual_map.get(item.barcode, 0)
        expected = item.expected_quantity or 0
        variance = actual_sum - expected
        
        total_expected += expected
        total_actual += actual_sum

        variance_data.append({
            'barcode': item.barcode,
            'product_name': item.product_name,
            'expected': expected,
            'actual': actual_sum,
            'variance': variance,
            'category': item.category,
        })

    # Total Discrepancy Count
    total_discrepancies = sum(1 for v in variance_data if v['variance'] != 0)
    
    # Net Accuracy (Percentage)
    accuracy = (total_actual / total_expected * 100) if total_expected > 0 else 100
    if accuracy > 100: accuracy = 100 - (accuracy - 100) # Simple penalty for overages

    # Find unlisted items
    unlisted = AuditLogEntry.objects.filter(
        session=session,
        is_unlisted=True
    ).values('unlisted_label', 'barcode').annotate(
        total=Sum('delta'),
        count=Count('id')
    ).order_by('-total')

    # Sort by absolute variance
    variance_data.sort(key=lambda x: abs(x['variance']), reverse=True)

    return {
        'variance_data': variance_data,
        'unlisted_items': list(unlisted),
        'total_discrepancies': total_discrepancies,
        'total_expected': total_expected,
        'total_actual': total_actual,
        'accuracy': round(accuracy, 2),
    }

def get_session_activity_data(session):
    """
    Centralized logic to get the full audit trail for a session.
    """
    logs = AuditLogEntry.objects.filter(session=session).order_by('-timestamp')
    
    activity_items = []
    # Index catalog for fast lookup
    catalog_map = {item.barcode: item.product_name for item in CatalogItem.objects.filter(session=session)}
    
    for entry in logs:
        activity_items.append({
            'product_name': catalog_map.get(entry.barcode, entry.unlisted_label or entry.barcode),
            'barcode': entry.barcode,
            'delta': entry.delta,
            'auditor': entry.auditor_id,
            'timestamp': entry.timestamp,
            'is_unlisted': entry.is_unlisted,
        })
    
    return activity_items
