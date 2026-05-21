import uuid
import string
import random
from django.db import models


def generate_session_pin():
    chars = string.ascii_uppercase + string.digits
    while True:
        pin = ''.join(random.choices(chars, k=5))
        if not AuditSession.objects.filter(session_pin=pin).exists():
            return pin


class AuditSession(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('archived', 'Archived'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    session_pin = models.CharField(max_length=5, unique=True, default=generate_session_pin)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.session_pin})'


class CatalogItem(models.Model):
    session = models.ForeignKey(AuditSession, on_delete=models.CASCADE, related_name='catalog_items')
    barcode = models.CharField(max_length=64, db_index=True)
    product_name = models.CharField(max_length=500)
    expected_quantity = models.PositiveIntegerField(null=True, blank=True)
    category = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        unique_together = ['session', 'barcode']
        ordering = ['product_name']
        indexes = [
            models.Index(fields=['session', 'barcode']),
        ]

    def __str__(self):
        return f'{self.product_name} ({self.barcode})'


class AuditLogEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(AuditSession, on_delete=models.CASCADE, related_name='log_entries')
    auditor_id = models.CharField(max_length=64, db_index=True)
    zone = models.CharField(max_length=64, db_index=True)
    barcode = models.CharField(max_length=64, db_index=True)
    delta = models.IntegerField()
    timestamp = models.DateTimeField(db_index=True)
    synced = models.BooleanField(default=False)
    is_unlisted = models.BooleanField(default=False)
    unlisted_label = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['session', 'barcode']),
            models.Index(fields=['session', 'auditor_id']),
            models.Index(fields=['session', 'zone']),
            models.Index(fields=['synced']),
        ]

    def __str__(self):
        return f'{self.barcode}: {self.delta:+d} by {self.auditor_id}'


class AuditorSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(AuditSession, on_delete=models.CASCADE, related_name='auditor_sessions')
    nickname = models.CharField(max_length=100)
    zone = models.CharField(max_length=64)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(auto_now=True)
    is_online = models.BooleanField(default=True)

    class Meta:
        ordering = ['-joined_at']

    def __str__(self):
        return f'{self.nickname} in {self.zone}'


class RecountTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(AuditSession, on_delete=models.CASCADE, related_name='recount_tasks')
    barcode = models.CharField(max_length=64, db_index=True)
    assigned_to = models.ForeignKey(AuditorSession, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('completed', 'Completed')], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['session', 'barcode', 'status']

    def __str__(self):
        return f'Recount {self.barcode} in {self.session.name}'
