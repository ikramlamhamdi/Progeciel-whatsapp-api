# webhook/serializers.py
from rest_framework import serializers
from .models import MessageRecu


class MessageRecuSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageRecu
        fields = [
            'id',
            'wa_message_id',
            'from_number',
            'type_message',
            'contenu_texte',
            'media_id',
            'statut',
            'reponse_envoyee',
            'recu_le',
        ]