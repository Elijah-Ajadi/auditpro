import json
import os
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

def service_worker(request):
    sw_path = os.path.join(settings.BASE_DIR, 'auditor', 'static', 'auditor', 'sw.js')
    with open(sw_path, 'rb') as f:
        return HttpResponse(f.read(), content_type='application/javascript')
from django.contrib import messages
from core.models import AuditSession, CatalogItem, AuditorSession


def join(request):
    return render(request, 'auditor/join.html')


def join_with_pin(request, session_pin):
    return render(request, 'auditor/join.html', {'prefilled_pin': session_pin})


@require_POST
def authenticate(request):
    session_pin = request.POST.get('session_pin', '').strip().upper()
    nickname = request.POST.get('nickname', '').strip()

    if not session_pin or not nickname:
        messages.error(request, 'All fields are required.')
        return redirect('auditor:join')

    try:
        audit_session = AuditSession.objects.get(session_pin=session_pin, status='active')
    except AuditSession.DoesNotExist:
        messages.error(request, 'Invalid or expired session PIN.')
        return redirect('auditor:join')

    auditor = AuditorSession.objects.create(
        session=audit_session,
        nickname=nickname,
    )

    request.session['auditor_id'] = str(auditor.id)
    request.session['session_id'] = str(audit_session.id)
    request.session['nickname'] = nickname

    return redirect('auditor:hydrate')


def hydrate(request):
    if not request.session.get('session_id'):
        return redirect('auditor:join')

    session_id = request.session['session_id']
    return render(request, 'auditor/hydrate.html', {'session_id': session_id})


def scan(request):
    if not request.session.get('session_id'):
        return redirect('auditor:join')

    return render(request, 'auditor/scan.html', {
        'nickname': request.session.get('nickname', 'Auditor'),
        'session_id': request.session.get('session_id', ''),
    })


def catalog_json(request):
    if not request.session.get('session_id'):
        return JsonResponse({'error': 'Not authenticated'}, status=401)

    session_id = request.session['session_id']
    items = CatalogItem.objects.filter(session_id=session_id).values('barcode', 'product_name', 'expected_quantity')

    catalog = [{'b': item['barcode'], 'n': item['product_name']} for item in items]

    return JsonResponse(catalog, safe=False)
