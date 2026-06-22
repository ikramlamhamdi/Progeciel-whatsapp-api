# campagnes/serializers.py

from rest_framework import serializers
from .models import Client, Campagne, Envoi, TemplateWhatsApp


class TemplateWhatsAppSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateWhatsApp
        fields = [
            'id',
            'nom',
            'categorie',
            'langue',
            'statut',
            'nombre_variables',
            'contenu_header',
            'contenu_body',
            'contenu_footer',
            'description',
            'date_creation_meta',
            'date_approbation',
        ]


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ['id', 'nom', 'numero', 'email', 'date_ajout']


class CampagneSerializer(serializers.ModelSerializer):
    template_nom = serializers.CharField(source='template.nom', read_only=True)
    statistiques = serializers.SerializerMethodField()

    class Meta:
        model = Campagne
        fields = ['id', 'nom', 'date_envoi', 'statut', 'template', 'template_nom', 'variables_template', 'statistiques']

    def get_statistiques(self, obj):
        return obj.statistiques()


class EnvoiSerializer(serializers.ModelSerializer):
    class Meta:
        model = Envoi
        fields = ['id', 'campagne', 'client', 'statut', 'date_envoi']
