# webhook/tasks.py
import base64
import logging

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from celery import shared_task

from .models import MessageRecu

logger = logging.getLogger(__name__)


def _telecharger_audio_meta(media_id: str) -> bytes | None:
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"}

    try:
        url_info = requests.get(
            f"https://graph.facebook.com/{settings.META_GRAPH_VERSION}/{media_id}",
            headers=headers, timeout=10
        )
        url_info.raise_for_status()
        download_url = url_info.json().get("url")
        if not download_url:
            logger.error("URL audio introuvable dans la réponse Meta")
            return None
    except Exception as e:
        logger.error(f"Erreur récupération URL audio : {e}")
        return None

    try:
        audio_response = requests.get(download_url, headers=headers, timeout=30)
        audio_response.raise_for_status()
        logger.info(f"Audio téléchargé depuis Meta ({len(audio_response.content)} bytes)")
        return audio_response.content
    except Exception as e:
        logger.error(f"Erreur téléchargement fichier audio : {e}")
        return None


@shared_task(bind=True)
def envoyer_texte_a_n8n_async(self, message_id: int):
    """
    Transmet un message texte reçu à n8n, en arrière-plan.

    Déplacé depuis webhook/views.py : cet appel réseau (jusqu'à 10s de
    timeout) ne doit jamais bloquer la réponse au webhook Meta, qui doit
    répondre vite (Meta peut suspendre le webhook s'il est trop lent).
    """
    try:
        message = MessageRecu.objects.get(id=message_id)
    except MessageRecu.DoesNotExist:
        logger.error(f"[Celery] MessageRecu {message_id} introuvable, tâche annulée.")
        return

    n8n_url = settings.N8N_WEBHOOK_URL
    if not n8n_url:
        logger.warning("N8N_WEBHOOK_URL non configuré")
        return

    payload = {
        "message_id": message.id,
        "wa_message_id": message.wa_message_id,
        "from_number": message.from_number,
        "type_message": message.type_message,
        "contenu_texte": message.contenu_texte,
    }

    try:
        response = requests.post(n8n_url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Message {message.id} envoyé à n8n ✓")
        message.changer_statut("en_traitement", forcer=True)
    except Exception as e:
        logger.error(f"Erreur envoi n8n : {e}")
        message.changer_statut("echec", forcer=True)


@shared_task(bind=True)
def envoyer_audio_a_n8n_async(self, message_id: int):
    """
    Télécharge l'audio depuis Meta et le transmet à n8n, en arrière-plan.

    Déplacé depuis webhook/views.py : la chaîne complète (téléchargement
    Meta jusqu'à 30s + envoi n8n jusqu'à 30s) pouvait bloquer la réponse
    au webhook Meta pendant potentiellement une minute.
    """
    try:
        message = MessageRecu.objects.get(id=message_id)
    except MessageRecu.DoesNotExist:
        logger.error(f"[Celery] MessageRecu {message_id} introuvable, tâche annulée.")
        return

    n8n_url = settings.N8N_WEBHOOK_URL
    if not n8n_url:
        logger.warning("N8N_WEBHOOK_URL non configuré")
        return

    audio_bytes = _telecharger_audio_meta(message.media_id)
    if not audio_bytes:
        message.changer_statut("echec", forcer=True)
        return

    # Sauvegarde du fichier pour l'écoute côté frontend
    nom_fichier = f"{message.wa_message_id}.ogg"
    message.audio_file.save(nom_fichier, ContentFile(audio_bytes), save=True)

    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    payload = {
        "message_id": message.id,
        "wa_message_id": message.wa_message_id,
        "from_number": message.from_number,
        "type_message": "audio",
        "audio_base64": audio_b64,
    }

    try:
        response = requests.post(n8n_url, json=payload, timeout=30)
        response.raise_for_status()
        logger.info(f"Audio {message.id} envoyé à n8n ✓")
        message.changer_statut("en_traitement", forcer=True)
    except Exception as e:
        logger.error(f"Erreur envoi audio à n8n : {e}")
        message.changer_statut("echec", forcer=True)