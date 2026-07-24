# webhook/serializers.py
from rest_framework import serializers
from .models import MessageRecu


class MessageRecuSerializer(serializers.ModelSerializer):
    audio_file = serializers.SerializerMethodField()

    class Meta:
        model = MessageRecu
        fields = [
            'id',
            'wa_message_id',
            'from_number',
            'type_message',
            'contenu_texte',
            'media_id',
            'audio_file',
            'statut',
            'reponse_envoyee',
            'recu_le',
        ]

    def get_audio_file(self, obj):
        if not obj.audio_file:
            return None
        return obj.audio_file.url
