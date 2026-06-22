from django.urls import path
from . import views

urlpatterns = [
    # Templates WhatsApp
    path('templates/', views.templates_list, name='templates'),
    path('templates/utilisables/', views.templates_utilisables, name='templates_utilisables'),
    path('templates/creer/', views.creer_template, name='creer_template'),
    path('templates/synchroniser/', views.synchroniser_templates, name='synchroniser_templates'),
    path('templates/<int:template_id>/supprimer/', views.supprimer_template, name='supprimer_template'),

    # Clients
    path('clients/', views.clients_list, name='clients'),
    path('clients/import/', views.importer_clients_excel, name='import_clients'),

    # Campagnes
    path('campagnes/', views.campagnes_list, name='campagnes'),
    path('campagnes/<int:campagne_id>/envoyer/', views.envoyer_campagne, name='envoyer_campagne'),

    # Test unique
    path('envoyer-test/', views.envoyer_test_unique, name='envoyer_test'),
]
