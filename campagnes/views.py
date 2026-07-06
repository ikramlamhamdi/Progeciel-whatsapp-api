# campagnes/views.py

import mimetypes
import re
import unicodedata

import openpyxl
import requests

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .models import (
    BoutonTemplateWhatsApp,
    Campagne,
    Client,
    Envoi,
    TemplateWhatsApp,
)
from .serializers import (
    CampagneSerializer,
    ClientSerializer,

    TemplateWhatsAppSerializer,
)
from .services import construire_payload, resoudre_variables_pour_client, normaliser_numero
from .tasks import envoyer_campagne_async

META_REQUEST_TIMEOUT = 15
GRAPH_VERSION = getattr(settings, 'META_GRAPH_VERSION', 'v23.0')


def normaliser_nom_template(nom):
    """Convertit un nom libre en nom compatible Meta: lettres, chiffres et underscores."""
    nom = unicodedata.normalize('NFKD', str(nom or ''))
    nom = nom.encode('ascii', 'ignore').decode('ascii')
    nom = re.sub(r'[\s-]+', '_', nom.strip().lower())
    nom = re.sub(r'[^a-z0-9_]', '', nom)
    nom = re.sub(r'_+', '_', nom).strip('_')
    return nom


def analyser_variables_body(contenu_body):
    """
    Valide les variables WhatsApp du body et retourne leur nombre.
    Meta attend des variables numeriques continues: {{1}}, {{2}}, ...
    """
    contenu_body = contenu_body or ''
    blocs_variables = re.findall(r'{{\s*([^}]+)\s*}}', contenu_body)
    variables_numeriques = re.findall(r'{{\s*(\d+)\s*}}', contenu_body)

    if len(blocs_variables) != len(variables_numeriques):
        return None, 'Les variables du body doivent etre numeriques: {{1}}, {{2}}, ...'

    if not variables_numeriques:
        return 0, None

    numeros = sorted({int(numero) for numero in variables_numeriques})
    attendus = list(range(1, max(numeros) + 1))
    if numeros != attendus:
        return None, 'Les variables doivent etre continues, par exemple {{1}}, {{2}}, {{3}}.'

    return max(numeros), None


def ajouter_exemples_aux_composants_meta(composants, exemples_variables=None, header_handle=None):
    """
    Ajoute les exemples requis par Meta sans les stocker dans composants_meta().
    La methode du modele garde la structure stable du template; la vue ajoute
    seulement les donnees d'exemple necessaires a la creation chez Meta.
    """
    for composant in composants:
        type_composant = str(composant.get('type', '')).upper()

        if type_composant == 'BODY' and exemples_variables:
            composant['example'] = {
                'body_text': [exemples_variables]
            }

        if type_composant == 'HEADER' and header_handle:
            composant['example'] = {
                'header_handle': [header_handle]
            }

    return composants


def formater_erreurs_validation(erreur):
    if hasattr(erreur, 'message_dict'):
        return erreur.message_dict
    return erreur.messages


def mapper_statut_meta(statut_meta):
    mapping_statut = {
        'approved': 'approuve',
        'pending': 'en_attente',
        'in_appeal': 'en_attente',
        'rejected': 'rejete',
        'paused': 'suspendu',
        'disabled': 'suspendu',
        'pending_deletion': 'suspendu',
    }
    return mapping_statut.get(str(statut_meta or '').lower(), 'en_attente')


def mapper_categorie_meta(categorie_meta):
    categories_valides = {choix[0] for choix in TemplateWhatsApp.CATEGORIE_CHOICES}
    categorie = str(categorie_meta or 'UTILITY').upper()
    return categorie if categorie in categories_valides else 'UTILITY'


def extraire_composants_template_meta(template_data):
    contenu_header = ''
    contenu_body = ''
    contenu_footer = ''

    for composant in template_data.get('components', []):
        type_composant = str(composant.get('type', '')).upper()

        if type_composant == 'HEADER' and composant.get('format') == 'TEXT':
            contenu_header = composant.get('text', '')
        elif type_composant == 'BODY':
            contenu_body = composant.get('text', '')
        elif type_composant == 'FOOTER':
            contenu_footer = composant.get('text', '')

    nombre_variables, erreur_variables = analyser_variables_body(contenu_body)
    if erreur_variables:
        nombre_variables = len(re.findall(r'{{\s*\d+\s*}}', contenu_body))

    return contenu_header, contenu_body, contenu_footer, nombre_variables


def sauvegarder_template_meta(template_data):
    nom = template_data.get('name')
    if not nom:
        return None, False

    statut_django = mapper_statut_meta(template_data.get('status', 'PENDING'))
    categorie_django = mapper_categorie_meta(template_data.get('category', 'UTILITY'))
    langue = template_data.get('language', 'en_US')
    contenu_header, contenu_body, contenu_footer, nombre_variables = extraire_composants_template_meta(template_data)

    template, cree = TemplateWhatsApp.objects.update_or_create(
        nom=nom,
        defaults={
            'categorie': categorie_django,
            'langue': langue,
            'statut': statut_django,
            'contenu_header': contenu_header,
            'contenu_body': contenu_body,
            'contenu_footer': contenu_footer,
            'nombre_variables': nombre_variables,
        }
    )

    champs_a_mettre_a_jour = []
    if not template.date_creation_meta:
        template.date_creation_meta = timezone.now()
        champs_a_mettre_a_jour.append('date_creation_meta')

    if statut_django == 'approuve' and not template.date_approbation:
        template.date_approbation = timezone.now()
        champs_a_mettre_a_jour.append('date_approbation')

    if champs_a_mettre_a_jour:
        template.save(update_fields=champs_a_mettre_a_jour)

    return template, cree


def reponse_erreur_meta(message, result, http_status=status.HTTP_400_BAD_REQUEST):
    erreur_meta = result.get('error', {}) if isinstance(result, dict) else {}
    error_data = erreur_meta.get('error_data') or {}

    data = {
        'erreur': message,
        'detail': erreur_meta.get('message', 'Erreur inconnue'),
        'details_meta': error_data.get('details'),
        'code': erreur_meta.get('code'),
        'sous_code': erreur_meta.get('error_subcode'),
        'fbtrace_id': erreur_meta.get('fbtrace_id'),
    }

    if settings.DEBUG:
        data['reponse_meta_complete'] = result

    return Response(data, status=http_status)


def valider_header_url(header_url, type_header):
    """
    Vérifie que header_url pointe vraiment vers un fichier média exploitable
    (et pas une page HTML, un viewer, une redirection cassée, etc.) avant
    d'envoyer quoi que ce soit à Meta.

    Retourne (est_valide: bool, message_erreur: str|None).
    """
    types_attendus = {
        'IMAGE': ('image/',),
        'VIDEO': ('video/',),
        'DOCUMENT': ('application/pdf', 'application/msword', 'application/vnd.'),
    }
    prefixes_attendus = types_attendus.get(type_header, ())

    try:
        reponse = requests.head(
            header_url, allow_redirects=True, timeout=8
        )
        if reponse.status_code in (405, 403) or 'content-type' not in reponse.headers:
            reponse = requests.get(
                header_url, allow_redirects=True, timeout=10, stream=True
            )

        if not (200 <= reponse.status_code < 300):
            return False, f'L\'URL retourne le statut HTTP {reponse.status_code} (pas accessible publiquement).'

        content_type = reponse.headers.get('content-type', '').split(';')[0].strip().lower()

        if not content_type:
            return False, 'Impossible de déterminer le type de fichier (Content-Type absent).'

        if not any(content_type.startswith(p) for p in prefixes_attendus):
            return False, (
                f'L\'URL ne pointe pas vers un fichier {type_header.lower()} valide '
                f'(Content-Type reçu : "{content_type}"). C\'est probablement une page web '
                f'(ex: un lien de résultats de recherche d\'images) plutôt qu\'un lien direct '
                f'vers le fichier.'
            )

        return True, None

    except requests.exceptions.RequestException as e:
        return False, f'Impossible d\'accéder à l\'URL : {str(e)}'


# ============================================================
# 0. API TEMPLATES WHATSAPP
# ============================================================

@api_view(['GET'])
def templates_list(request):
    """Liste tous les templates WhatsApp."""
    templates = TemplateWhatsApp.objects.all()
    serializer = TemplateWhatsAppSerializer(templates, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def templates_utilisables(request):
    """Liste uniquement les templates approuvés et utilisables."""
    templates = TemplateWhatsApp.objects.filter(statut='approuve')
    serializer = TemplateWhatsAppSerializer(templates, many=True)
    return Response(serializer.data)


@api_view(['POST'])
def synchroniser_templates(request):
    """
    Synchronise les templates depuis Meta vers la base locale.

    Utile apres la creation d'un template: Meta valide le statut de facon
    asynchrone, donc on doit relire l'etat reel depuis l'API Meta.
    """
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{settings.WHATSAPP_WABA_ID}/message_templates"
    headers = {
        'Authorization': f'Bearer {settings.WHATSAPP_TOKEN}',
    }

    templates_synchronises = []
    compteur_crees = 0
    compteur_mis_a_jour = 0

    try:
        while url:
            response = requests.get(url, headers=headers, timeout=META_REQUEST_TIMEOUT)
            result = response.json()

            if not 200 <= response.status_code < 300:
                return reponse_erreur_meta('Meta a refusé la synchronisation.', result)

            for template_data in result.get('data', []):
                template, cree = sauvegarder_template_meta(template_data)
                if not template:
                    continue

                templates_synchronises.append(template)
                if cree:
                    compteur_crees += 1
                else:
                    compteur_mis_a_jour += 1

            url = result.get('paging', {}).get('next')

    except Exception as e:
        return Response(
            {'erreur': f'Erreur réseau : {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    serializer = TemplateWhatsAppSerializer(templates_synchronises, many=True)
    return Response({
        'message': 'Synchronisation terminée.',
        'templates_crees': compteur_crees,
        'templates_mis_a_jour': compteur_mis_a_jour,
        'total': compteur_crees + compteur_mis_a_jour,
        'templates': serializer.data,
    })


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def upload_header_media_template(request):
    """
    Upload un fichier pour servir d'EXEMPLE de header lors de la CREATION
    d'un template (utilise la "resumable upload session" /app_id/uploads).
    Retourne un header_handle, valable uniquement pour creer_template().

    Ne PAS confondre avec upload_media_pour_envoi() ci-dessous, qui sert à
    envoyer un message réel avec un media_id.
    """
    fichier = request.FILES.get('fichier') or request.FILES.get('file')

    if not fichier:
        return Response(
            {'erreur': 'Aucun fichier reçu. Envoyez le fichier dans le champ "fichier".'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not settings.WHATSAPP_APP_ID:
        return Response(
            {'erreur': 'WHATSAPP_APP_ID est manquant dans .env/settings.py.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    if not settings.WHATSAPP_TOKEN:
        return Response(
            {'erreur': 'WHATSAPP_TOKEN est manquant dans .env/settings.py.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    content_type = fichier.content_type or mimetypes.guess_type(fichier.name)[0]

    types_acceptes = {
        'image/jpeg': 'IMAGE',
        'image/png': 'IMAGE',
        'video/mp4': 'VIDEO',
        'video/3gpp': 'VIDEO',
        'application/pdf': 'DOCUMENT',
        'application/msword': 'DOCUMENT',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'DOCUMENT',
        'application/vnd.ms-excel': 'DOCUMENT',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'DOCUMENT',
    }

    type_header_detecte = types_acceptes.get(content_type)

    if not type_header_detecte:
        return Response(
            {
                'erreur': 'Type de fichier non supporté pour un header WhatsApp.',
                'content_type': content_type,
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        session_url = f'https://graph.facebook.com/{GRAPH_VERSION}/{settings.WHATSAPP_APP_ID}/uploads'

        session_response = requests.post(
            session_url,
            params={
                'file_name': fichier.name,
                'file_length': fichier.size,
                'file_type': content_type,
                'access_token': settings.WHATSAPP_TOKEN,
            },
            timeout=30
        )

        try:
            session_result = session_response.json()
        except ValueError:
            session_result = {'raw': session_response.text}

        if not 200 <= session_response.status_code < 300:
            return Response(
                {
                    'erreur': 'Meta a refusé la création de session upload.',
                    'status_meta': session_response.status_code,
                    'detail': session_result.get('error', {}).get('message'),
                    'code': session_result.get('error', {}).get('code'),
                    'fbtrace_id': session_result.get('error', {}).get('fbtrace_id'),
                    'reponse_meta': session_result,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        upload_session_id = session_result.get('id')

        if not upload_session_id:
            return Response(
                {
                    'erreur': 'Meta n’a pas retourné d’ID de session upload.',
                    'reponse_meta': session_result,
                },
                status=status.HTTP_502_BAD_GATEWAY
            )

        fichier.seek(0)

        upload_response = requests.post(
            f'https://graph.facebook.com/{GRAPH_VERSION}/{upload_session_id}',
            headers={
                'Authorization': f'OAuth {settings.WHATSAPP_TOKEN}',
                'file_offset': '0',
            },
            data=fichier.read(),
            timeout=60
        )

        try:
            upload_result = upload_response.json()
        except ValueError:
            upload_result = {'raw': upload_response.text}

        if not 200 <= upload_response.status_code < 300:
            return Response(
                {
                    'erreur': 'Meta a refusé l’upload du média.',
                    'status_meta': upload_response.status_code,
                    'detail': upload_result.get('error', {}).get('message'),
                    'code': upload_result.get('error', {}).get('code'),
                    'fbtrace_id': upload_result.get('error', {}).get('fbtrace_id'),
                    'reponse_meta': upload_result,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        header_handle = upload_result.get('h')

        if not header_handle:
            return Response(
                {
                    'erreur': 'Meta n’a pas retourné de header_handle.',
                    'reponse_meta': upload_result,
                },
                status=status.HTTP_502_BAD_GATEWAY
            )

        return Response({
            'message': 'Média uploadé chez Meta avec succès.',
            'header_handle': header_handle,
            'type_header': type_header_detecte,
            'file_name': fichier.name,
            'content_type': content_type,
        })

    except Exception as e:
        return Response(
            {'erreur': f'Erreur lors de l’upload média : {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def upload_media_pour_envoi(request):
    """
    Upload un fichier local vers l'API Media de WhatsApp (PAS l'API "uploads"
    utilisée pour créer des templates) afin d'obtenir un media_id réutilisable
    pour ENVOYER un message (campagne ou test unique).

    Body (multipart/form-data) :
    {
        "fichier": <fichier image/vidéo/document>
    }

    Réponse :
    {
        "media_id": "1234567890",
        "type_header": "IMAGE",
        "file_name": "...",
        "content_type": "image/jpeg"
    }

    Le frontend doit appeler cet endpoint AVANT envoyer_campagne / envoyer_test_unique,
    puis transmettre le media_id obtenu dans le champ "header_media_id".
    """
    fichier = request.FILES.get('fichier') or request.FILES.get('file')

    if not fichier:
        return Response(
            {'erreur': 'Aucun fichier reçu. Envoyez le fichier dans le champ "fichier".'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not settings.WHATSAPP_PHONE_NUMBER_ID:
        return Response(
            {'erreur': 'WHATSAPP_PHONE_NUMBER_ID est manquant dans .env/settings.py.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    if not settings.WHATSAPP_TOKEN:
        return Response(
            {'erreur': 'WHATSAPP_TOKEN est manquant dans .env/settings.py.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    content_type = fichier.content_type or mimetypes.guess_type(fichier.name)[0]

    types_acceptes = {
        'image/jpeg': 'IMAGE',
        'image/png': 'IMAGE',
        'video/mp4': 'VIDEO',
        'video/3gpp': 'VIDEO',
        'application/pdf': 'DOCUMENT',
        'application/msword': 'DOCUMENT',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'DOCUMENT',
        'application/vnd.ms-excel': 'DOCUMENT',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'DOCUMENT',
    }

    type_header_detecte = types_acceptes.get(content_type)

    if not type_header_detecte:
        return Response(
            {
                'erreur': 'Type de fichier non supporté pour un header WhatsApp.',
                'content_type': content_type,
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    limites_taille = {
        'IMAGE': 5 * 1024 * 1024,
        'VIDEO': 16 * 1024 * 1024,
        'DOCUMENT': 100 * 1024 * 1024,
    }
    if fichier.size > limites_taille[type_header_detecte]:
        return Response(
            {
                'erreur': f'Fichier trop volumineux pour un header {type_header_detecte} '
                          f'(max {limites_taille[type_header_detecte] // (1024 * 1024)} Mo).'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    url_media = f'https://graph.facebook.com/{GRAPH_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/media'
    headers = {
        'Authorization': f'Bearer {settings.WHATSAPP_TOKEN}',
    }

    try:
        fichier.seek(0)
        fichiers_envoi = {
            'file': (fichier.name, fichier.read(), content_type),
        }
        data_envoi = {
            'messaging_product': 'whatsapp',
            'type': content_type,
        }

        response = requests.post(
            url_media, headers=headers, files=fichiers_envoi, data=data_envoi, timeout=60
        )

        try:
            result = response.json()
        except ValueError:
            result = {'raw': response.text}

        if not 200 <= response.status_code < 300:
            return Response(
                {
                    'erreur': 'Meta a refusé l’upload du média.',
                    'status_meta': response.status_code,
                    'detail': result.get('error', {}).get('message'),
                    'code': result.get('error', {}).get('code'),
                    'fbtrace_id': result.get('error', {}).get('fbtrace_id'),
                    'reponse_meta': result,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        media_id = result.get('id')

        if not media_id:
            return Response(
                {
                    'erreur': 'Meta n’a pas retourné de media_id.',
                    'reponse_meta': result,
                },
                status=status.HTTP_502_BAD_GATEWAY
            )

        return Response({
            'message': 'Média uploadé chez Meta avec succès.',
            'media_id': media_id,
            'type_header': type_header_detecte,
            'file_name': fichier.name,
            'content_type': content_type,
        })

    except Exception as e:
        return Response(
            {'erreur': f'Erreur lors de l’upload média : {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def creer_template(request):
    """
    Crée un template WhatsApp directement via l'API Meta,
    puis le sauvegarde localement si Meta l'accepte.
    """
    nom = normaliser_nom_template(request.data.get('nom'))
    categorie = str(request.data.get('categorie', '')).strip().upper()
    langue = str(request.data.get('langue', 'fr')).strip()
    contenu_body = str(request.data.get('contenu_body', '')).strip()
    contenu_header = str(request.data.get('contenu_header') or '').strip()
    contenu_footer = str(request.data.get('contenu_footer') or '').strip()
    type_header = str(
        request.data.get('type_header') or ('TEXT' if contenu_header else 'NONE')
    ).strip().upper()
    header_handle = str(
        request.data.get('header_handle') or request.data.get('exemple_header_handle') or ''
    ).strip()
    boutons_data = request.data.get('boutons') or request.data.get('buttons') or []

    if not nom or not categorie or not contenu_body:
        return Response(
            {'erreur': 'Les champs nom, categorie et contenu_body sont obligatoires.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    categories_valides = {choix[0] for choix in TemplateWhatsApp.CATEGORIE_CHOICES}
    if categorie not in categories_valides:
        return Response(
            {'erreur': f'Catégorie invalide. Valeurs acceptées : {sorted(categories_valides)}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    types_header_valides = {choix[0] for choix in TemplateWhatsApp.TYPE_HEADER_CHOICES}
    if type_header not in types_header_valides:
        return Response(
            {'erreur': f'Type de header invalide. Valeurs acceptées : {sorted(types_header_valides)}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if type_header in {'IMAGE', 'VIDEO', 'DOCUMENT'} and not header_handle:
        return Response(
            {
                'erreur': 'Pour un header média, fournissez header_handle après avoir uploadé le média chez Meta.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    if boutons_data and not isinstance(boutons_data, list):
        return Response(
            {'erreur': 'boutons doit être une liste.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if len(boutons_data) > 3:
        return Response(
            {'erreur': 'Un template WhatsApp ne doit pas dépasser 3 boutons.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if TemplateWhatsApp.objects.filter(nom=nom).exists():
        return Response(
            {'erreur': f'Le template "{nom}" existe déjà en base de données.'},
            status=status.HTTP_409_CONFLICT
        )

    if '{{' in contenu_header or '{{' in contenu_footer:
        return Response(
            {'erreur': 'Les variables ne sont pas encore supportées dans le header/footer.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    nombre_variables, erreur_variables = analyser_variables_body(contenu_body)
    if erreur_variables:
        return Response({'erreur': erreur_variables}, status=status.HTTP_400_BAD_REQUEST)

    nombre_variables_demande = request.data.get('nombre_variables')
    if nombre_variables_demande not in (None, ''):
        try:
            nombre_variables_demande = int(nombre_variables_demande)
        except (TypeError, ValueError):
            return Response(
                {'erreur': 'nombre_variables doit être un nombre entier.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if nombre_variables_demande != nombre_variables:
            return Response(
                {
                    'erreur': 'nombre_variables ne correspond pas aux variables présentes dans contenu_body.',
                    'attendu': nombre_variables,
                    'fourni': nombre_variables_demande,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

    exemples_variables = request.data.get('exemples_variables') or request.data.get('variables_exemple') or []
    if exemples_variables and not isinstance(exemples_variables, list):
        return Response(
            {'erreur': 'exemples_variables doit être une liste.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if nombre_variables:
        if not exemples_variables:
            exemples_variables = [f'exemple_{index}' for index in range(1, nombre_variables + 1)]

        if len(exemples_variables) != nombre_variables:
            return Response(
                {
                    'erreur': 'Le nombre d’exemples doit correspondre au nombre de variables.',
                    'attendu': nombre_variables,
                    'fourni': len(exemples_variables),
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        exemples_variables = [str(exemple) for exemple in exemples_variables]

    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{settings.WHATSAPP_WABA_ID}/message_templates"
    headers = {
        'Authorization': f'Bearer {settings.WHATSAPP_TOKEN}',
        'Content-Type': 'application/json'
    }

    try:
        with transaction.atomic():
            template = TemplateWhatsApp.objects.create(
                nom=nom,
                categorie=categorie,
                langue=langue,
                type_header=type_header,
                contenu_body=contenu_body,
                contenu_header=contenu_header,
                contenu_footer=contenu_footer,
                nombre_variables=nombre_variables,
                exemples_variables_body=exemples_variables,
                date_creation_meta=timezone.now(),
                statut='en_attente',
            )
            template.full_clean()

            for index, bouton_data in enumerate(boutons_data, start=1):
                if not isinstance(bouton_data, dict):
                    raise ValidationError({'boutons': 'Chaque bouton doit être un objet JSON.'})

                ordre = bouton_data.get('ordre') or index
                try:
                    ordre = int(ordre)
                except (TypeError, ValueError):
                    raise ValidationError({'boutons': 'Le champ ordre d’un bouton doit être un entier.'})

                bouton = BoutonTemplateWhatsApp(
                    template=template,
                    ordre=ordre,
                    type_bouton=str(
                        bouton_data.get('type_bouton') or bouton_data.get('type') or ''
                    ).strip().upper(),
                    texte=str(
                        bouton_data.get('texte') or bouton_data.get('text') or ''
                    ).strip(),
                    url=str(bouton_data.get('url') or '').strip(),
                    numero_telephone=str(
                        bouton_data.get('numero_telephone') or bouton_data.get('phone_number') or ''
                    ).strip(),
                )
                bouton.full_clean()
                bouton.save()

            composants = ajouter_exemples_aux_composants_meta(
                template.composants_meta(),
                exemples_variables=exemples_variables,
                header_handle=header_handle,
            )
            payload = {
                "name": nom,
                "language": langue,
                "category": categorie,
                "components": composants
            }

            response = requests.post(url, headers=headers, json=payload, timeout=META_REQUEST_TIMEOUT)
            result = response.json()

            if not 200 <= response.status_code < 300:
                transaction.set_rollback(True)
                return reponse_erreur_meta('Meta a refusé le template.', result)

            template_id_local = template.id
    except IntegrityError:
        return Response(
            {'erreur': f'Meta a accepté le template, mais "{nom}" existe déjà localement. Lancez sync_templates.'},
            status=status.HTTP_409_CONFLICT
        )
    except ValidationError as e:
        return Response(
            {'erreur': 'Données du template invalides.', 'details': formater_erreurs_validation(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'erreur': f'Erreur réseau : {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return Response(
        {
            'message': 'Template soumis à Meta avec succès. En attente d\'approbation.',
            'template_id_local': template_id_local,
            'template_id_meta': result.get('id'),
            'statut': 'en_attente',
        },
        status=status.HTTP_201_CREATED
    )


@api_view(['DELETE'])
def supprimer_template(request, template_id):
    """
    Supprime un template WhatsApp chez Meta puis localement.
    """
    try:
        template = TemplateWhatsApp.objects.get(id=template_id)
    except TemplateWhatsApp.DoesNotExist:
        return Response(
            {'erreur': 'Template non trouvé en base de données.'},
            status=status.HTTP_404_NOT_FOUND
        )

    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{settings.WHATSAPP_WABA_ID}/message_templates"
    headers = {
        'Authorization': f'Bearer {settings.WHATSAPP_TOKEN}',
        'Content-Type': 'application/json'
    }
    params = {
        "name": template.nom
    }

    try:
        response = requests.delete(url, headers=headers, params=params, timeout=META_REQUEST_TIMEOUT)
        result = response.json()
    except Exception as e:
        return Response(
            {'erreur': f'Erreur réseau : {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    if not 200 <= response.status_code < 300:
        return reponse_erreur_meta('Meta a refusé la suppression.', result)

    nom_template = template.nom
    template.delete()

    return Response(
        {
            'message': f'Template "{nom_template}" supprimé chez Meta et en base de données.',
        },
        status=status.HTTP_200_OK
    )


# ============================================================
# 1. API CLIENTS
# ============================================================

@api_view(['GET', 'POST'])
def clients_list(request):
    """
    GET  → Récupérer tous les clients
    POST → Ajouter un nouveau client
    """
    if request.method == 'GET':
        clients = Client.objects.all()
        serializer = ClientSerializer(clients, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        numero_normalise = Client.normaliser_numero(request.data.get('numero'))

        if not numero_normalise:
            return Response(
                {'erreur': 'Le numéro fourni est invalide.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if Client.objects.filter(numero=numero_normalise).exists():
            return Response(
                {'erreur': f'Un client avec ce numéro existe déjà.'},
                status=status.HTTP_409_CONFLICT
            )

        serializer = ClientSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response({'erreur': 'Données invalides.', 'details': serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)


# ============================================================
# 2. API IMPORT EXCEL
# ============================================================

@api_view(['POST'])
def importer_clients_excel(request):
    """
    Importer des clients depuis un fichier Excel (.xlsx)
    Format attendu : A=Nom, B=Numéro, C=Email, D=Ville, E=Entreprise, F=Segment
    """
    fichier = request.FILES.get('fichier')

    if not fichier:
        return Response(
            {'erreur': 'Aucun fichier fourni. Utilisez le champ "fichier".'},
            status=status.HTTP_400_BAD_REQUEST
        )

    segments_valides = {choix[0] for choix in Client.SEGMENT_CHOICES}

    try:
        wb = openpyxl.load_workbook(fichier)
        ws = wb.active
        clients_ajoutes = 0
        doublons_fichier = 0
        doublons_existants = 0
        numeros_invalides = 0
        numeros_vus = set()

        for row in ws.iter_rows(min_row=2, values_only=True):
            if row is None or all(cellule is None for cellule in row):
                continue

            nom = str(row[0]).strip() if len(row) > 0 and row[0] else ''
            numero_brut = str(row[1]).strip() if len(row) > 1 and row[1] else ''
            email = str(row[2]).strip() if len(row) > 2 and row[2] else ''
            ville = str(row[3]).strip() if len(row) > 3 and row[3] else ''
            entreprise = str(row[4]).strip() if len(row) > 4 and row[4] else ''
            segment = str(row[5]).strip().lower() if len(row) > 5 and row[5] else 'prospect'

            if segment not in segments_valides:
                segment = 'prospect'

            numero = Client.normaliser_numero(numero_brut)

            if not numero:
                numeros_invalides += 1
                continue

            if numero in numeros_vus:
                doublons_fichier += 1
                continue
            numeros_vus.add(numero)

            client, cree = Client.objects.get_or_create(
                numero=numero,
                defaults={
                    'nom': nom,
                    'email': email,
                    'ville': ville,
                    'entreprise': entreprise,
                    'segment': segment,
                }
            )
            if cree:
                clients_ajoutes += 1
            else:
                doublons_existants += 1

        return Response({
            'message': 'Import terminé !',
            'clients_ajoutes': clients_ajoutes,
            'doublons_ignores_fichier': doublons_fichier,
            'doublons_ignores_deja_en_base': doublons_existants,
            'numeros_invalides': numeros_invalides,
        })

    except Exception as e:
        return Response(
            {'erreur': f'Erreur lors de l\'import : {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
# ============================================================
# 3. API CAMPAGNES
# ============================================================

@api_view(['GET', 'POST'])
def campagnes_list(request):
    """
    GET  → Récupérer toutes les campagnes
    POST → Créer une nouvelle campagne
    """
    if request.method == 'GET':
        campagnes = Campagne.objects.all().order_by('-date_creation')
        serializer = CampagneSerializer(campagnes, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = CampagneSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================================
# 4. API ENVOI WHATSAPP VIA TEMPLATE
# ============================================================

@api_view(['POST'])
def envoyer_campagne(request, campagne_id):
    """
    Lance l'envoi d'une campagne WhatsApp en arrière-plan (tâche Celery).

    Cette vue ne fait plus la boucle d'envoi elle-même : elle valide,
    prépare les Envoi en statut 'en_attente', puis délègue le travail
    réel à un worker Celery. Ça évite de bloquer la requête HTTP (et le
    worker Django) pendant potentiellement plusieurs minutes sur une
    grosse campagne (ex: 600 destinataires).

    Body JSON :
    {
        "template_id": 1,                        (optionnel si déjà lié à la campagne)
        "variables": ["Ikram", "30"],
        "header_media_id": "1234567890",          (RECOMMANDÉ pour header IMAGE/VIDEO/DOCUMENT)
        "header_url": "https://...",              (fallback si pas de media_id)
        "client_ids": [1, 2, 3]                   (optionnel — tous les clients si absent)
    }

    Réponse immédiate (202) : la campagne passe en statut 'en_cours',
    la progression se suit via GET /campagnes/<id>/progression/.
    """
    try:
        campagne = Campagne.objects.get(id=campagne_id)
    except Campagne.DoesNotExist:
        return Response(
            {'erreur': 'Campagne non trouvée'},
            status=status.HTTP_404_NOT_FOUND
        )

    # ── Récupérer le template ──────────────────────────────────
    template = None
    variables = []

    template_id = request.data.get('template_id')
    if template_id:
        try:
            template = TemplateWhatsApp.objects.get(id=template_id)
            variables = request.data.get('variables', [])
        except TemplateWhatsApp.DoesNotExist:
            return Response({'erreur': 'Template non trouvé'}, status=404)
    elif campagne.template:
        template = campagne.template
        variables = campagne.variables_template
    else:
        return Response(
            {'erreur': 'Aucun template défini. Fournissez template_id ou liez un template à la campagne.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not template.est_utilisable():
        return Response(
            {
                'erreur': f'Le template "{template.nom}" n\'est pas approuvé.',
                'statut_actuel': template.get_statut_display()
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # ── Vérifier les variables ─────────────────────────────────
    mapping_variables = request.data.get('mapping_variables') or getattr(campagne, 'mapping_variables', None)

    if mapping_variables:
        if len(mapping_variables) != template.nombre_variables:
            return Response(
                {
                    'erreur': 'Nombre de variables incorrect.',
                    'attendu': template.nombre_variables,
                    'fourni': len(mapping_variables),
                    'variables_attendues': template.liste_variables()
                },
                status=status.HTTP_400_BAD_REQUEST
            )
    elif len(variables) != template.nombre_variables:
        return Response(
            {
                'erreur': 'Nombre de variables incorrect.',
                'attendu': template.nombre_variables,
                'fourni': len(variables),
                'variables_attendues': template.liste_variables()
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # ── Vérifier header média si template média ─────────────────
    header_media_id = str(request.data.get('header_media_id') or '').strip()
    header_url = str(request.data.get('header_url') or '').strip()

    if template.type_header in ('IMAGE', 'VIDEO', 'DOCUMENT'):
        if not header_media_id and not header_url:
            return Response(
                {
                    'erreur': (
                        f'Ce template a un header {template.type_header}. '
                        f'Uploadez un fichier via /upload-media-envoi/ et fournissez "header_media_id" '
                        f'(ou, à défaut, "header_url" avec un lien direct vers le fichier).'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not header_media_id and header_url:
            est_valide, message_erreur = valider_header_url(header_url, template.type_header)
            if not est_valide:
                return Response(
                    {'erreur': f'header_url invalide : {message_erreur}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

    # ── Récupérer les clients ──────────────────────────────────
    client_ids = request.data.get('client_ids', [])
    if client_ids:
        clients = Client.objects.filter(id__in=client_ids)
        if not clients.exists():
            return Response(
                {'erreur': 'Aucun client trouvé pour les IDs fournis.'},
                status=status.HTTP_400_BAD_REQUEST
            )
    else:
        clients = Client.objects.all()
        if not clients.exists():
            return Response(
                {'erreur': 'Aucun client dans la base de données.'},
                status=status.HTTP_400_BAD_REQUEST
            )

    # ── Préparer les Envoi et exclure les clients déjà servis avec succès ──
    # (permet de relancer une campagne 'partiel'/'echec' sans redoubler
    # les envois déjà passés en 'envoye' ou 'lu')
    clients_a_envoyer = []
    for client in clients:
        envoi_existant = Envoi.objects.filter(campagne=campagne, client=client).first()
        if envoi_existant and envoi_existant.statut in ('envoye', 'lu'):
            continue
        Envoi.objects.update_or_create(
            campagne=campagne, client=client,
            defaults={'statut': 'en_attente', 'erreur': '', 'message_id_whatsapp': ''}
        )
        clients_a_envoyer.append(client.id)

    if not clients_a_envoyer:
        return Response({
            'message': 'Tous les clients sélectionnés ont déjà reçu ce message avec succès.'
        }, status=status.HTTP_200_OK)

    campagne.statut = 'en_cours'
    campagne.save(update_fields=['statut'])

    envoyer_campagne_async.delay(
        campagne.id,
        clients_a_envoyer,
        template.id,
        variables,
        mapping_variables,
        header_media_id or None,
        header_url or None,
    )

    return Response({
        'message': 'Campagne lancée. Envoi en cours en arrière-plan.',
        'campagne': campagne.nom,
        'total_a_envoyer': len(clients_a_envoyer),
        'deja_envoyes': clients.count() - len(clients_a_envoyer),
    }, status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
def api_progression_campagne(request, campagne_id):
    """
    Endpoint léger de suivi de progression, à interroger périodiquement
    (polling) depuis le frontend pendant qu'une campagne est 'en_cours'.
    """
    try:
        campagne = Campagne.objects.get(id=campagne_id)
    except Campagne.DoesNotExist:
        return Response({'erreur': 'Campagne non trouvée'}, status=status.HTTP_404_NOT_FOUND)

    stats = campagne.statistiques()
    traites = stats['envoye'] + stats['lu'] + stats['echec']

    return Response({
        'statut': campagne.statut,
        'statut_display': campagne.get_statut_display(),
        'statistiques': stats,
        'traites': traites,
        'total': stats['total'],
        'termine': campagne.statut in ('terminee', 'partiel', 'echec'),
    })


@api_view(['GET'])
def detail_campagne(request, campagne_id):
    """
    Retourne les détails d'une campagne :
    - Infos générales
    - Statistiques
    - Liste de tous les envois avec statut par client
    """
    try:
        campagne = Campagne.objects.get(id=campagne_id)
    except Campagne.DoesNotExist:
        return Response(
            {'erreur': 'Campagne non trouvée'},
            status=status.HTTP_404_NOT_FOUND
        )

    envois = Envoi.objects.filter(campagne=campagne).select_related('client')

    envois_data = []
    for envoi in envois:
        envois_data.append({
            'client_id': envoi.client.id,
            'client_nom': envoi.client.nom,
            'client_numero': envoi.client.numero,
            'statut': envoi.statut,
            'date_envoi': envoi.date_envoi,
            'erreur': envoi.erreur,
            'message_id_whatsapp': envoi.message_id_whatsapp,
        })

    return Response({
        'id': campagne.id,
        'nom': campagne.nom,
        'statut': campagne.statut,
        'date_creation': campagne.date_creation,
        'template': campagne.template.nom if campagne.template else None,
        'statistiques': campagne.statistiques(),
        'envois': envois_data,
    })


# ============================================================
# 5. API TEST ENVOI UNIQUE
# ============================================================

@api_view(['POST'])
def envoyer_test_unique(request):
    """
    Envoyer un message test à UN SEUL numéro.
    Reste synchrone : un seul appel Meta, pas de risque de blocage.
    """
    numero = request.data.get('to')
    template_id = request.data.get('template_id')

    if not numero:
        return Response(
            {'erreur': 'Le numéro "to" est obligatoire'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not template_id:
        return Response(
            {'erreur': 'Le template_id est obligatoire'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        template = TemplateWhatsApp.objects.get(id=template_id)
    except TemplateWhatsApp.DoesNotExist:
        return Response(
            {'erreur': 'Template non trouvé'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not template.est_utilisable():
        return Response(
            {
                'erreur': f'Le template "{template.nom}" n\'est pas approuvé.',
                'statut_actuel': template.get_statut_display()
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    variables = request.data.get('variables', [])

    if len(variables) != template.nombre_variables:
        return Response(
            {
                'erreur': 'Nombre de variables incorrect.',
                'attendu': template.nombre_variables,
                'fourni': len(variables),
                'variables_attendues': template.liste_variables()
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    header_media_id = str(request.data.get('header_media_id') or '').strip()
    header_url = str(request.data.get('header_url') or '').strip()

    if template.type_header in ('IMAGE', 'VIDEO', 'DOCUMENT'):
        if not header_media_id and not header_url:
            return Response(
                {
                    'erreur': (
                        f'Ce template a un header {template.type_header}. '
                        f'Uploadez un fichier via /upload-media-envoi/ et fournissez "header_media_id" '
                        f'(ou, à défaut, "header_url" avec un lien direct vers le fichier).'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not header_media_id and header_url:
            est_valide, message_erreur = valider_header_url(header_url, template.type_header)
            if not est_valide:
                return Response(
                    {'erreur': f'header_url invalide : {message_erreur}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

    numero = normaliser_numero(numero)
    payload = construire_payload(
        template, numero, variables,
        header_url=header_url or None,
        header_media_id=header_media_id or None,
    )

    url_api = f"https://graph.facebook.com/{GRAPH_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        'Authorization': f'Bearer {settings.WHATSAPP_TOKEN}',
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(url_api, headers=headers, json=payload, timeout=META_REQUEST_TIMEOUT)
        result = response.json()

        if 200 <= response.status_code < 300:
            return Response({
                'success': True,
                'message': 'Message envoyé avec succès !',
                'whatsapp_response': result,
                'message_id': result.get('messages', [{}])[0].get('id')
            })
        else:
            return Response({
                'success': False,
                'error': result.get('error', {}).get('message', 'Erreur inconnue'),
                'code': result.get('error', {}).get('code'),
                'details': result
            }, status=response.status_code)

    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)