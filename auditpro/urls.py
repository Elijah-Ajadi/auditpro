from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('supervisor/', include('supervisor.urls', namespace='supervisor')),
    path('auditor/', include('auditor.urls', namespace='auditor')),
    path('api/', include('api.urls', namespace='api')),
    path('', include('core.urls', namespace='core')),
]
