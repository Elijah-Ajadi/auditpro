import json
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.db import IntegrityError
from django.utils import timezone
from core.models import AuditSession, AuditLogEntry, CatalogItem, AuditorSession


@require_GET
def health_check(request):
    print(f"DEBUG: Health check ping received from {request.META.get('REMOTE_ADDR')}")
    return JsonResponse({'status': 'ok'})


@require_POST
@csrf_exempt
def sync_endpoint(request):
    print(f"DEBUG: Sync request received from {request.META.get('REMOTE_ADDR')}")
    try:
        body = json.loads(request.body)
        logs = body.get('logs', [])
        print(f"DEBUG: Processing {len(logs)} logs")
    except json.JSONDecodeError:
        print("DEBUG: Failed to decode JSON body")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    acknowledged = []
    auditor_nicknames = set()

    for log in logs:
        try:
            session = AuditSession.objects.get(id=log.get('session_id'))
            AuditLogEntry.objects.update_or_create(
                id=log.get('id'),
                defaults={
                    'session': session,
                    'auditor_id': log.get('auditor_id', ''),
                    'zone': log.get('zone', ''),
                    'barcode': log.get('barcode', ''),
                    'delta': int(log.get('delta', 0)),
                    'timestamp': log.get('timestamp'),
                    'synced': True,
                    'is_unlisted': log.get('is_unlisted', False),
                    'unlisted_label': log.get('unlisted_label', ''),
                }
            )
            
            # If this was a recount item, clear previous incorrect logs for this barcode
            # so the new count becomes the 'Ground Truth'
            from core.models import RecountTask
            recount_qs = RecountTask.objects.filter(
                session=session,
                barcode=log.get('barcode'),
                status='pending'
            )
            
            if recount_qs.exists():
                print(f"DEBUG: Clearing previous logs for barcode {log.get('barcode')} due to recount")
                AuditLogEntry.objects.filter(
                    session=session,
                    barcode=log.get('barcode')
                ).delete()
                recount_qs.update(status='completed')
            
            acknowledged.append(log.get('id'))
            auditor_nicknames.add(log.get('auditor_id', ''))
        except (AuditSession.DoesNotExist, ValueError, KeyError):
            continue

    for nickname in auditor_nicknames:
        if nickname and 'session' in locals():
            AuditorSession.objects.filter(
                session=session,
                nickname=nickname
            ).update(last_active=timezone.now())

    return JsonResponse({'acknowledged': acknowledged})


def catalog_api(request, session_id):
    session = get_object_or_404(AuditSession, id=session_id)
    items = CatalogItem.objects.filter(session=session).values('barcode', 'product_name', 'expected_quantity')
    catalog = [{'b': item['barcode'], 'n': item['product_name']} for item in items]
    return JsonResponse(catalog, safe=False)


def recount_tasks(request, session_id):
    from core.models import RecountTask, CatalogItem
    
    session = get_object_or_404(AuditSession, id=session_id)
    
    pending_tasks = RecountTask.objects.filter(
        session=session,
        status='pending'
    ).select_related('session')
    
    tasks_data = []
    for task in pending_tasks:
        catalog_item = CatalogItem.objects.filter(session=session, barcode=task.barcode).first()
        tasks_data.append({
            'id': str(task.id),
            'barcode': task.barcode,
            'product_name': catalog_item.product_name if catalog_item else 'Unknown Item',
        })
    
    return JsonResponse({'recounts': tasks_data})
