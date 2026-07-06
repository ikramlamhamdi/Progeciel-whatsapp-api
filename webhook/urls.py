# webhook/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Webhook Meta
    path('whatsapp/', views.webhook_whatsapp, name='webhook_whatsapp'),
    path('n8n-repondre/', views.n8n_repondre, name='n8n_repondre'),

    # API Frontend
    path('messages/', views.api_messages_liste, name='api_messages_liste'),
    path('messages/<int:message_id>/marquer-lu/', views.api_marquer_lu, name='api_marquer_lu'),
    path('messages/<int:message_id>/repondre/', views.api_repondre_manuel, name='api_repondre_manuel'),

]