# campagnes/tasks.py

import re

import requests

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from .models import Client, Campagne, Envoi, TemplateWhatsApp

META_REQUEST_TIMEOUT = 15


def normaliser_numero(numero):
    numero = re.sub(r'[^\d+]', '', str(numero or '').strip())
    numero = numero.removeprefix('+')

    if numero.startswith('00'):
        numero = numero[2:]
    if numero.startswith('0'):
        numero = numero[1:]
    if not numero.startswith('212'):
        numero = f'212{numero}'

    return f'+{numero}'


def construire_payload(template, numero, variables=None):
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": numero,
        "type": "template",
        "template": {
            "name": template.nom,
            "language": {"code": template.langue}
        }
    }
    if variables and template.nombre_variables > 0:
        payload["template"]["components"] = [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": str(param)} for param in variables
                ]
            }
        ]
    return payload


@shared_task(bind=True, max_retries=3)
def envoyer_message_whatsapp(self, client_id, campagne_id, template_id, variables=None):
    """
    Tâche Celery : envoyer UN message WhatsApp à UN client.
    Gère les retries et les rate limits.
    """
    try:
        client = Client.objects.get(id=client_id)
        campagne = Campagne.objects.get(id=campagne_id)
        template = TemplateWhatsApp.objects.get(id=template_id)

        # Vérifier que le template est utilisable
        if not template.est_utilisable():
            raise Exception(f"Template {template.nom} non approuvé")

        # Normaliser le numéro
        numero = normaliser_numero(client.numero)

        # Construire le payload
        payload = construire_payload(template, numero, variables or [])

        # Headers API Meta
        url = f"https://graph.facebook.com/v18.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
        headers = {
            'Authorization': f'Bearer {settings.WHATSAPP_TOKEN}',
            'Content-Type': 'application/json'
        }

        # Envoyer le message
        response = requests.post(url, headers=headers, json=payload, timeout=META_REQUEST_TIMEOUT)
        result = response.json()

        if 200 <= response.status_code < 300:
            # ✅ Succès
            message_id = result.get('messages', [{}])[0].get('id', '')
            Envoi.objects.update_or_create(
                campagne=campagne,
                client=client,
                defaults={
                    'statut': 'envoye',
                    'message_id_whatsapp': message_id,
                    'erreur': '',
                    'date_envoi': timezone.now(),
                }
            )
            return {'success': True, 'message_id': message_id}

        elif response.status_code == 429:
            # ❌ Rate limit Meta - retry après 60 secondes
            raise self.retry(countdown=60, exc=Exception("Rate limit Meta"))

        else:
            # ❌ Erreur API
            erreur = result.get('error', {}).get('message', 'Erreur inconnue')
            Envoi.objects.update_or_create(
                campagne=campagne,
                client=client,
                defaults={
                    'statut': 'echec',
                    'erreur': erreur,
                    'date_envoi': timezone.now(),
                }
            )
            raise Exception(erreur)

    except Exception as exc:
        # ❌ Erreur réseau ou autre - retry
        raise self.retry(countdown=60, exc=exc)
