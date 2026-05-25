import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Count, Max
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from core.models import AuditSession, CatalogItem, AuditLogEntry, AuditorSession, RecountTask
from core.utils import parse_uploaded_file, detect_column_mapping, apply_mapping_and_parse, generate_qr_code_base64, EXPECTED_FIELDS


def dashboard(request):
    sessions = AuditSession.objects.exclude(status='archived').order_by('-created_at')[:20]
    return render(request, 'supervisor/dashboard.html', {
        'sessions': sessions,
    })


def audit_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Session name is required.')
            return render(request, 'supervisor/audit_create.html')

        session = AuditSession.objects.create(name=name, status='draft')
        return redirect('supervisor:audit_upload', session_id=str(session.id))

    return render(request, 'supervisor/audit_create.html')


def audit_upload(request, session_id):
    session = get_object_or_404(AuditSession, id=session_id)

    if request.method == 'POST' and request.FILES.get('file'):
        uploaded_file = request.FILES['file']
        data, error = parse_uploaded_file(uploaded_file)

        if error:
            messages.error(request, error)
            return render(request, 'supervisor/audit_upload.html', {'session': session})

        column_mapping = detect_column_mapping(data['headers'])

        request.session[f'upload_{session_id}'] = {
            'headers': data['headers'],
            'rows': data['rows'],
            'row_count': data['row_count'],
        }

        field_mappings = [
            {'field': f, 'mapped': column_mapping.get(f), 'auto': f in column_mapping}
            for f in EXPECTED_FIELDS
        ]

        return render(request, 'supervisor/column_mapping.html', {
            'session': session,
            'headers': data['headers'],
            'field_mappings': field_mappings,
            'row_count': data['row_count'],
        })

    return render(request, 'supervisor/audit_upload.html', {'session': session})


@require_POST
def submit_column_mapping(request, session_id):
    session = get_object_or_404(AuditSession, id=session_id)
    file_data = request.session.get(f'upload_{session_id}')

    if not file_data:
        messages.error(request, 'Upload session expired. Please re-upload your file.')
        return redirect('supervisor:audit_upload', session_id=session_id)

    column_mapping = {}
    unmapped = []
    for field in EXPECTED_FIELDS:
        mapped_col = request.POST.get(f'map_{field}', '').strip()
        if mapped_col:
            column_mapping[field] = mapped_col
        else:
            unmapped.append(field)

    if unmapped:
        messages.error(request, f'Missing mapping for: {", ".join(unmapped)}')
        field_mappings = [
            {'field': f, 'mapped': column_mapping.get(f), 'auto': f in column_mapping}
            for f in EXPECTED_FIELDS
        ]
        return render(request, 'supervisor/column_mapping.html', {
            'session': session,
            'headers': file_data['headers'],
            'field_mappings': field_mappings,
            'row_count': file_data['row_count'],
        })

    parsed_items = apply_mapping_and_parse(file_data['rows'], column_mapping)

    if not parsed_items:
        messages.error(request, 'No valid items found after mapping. Check that barcode column contains data.')
        field_mappings = [
            {'field': f, 'mapped': column_mapping.get(f), 'auto': f in column_mapping}
            for f in EXPECTED_FIELDS
        ]
        return render(request, 'supervisor/column_mapping.html', {
            'session': session,
            'headers': file_data['headers'],
            'field_mappings': field_mappings,
            'row_count': file_data['row_count'],
        })

    request.session[f'parsed_{session_id}'] = parsed_items

    return render(request, 'supervisor/audit_confirm.html', {
        'session': session,
        'parsed_items': parsed_items,
        'item_count': len(parsed_items),
        'preview': json.dumps(parsed_items[:5], indent=2),
    })


@require_POST
def confirm_import(request, session_id):
    session = get_object_or_404(AuditSession, id=session_id)
    parsed_items = request.session.get(f'parsed_{session_id}')

    if not parsed_items:
        messages.error(request, 'No data to import. Please upload a file first.')
        return redirect('supervisor:audit_upload', session_id=session_id)

    with transaction.atomic():
        catalog_items = []
        for item in parsed_items:
            catalog_items.append(CatalogItem(
                session=session,
                barcode=item.get('barcode', ''),
                product_name=item.get('product_name', ''),
                expected_quantity=item.get('expected_quantity'),
                category=item.get('category', ''),
            ))
        
        # Clear existing catalog for this session if re-importing
        CatalogItem.objects.filter(session=session).delete()
        CatalogItem.objects.bulk_create(catalog_items)

        session.status = 'active'
        session.save()

        del request.session[f'parsed_{session_id}']

    messages.success(request, f'Successfully imported {len(parsed_items)} items.')
    return redirect('supervisor:session_detail', session_id=session_id)


def session_detail(request, session_id):
    session = get_object_or_404(AuditSession, id=session_id)
    join_url = request.build_absolute_uri(reverse('auditor:join_with_pin', args=[session.session_pin]))
    qr_code = generate_qr_code_base64(join_url)
    item_count = session.catalog_items.count()

    return render(request, 'supervisor/session_detail.html', {
        'session': session,
        'session_pin': session.session_pin,
        'join_url': join_url,
        'qr_code': qr_code,
        'item_count': item_count,
    })


def monitor(request, session_id):
    session = get_object_or_404(AuditSession, id=session_id)
    return render(request, 'supervisor/monitor.html', {'session': session})


def monitor_refresh(request, session_id):
    session = get_object_or_404(AuditSession, id=session_id)
    cutoff = timezone.now() - timedelta(minutes=5)
    auditors = AuditorSession.objects.filter(session=session)

    # Multi-auditor stats in one query
    log_stats_qs = AuditLogEntry.objects.filter(session=session).values('auditor_id').annotate(
        total_scans=Count('id'),
        last_activity=Max('timestamp')
    )
    stats_map = {item['auditor_id']: item for item in log_stats_qs}

    auditor_stats = []
    for auditor in auditors:
        stats = stats_map.get(auditor.nickname, {})
        is_online = auditor.last_active >= cutoff if auditor.last_active else False

        auditor_stats.append({
            'nickname': auditor.nickname,
            'total_scans': stats.get('total_scans', 0),
            'last_activity': stats.get('last_activity'),
            'is_online': is_online,
            'joined_at': auditor.joined_at,
        })

    total_items = session.catalog_items.count()

    scanned_barcodes = AuditLogEntry.objects.filter(
        session=session
    ).values_list('barcode', flat=True).distinct()

    unique_items_scanned = session.catalog_items.filter(barcode__in=scanned_barcodes).count()
    progress = round((unique_items_scanned / total_items * 100), 1) if total_items > 0 else 0

    recent_activity = AuditLogEntry.objects.filter(
        session=session
    ).select_related('session').order_by('-timestamp')[:50]

    activity_items = []
    for entry in recent_activity:
        catalog_item = CatalogItem.objects.filter(
            session=session,
            barcode=entry.barcode
        ).first()

        activity_items.append({
            'product_name': catalog_item.product_name if catalog_item else entry.unlisted_label or entry.barcode,
            'barcode': entry.barcode,
            'quantity_recorded': entry.delta,
            'expected_quantity': catalog_item.expected_quantity if catalog_item else None,
            'auditor': entry.auditor_id,
            'timestamp': entry.timestamp,
            'is_unlisted': entry.is_unlisted,
        })

    context = {
        'session': session,
        'auditors': auditor_stats,
        'total_items': total_items,
        'unique_items_scanned': unique_items_scanned,
        'progress': progress,
        'recent_activity': activity_items,
    }

    if request.htmx:
        return render(request, 'supervisor/partials/monitor_full.html', context)

    return render(request, 'supervisor/monitor.html', context)


from .logic import get_session_variance_data, get_session_activity_data

def variance(request, session_id):
    session = get_object_or_404(AuditSession, id=session_id)
    data = get_session_variance_data(session)
    
    context = {
        'session': session,
        'variance_data': data['variance_data'],
        'unlisted_items': data['unlisted_items'],
        'total_discrepancies': data['total_discrepancies'],
        'accuracy': data['accuracy'],
    }

    return render(request, 'supervisor/variance.html', context)


@require_POST
def trigger_recount(request, session_id, barcode):
    session = get_object_or_404(AuditSession, id=session_id)

    # Create a recount task
    RecountTask.objects.get_or_create(
        session=session,
        barcode=barcode,
        status='pending'
    )

    if request.headers.get('HX-Request'):
        messages.success(request, f'Recount triggered for {barcode}')
        return redirect('supervisor:variance', session_id=session_id)

    messages.success(request, f'Recount triggered for barcode {barcode}')
    return redirect('supervisor:variance', session_id=session_id)


@require_POST
def archive_session(request, session_id):
    session = get_object_or_404(AuditSession, id=session_id)
    session.status = 'archived'
    session.save()
    messages.success(request, f'Session "{session.name}" archived.')
    return redirect('supervisor:dashboard')


def archived_sessions(request):
    sessions = AuditSession.objects.filter(status='archived').order_by('-created_at')
    return render(request, 'supervisor/archived_sessions.html', {
        'sessions': sessions,
    })
