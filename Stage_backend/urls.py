# Stage_backend/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('campagnes.urls')),
    path('api/webhook/', include('webhook.urls')),  # ← on ajoute juste /webhook/
]