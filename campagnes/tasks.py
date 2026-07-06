# campagnes/tasks.py
import time
import logging
import requests
from django.conf import settings
from django.utils import timezone
from celery import shared_task

from .models import Campagne, Client, Envoi, TemplateWhatsApp
from .services import construire_payload, resoudre_variables_pour_client, normaliser_numero

logger = logging.getLogger(__name__)

GRAPH_VERSION = getattr(settings, 'META_GRAPH_VERSION', 'v23.0')
DELAI_ENTRE_ENVOIS = 0.15  # ~6-7 msg/s, marge de sécurité sous les limites de débit Meta
MAX_TENTATIVES_429 = 3


@shared_task(bind=True)
def envoyer_campagne_async(self, campagne_id, client_ids, template_id, variables, mapping_variables, header_media_id, header_url):
    try:
        campagne = Campagne.objects.get(id=campagne_id)
    except Campagne.DoesNotExist:
        logger.error(f"[Celery] Campagne {campagne_id} introuvable, tâche annulée.")
        return

    try:
        template = TemplateWhatsApp.objects.get(id=template_id)
    except TemplateWhatsApp.DoesNotExist:
        logger.error(f"[Celery] Template {template_id} introuvable, campagne {campagne_id} annulée.")
        campagne.statut = 'echec'
        campagne.save(update_fields=['statut'])
        return

    clients = Client.objects.filter(id__in=client_ids)
    url_api = f"https://graph.facebook.com/{GRAPH_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        'Authorization': f'Bearer {settings.WHATSAPP_TOKEN}',
        'Content-Type': 'application/json',
    }

    succes = 0
    echecs = 0

    for client in clients:
        numero = normaliser_numero(client.numero)
        variables_client = resoudre_variables_pour_client(
            client, mapping_variables, template.nombre_variables, variables_statiques=variables
        )
        payload = construire_payload(
            template, numero, variables_client,
            header_url=header_url or None,
            header_media_id=header_media_id or None,
        )

        tentative = 0
        while True:
            tentative += 1
            try:
                response = requests.post(url_api, headers=headers, json=payload, timeout=15)
                try:
                    result = response.json()
                except ValueError:
                    result = {}

                if response.status_code == 429 and tentative < MAX_TENTATIVES_429:
                    attente = 2 ** tentative  # 2s, puis 4s
                    logger.warning(
                        f"[Celery] Rate limit Meta atteint pour {client.id}, "
                        f"retry dans {attente}s (tentative {tentative})"
                    )
                    time.sleep(attente)
                    continue

                if 200 <= response.status_code < 300:
                    message_id = result.get('messages', [{}])[0].get('id', '')
                    Envoi.objects.update_or_create(
                        campagne=campagne, client=client,
                        defaults={
                            'statut': 'envoye',
                            'message_id_whatsapp': message_id,
                            'erreur': '',
                            'date_envoi': timezone.now(),
                        }
                    )
                    succes += 1
                else:
                    erreur_meta = result.get('error', {}) if isinstance(result, dict) else {}
                    erreur_msg = erreur_meta.get('message', 'Erreur inconnue')
                    code = erreur_meta.get('code')
                    sous_code = erreur_meta.get('error_subcode')
                    details = (erreur_meta.get('error_data') or {}).get('details')

                    erreur_complete = erreur_msg
                    if code:
                        erreur_complete += f' (code {code}'
                        if sous_code:
                            erreur_complete += f', sous-code {sous_code}'
                        erreur_complete += ')'
                    if details:
                        erreur_complete += f' — {details}'

                    Envoi.objects.update_or_create(
                        campagne=campagne, client=client,
                        defaults={
                            'statut': 'echec',
                            'erreur': erreur_complete,
                            'date_envoi': timezone.now(),
                        }
                    )
                    echecs += 1

            except Exception as e:
                Envoi.objects.update_or_create(
                    campagne=campagne, client=client,
                    defaults={
                        'statut': 'echec',
                        'erreur': str(e),
                        'date_envoi': timezone.now(),
                    }
                )
                echecs += 1

            break

        time.sleep(DELAI_ENTRE_ENVOIS)

    if echecs == 0:
        campagne.statut = 'terminee'
    elif succes == 0:
        campagne.statut = 'echec'
    else:
        campagne.statut = 'partiel'
    campagne.save(update_fields=['statut'])

    logger.info(f"[Celery] Campagne {campagne_id} terminée : {succes} succès, {echecs} échecs.")