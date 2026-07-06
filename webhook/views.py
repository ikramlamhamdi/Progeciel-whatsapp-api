# webhook/views.py
import hashlib
import hmac
import json
import logging
import requests
import base64

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status as drf_status

from .models import MessageRecu
from .serializers import MessageRecuSerializer
from campagnes.models import Envoi

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Sécurité
# ──────────────────────────────────────────────

def _valider_signature(request) -> bool:
    signature_header = request.headers.get("X-Hub-Signature-256", "")
    if not signature_header.startswith("sha256="):
        return False
    signature_recue = signature_header[len("sha256="):]
    secret = settings.WHATSAPP_APP_SECRET.encode()
    signature_calculee = hmac.new(secret, request.body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature_recue, signature_calculee)


def _valider_secret_n8n(request) -> bool:
    """Vérifie que la requête vient bien de n8n via secret partagé."""
    secret = getattr(settings, 'N8N_WEBHOOK_SECRET', None)
    if not secret:
        logger.warning("N8N_WEBHOOK_SECRET non configuré — vérification désactivée")
        return True
    token = request.headers.get("X-N8N-Secret", "")
    return hmac.compare_digest(token, secret)


# ──────────────────────────────────────────────
# Webhook Meta (réception messages WhatsApp + statuts de livraison)
# ──────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["GET", "POST"])
def webhook_whatsapp(request):
    if request.method == "GET":
        mode      = request.GET.get("hub.mode")
        token     = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        if mode == "subscribe" and token == settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN:
            logger.info("Webhook vérifié par Meta.")
            return HttpResponse(challenge, content_type="text/plain")
        logger.warning("Échec de vérification webhook : token invalide.")
        return HttpResponse("Token invalide", status=403)

    if not _valider_signature(request):
        logger.warning("Signature HMAC invalide — requête rejetée.")
        return HttpResponse("Signature invalide", status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse("JSON invalide", status=400)

    try:
        value = data["entry"][0]["changes"][0]["value"]
    except (KeyError, IndexError):
        return HttpResponse("OK", status=200)

    # Messages entrants (Phase 2 : réponses IA / escalade)
    for msg in value.get("messages", []):
        _traiter_message(msg)

    # Statuts de livraison des messages sortants (Phase 1 : campagnes)
    for statut_meta in value.get("statuses", []):
        _traiter_statut(statut_meta)

    return HttpResponse("OK", status=200)


def _traiter_message(msg: dict):
    wa_id    = msg.get("id")
    from_num = msg.get("from")
    msg_type = msg.get("type")

    if MessageRecu.objects.filter(wa_message_id=wa_id).exists():
        logger.info(f"Message {wa_id} déjà traité, ignoré.")
        return

    contenu  = ""
    media_id = ""

    if msg_type == "text":
        contenu = msg.get("text", {}).get("body", "")
    elif msg_type == "audio":
        media_id = msg.get("audio", {}).get("id", "")

    message = MessageRecu.objects.create(
        wa_message_id=wa_id,
        from_number=from_num,
        type_message=msg_type if msg_type in ("text", "audio") else "other",
        contenu_texte=contenu,
        media_id=media_id,
        statut="nouveau",
    )
    logger.info(f"Message {wa_id} enregistré — type: {msg_type}")

    if msg_type == "text":
        _envoyer_a_n8n(message)
    elif msg_type == "audio":
        _envoyer_audio_a_n8n(message)


# ──────────────────────────────────────────────
# Traitement des statuts de livraison (sent/delivered/read/failed)
# ──────────────────────────────────────────────

# Mapping Meta → statuts Envoi
_STATUT_META_VERS_ENVOI = {
    "sent": "envoye",
    "delivered": "envoye",  # pas de statut "livré" distinct dans Envoi actuellement
    "read": "lu",
    "failed": "echec",
}

# Rang de progression : un statut ne peut que monter, jamais redescendre
# (Meta ne garantit pas l'ordre d'arrivée des événements sent/delivered/read)
_RANG_STATUT = {
    "en_attente": 0,
    "envoye": 1,
    "lu": 2,
    "echec": 1,
}


def _traiter_statut(statut_meta: dict):
    """
    Traite un événement de statut de livraison envoyé par Meta
    (value.statuses[]), et met à jour l'Envoi correspondant via
    le message_id_whatsapp.
    """
    wa_message_id = statut_meta.get("id")
    nouveau_statut_meta = statut_meta.get("status")  # sent / delivered / read / failed

    if not wa_message_id or nouveau_statut_meta not in _STATUT_META_VERS_ENVOI:
        return

    nouveau_statut_envoi = _STATUT_META_VERS_ENVOI[nouveau_statut_meta]

    try:
        envoi = Envoi.objects.get(message_id_whatsapp=wa_message_id)
    except Envoi.DoesNotExist:
        logger.warning(f"Statut reçu pour un message inconnu : {wa_message_id}")
        return
    except Envoi.MultipleObjectsReturned:
        logger.error(f"Plusieurs Envoi partagent le même message_id_whatsapp : {wa_message_id}")
        return

    rang_actuel = _RANG_STATUT.get(envoi.statut, 0)
    rang_nouveau = _RANG_STATUT.get(nouveau_statut_envoi, 0)

    if rang_nouveau < rang_actuel:
        logger.info(
            f"Statut {nouveau_statut_meta} ignoré pour Envoi {envoi.id} "
            f"(déjà à '{envoi.statut}', pas de régression)"
        )
        return

    # Un échec explicite doit toujours être enregistré, avec le détail de l'erreur
    if nouveau_statut_meta == "failed":
        erreurs = statut_meta.get("errors", [])
        if erreurs:
            e = erreurs[0]
            envoi.erreur = f"code: {e.get('code')} | {e.get('title')} | {e.get('message', '')}"
        envoi.statut = "echec"
        envoi.save(update_fields=["statut", "erreur"])
        logger.info(f"Envoi {envoi.id} → echec (via webhook Meta)")
        return

    envoi.statut = nouveau_statut_envoi
    envoi.save(update_fields=["statut"])
    logger.info(f"Envoi {envoi.id} → {nouveau_statut_envoi} (via webhook Meta, event: {nouveau_statut_meta})")


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


def _envoyer_audio_a_n8n(message: MessageRecu):
    n8n_url = settings.N8N_WEBHOOK_URL
    if not n8n_url:
        logger.warning("N8N_WEBHOOK_URL non configuré")
        return

    audio_bytes = _telecharger_audio_meta(message.media_id)
    if not audio_bytes:
        message.changer_statut("echec", forcer=True)
        return

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


def _envoyer_a_n8n(message: MessageRecu):
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


# ──────────────────────────────────────────────
# Retour n8n (après traitement LLM)
# ──────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def n8n_repondre(request):
    if not _valider_secret_n8n(request):
        logger.warning("Secret n8n invalide — requête rejetée.")
        return HttpResponse("Non autorisé", status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse("JSON invalide", status=400)

    message_id = data.get("message_id")
    reponse = data.get("reponse") or data.get("reply") or data.get("response")
    raw_statut = data.get("statut") or data.get("status") or "repondu_auto"

    # Accepte les alias n8n les plus courants et convertit vers les statuts Django.
    statut_alias = {
        "answered": "repondu_auto",
        "auto_replied": "repondu_auto",
        "escalated": "escalade",
    }
    statut = statut_alias.get(str(raw_statut).strip().lower(), str(raw_statut).strip().lower())
    statuts_valides = {code for code, _ in MessageRecu.STATUT_CHOICES}
    if statut not in statuts_valides:
        return HttpResponse(f"Statut invalide: {raw_statut}", status=400)

    try:
        message = MessageRecu.objects.get(id=message_id)
    except MessageRecu.DoesNotExist:
        return HttpResponse("Message introuvable", status=404)

    if statut == "repondu_auto" and not reponse:
        return HttpResponse("Réponse requise", status=400)

    if statut in ["repondu_auto", "escalade"] and reponse:
        envoye = _envoyer_whatsapp(message.from_number, reponse)
        if not envoye:
            return HttpResponse("Erreur envoi WhatsApp", status=500)

    message.reponse_envoyee = reponse or ""
    message.save(update_fields=["reponse_envoyee"])
    message.changer_statut(statut, forcer=True)
    logger.info(f"Message {message_id} mis à jour → {statut}")
    return HttpResponse("OK", status=200)


def _envoyer_whatsapp(to_number: str, texte: str) -> bool:
    url = (
        f"https://graph.facebook.com/{settings.META_GRAPH_VERSION}/"
        f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": texte}
    }
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code >= 400:
            logger.error(f"Erreur Meta {response.status_code}: {response.text}")
            return False
        logger.info(f"WhatsApp envoyé à {to_number} ✓")
        return True
    except requests.RequestException as exc:
        logger.error(f"Erreur réseau : {exc}")
        return False


# ──────────────────────────────────────────────
# API REST — Dashboard Frontend
# ──────────────────────────────────────────────

@api_view(['GET'])
def api_messages_liste(request):
    statut = request.GET.get('statut')
    qs = MessageRecu.objects.all().order_by('-recu_le')
    if statut:
        qs = qs.filter(statut=statut)
    serializer = MessageRecuSerializer(qs, many=True)
    return Response(serializer.data)


@api_view(['POST'])
def api_marquer_lu(request, message_id):
    """Marque un message comme lu (ouvert par l'agent), sans y répondre."""
    try:
        message = MessageRecu.objects.get(id=message_id)
    except MessageRecu.DoesNotExist:
        return Response({'erreur': 'Message introuvable'}, status=drf_status.HTTP_404_NOT_FOUND)

    if message.statut != 'nouveau':
        return Response({'success': True, 'message': 'Déjà lu ou traité.'})

    message.changer_statut('lu')
    return Response({'success': True, 'message': 'Message marqué comme lu.'})


@api_view(['POST'])
def api_repondre_manuel(request, message_id):
    """
    Répond à un message manuellement.
    - Si 'reponse' est fournie dans le body → envoie via l'API Meta puis marque repondu_manuel.
    - Si 'reponse' est absente/vide → marque juste repondu_manuel, sans envoi
      (cas où l'agent a déjà répondu directement dans l'app WhatsApp via wa.me).
    """
    try:
        message = MessageRecu.objects.get(id=message_id)
    except MessageRecu.DoesNotExist:
        return Response({'erreur': 'Message introuvable'}, status=drf_status.HTTP_404_NOT_FOUND)

    texte = (request.data.get('reponse') or '').strip()

    if texte:
        envoye = _envoyer_whatsapp(message.from_number, texte)
        if not envoye:
            return Response({'erreur': 'Erreur envoi WhatsApp'}, status=drf_status.HTTP_500_INTERNAL_SERVER_ERROR)
        message.reponse_envoyee = texte
        message.save(update_fields=['reponse_envoyee'])

    try:
        message.changer_statut('repondu_manuel', forcer=True)
    except ValueError as e:
        return Response({'erreur': str(e)}, status=drf_status.HTTP_400_BAD_REQUEST)

    return Response({'success': True, 'message': 'Message marqué comme répondu.'})