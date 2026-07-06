from django.contrib import admin
from .models import Client, Campagne, Envoi, TemplateWhatsApp, BoutonTemplateWhatsApp


class BoutonTemplateWhatsAppInline(admin.TabularInline):
    model = BoutonTemplateWhatsApp
    extra = 1
    max_num = 3

@admin.register(TemplateWhatsApp)
class TemplateWhatsAppAdmin(admin.ModelAdmin):
    list_display = ['nom', 'categorie', 'langue', 'statut', 'type_header', 'nombre_variables', 'est_utilisable']
    list_filter = ['statut', 'categorie', 'type_header', 'langue']
    search_fields = ['nom', 'contenu_body']
    readonly_fields = ['date_creation_meta', 'date_approbation']
    inlines = [BoutonTemplateWhatsAppInline]

    def est_utilisable(self, obj):
        return obj.est_utilisable()
    est_utilisable.boolean = True
    est_utilisable.short_description = "Utilisable ?"


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['nom', 'numero', 'email', 'date_ajout']
    search_fields = ['nom', 'numero']
    list_filter = ['date_ajout']


@admin.register(Campagne)
class CampagneAdmin(admin.ModelAdmin):
    list_display = ['nom', 'template', 'statut', 'apercu_stats', 'date_creation', 'date_envoi']
    list_filter = ['statut', 'date_creation']
    search_fields = ['nom']

    def apercu_stats(self, obj):
        stats = obj.statistiques()
        return f"{stats['envoye']} envoyés / {stats['lu']} lus / {stats['echec']} échecs"
    apercu_stats.short_description = "Statistiques"


@admin.register(Envoi)
class EnvoiAdmin(admin.ModelAdmin):
    list_display = ['campagne', 'client', 'statut', 'date_envoi', 'message_id_whatsapp']
    list_filter = ['statut', 'date_envoi']
    search_fields = ['campagne__nom', 'client__nom']