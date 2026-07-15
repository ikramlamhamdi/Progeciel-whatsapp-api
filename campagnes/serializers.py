from rest_framework import serializers
from .models import Client, Campagne, Envoi, TemplateWhatsApp, BoutonTemplateWhatsApp


class BoutonTemplateWhatsAppSerializer(serializers.ModelSerializer):
    class Meta:
        model = BoutonTemplateWhatsApp
        fields = ['id', 'ordre', 'type_bouton', 'texte', 'url', 'numero_telephone']


class TemplateWhatsAppSerializer(serializers.ModelSerializer):
    boutons = BoutonTemplateWhatsAppSerializer(many=True, read_only=True)

    class Meta:
        model = TemplateWhatsApp
        fields = [
            'id',
            'nom',
            'categorie',
            'langue',
            'statut',
            'type_header',
            'contenu_header',
            'contenu_body',
            'contenu_footer',
            'nombre_variables',
            'exemples_variables_body',
            'boutons',
            'description',
            'date_creation_meta',
            'date_approbation',
            'template_id_meta',
            'add_security_recommendation',
            'code_expiration_minutes',
            'otp_type',
            'otp_button_text',
        ]


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ['id', 'nom', 'numero', 'email', 'ville','entreprise','segment','date_ajout']


class CampagneSerializer(serializers.ModelSerializer):
    template_nom = serializers.CharField(source='template.nom', read_only=True)
    statistiques = serializers.SerializerMethodField()

    class Meta:
        model = Campagne
        fields = [
            'id',
            'nom',
            'date_creation',
            'date_envoi',
            'statut',
            'template',
            'template_nom',
            'variables_template',
            'statistiques',
        ]

    def get_statistiques(self, obj):
        return obj.statistiques()


class EnvoiSerializer(serializers.ModelSerializer):
    class Meta:
        model = Envoi
        fields = ['id', 'campagne', 'client', 'statut', 'date_envoi']