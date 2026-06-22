# campagnes/views.py

import re
import unicodedata

import requests
import openpyxl
from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Client, Campagne, Envoi, TemplateWhatsApp
from .serializers import ClientSerializer, CampagneSerializer, EnvoiSerializer, TemplateWhatsAppSerializer

META_REQUEST_TIMEOUT = 15


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


def construire_composants_template_meta(contenu_header, contenu_body, contenu_footer, exemples_variables):
    composants = []

    if contenu_header:
        composants.append({
            "type": "HEADER",
            "format": "TEXT",
            "text": contenu_header
        })

    body = {
        "type": "BODY",
        "text": contenu_body
    }
    if exemples_variables:
        body["example"] = {
            "body_text": [exemples_variables]
        }
    composants.append(body)

    if contenu_footer:
        composants.append({
            "type": "FOOTER",
            "text": contenu_footer
        })

    return composants


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
    url = f"https://graph.facebook.com/v18.0/{settings.WHATSAPP_WABA_ID}/message_templates"
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
def creer_template(request):
    """
    Crée un template WhatsApp directement via l'API Meta,
    puis le sauvegarde localement si Meta l'accepte.

    Body JSON attendu :
    {
        "nom": "promo_ete",
        "categorie": "MARKETING",
        "langue": "fr",
        "contenu_body": "Bonjour {{1}}, profitez de {{2}}% de réduction.",
        "nombre_variables": 2,
        "exemples_variables": ["Ikram", "30"],  (optionnel mais recommande si variables)
        "contenu_header": "Offre spéciale !",   (optionnel)
        "contenu_footer": "Répondez STOP pour vous désabonner."  (optionnel)
    }
    """
    # --- 1. Lire et valider les champs obligatoires ---
    nom = normaliser_nom_template(request.data.get('nom'))
    categorie = str(request.data.get('categorie', '')).strip().upper()
    langue = str(request.data.get('langue', 'fr')).strip()
    contenu_body = str(request.data.get('contenu_body', '')).strip()
    contenu_header = request.data.get('contenu_header', '').strip()
    contenu_footer = request.data.get('contenu_footer', '').strip()

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

    # --- 2. Construire les composants ---
    composants = construire_composants_template_meta(
        contenu_header,
        contenu_body,
        contenu_footer,
        exemples_variables
    )

    # --- 3. Appeler l'API Meta ---
    url = f"https://graph.facebook.com/v18.0/{settings.WHATSAPP_WABA_ID}/message_templates"
    headers = {
        'Authorization': f'Bearer {settings.WHATSAPP_TOKEN}',
        'Content-Type': 'application/json'
    }
    payload = {
        "name": nom,
        "language": langue,
        "category": categorie,
        "components": composants
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=META_REQUEST_TIMEOUT)
        result = response.json()
    except Exception as e:
        return Response(
            {'erreur': f'Erreur réseau : {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # --- 4. Si Meta refuse, on retourne l'erreur sans rien sauvegarder ---
    if not 200 <= response.status_code < 300:
        return reponse_erreur_meta('Meta a refusé le template.', result)

    # --- 5. Meta a accepté → on sauvegarde localement ---
    try:
        template = TemplateWhatsApp.objects.create(
            nom=nom,
            categorie=categorie,
            langue=langue,
            contenu_body=contenu_body,
            contenu_header=contenu_header,
            contenu_footer=contenu_footer,
            nombre_variables=nombre_variables,
            date_creation_meta=timezone.now(),
            statut='en_attente',  # Meta approuve de façon asynchrone
        )
    except IntegrityError:
        return Response(
            {'erreur': f'Meta a accepté le template, mais "{nom}" existe déjà localement. Lancez sync_templates.'},
            status=status.HTTP_409_CONFLICT
        )

    return Response(
        {
            'message': 'Template soumis à Meta avec succès. En attente d\'approbation.',
            'template_id_local': template.id,
            'template_id_meta': result.get('id'),
            'statut': 'en_attente',
        },
        status=status.HTTP_201_CREATED
    )

@api_view(['DELETE'])
def supprimer_template(request, template_id):
    """
    Supprime un template WhatsApp chez Meta puis localement.

    Meta identifie les templates par nom (pas par ID).
    On supprime d'abord chez Meta, puis localement seulement si Meta confirme.
    """
    # --- 1. Récupérer le template local ---
    try:
        template = TemplateWhatsApp.objects.get(id=template_id)
    except TemplateWhatsApp.DoesNotExist:
        return Response(
            {'erreur': 'Template non trouvé en base de données.'},
            status=status.HTTP_404_NOT_FOUND
        )

    # --- 2. Appeler l'API Meta ---
    url = f"https://graph.facebook.com/v18.0/{settings.WHATSAPP_WABA_ID}/message_templates"
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

    # --- 3. Si Meta refuse, on ne supprime rien localement ---
    if not 200 <= response.status_code < 300:
        return reponse_erreur_meta('Meta a refusé la suppression.', result)

    # --- 4. Meta a confirmé → on supprime localement ---
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
        serializer = ClientSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================================
# 2. API IMPORT EXCEL
# ============================================================

@api_view(['POST'])
def importer_clients_excel(request):
    """
    Importer des clients depuis un fichier Excel (.xlsx)
    Format attendu : Colonne A = Nom, Colonne B = Numéro, Colonne C = Email
    """
    fichier = request.FILES.get('fichier')

    if not fichier:
        return Response(
            {'erreur': 'Aucun fichier fourni. Utilisez le champ "fichier".'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        wb = openpyxl.load_workbook(fichier)
        ws = wb.active
        clients_ajoutes = 0
        clients_existant = 0

        for row in ws.iter_rows(min_row=2, values_only=True):
            nom = str(row[0]) if row[0] else ''
            numero = str(row[1]) if row[1] else ''
            email = str(row[2]) if len(row) > 2 and row[2] else ''

            if numero:
                client, cree = Client.objects.get_or_create(
                    numero=numero,
                    defaults={'nom': nom, 'email': email}
                )
                if cree:
                    clients_ajoutes += 1
                else:
                    clients_existant += 1

        return Response({
            'message': 'Import terminé !',
            'clients_ajoutes': clients_ajoutes,
            'clients_existant': clients_existant,
            'total_lignes': clients_ajoutes + clients_existant
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
# 4. API ENVOI WHATSAPP VIA TEMPLATE (AVEC GESTION TEMPLATE DJANGO)
# ============================================================

def normaliser_numero(numero):
    """Normalise un numéro de téléphone au format international."""
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
    """
    Construit le payload JSON pour l'API WhatsApp.
    """
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


@api_view(['POST'])
def envoyer_campagne(request, campagne_id):
    """
    Envoyer une campagne WhatsApp à TOUS les clients via TEMPLATE approuvé.
    Gère les templates via le modèle Django TemplateWhatsApp.

    Body JSON attendu (optionnel si déjà défini dans la campagne):
    {
        "template_id": 1,
        "variables": ["Ikram", "#CMD-1234", "250"]
    }
    """
    try:
        campagne = Campagne.objects.get(id=campagne_id)
    except Campagne.DoesNotExist:
        return Response(
            {'erreur': 'Campagne non trouvée'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Récupérer le template
    template = None
    variables = []

    # Priorité 1 : Template défini dans le body de la requête
    template_id = request.data.get('template_id')
    if template_id:
        try:
            template = TemplateWhatsApp.objects.get(id=template_id)
            variables = request.data.get('variables', [])
        except TemplateWhatsApp.DoesNotExist:
            return Response({'erreur': 'Template non trouvé'}, status=404)

    # Priorité 2 : Template déjà lié à la campagne
    elif campagne.template:
        template = campagne.template
        variables = campagne.variables_template

    else:
        return Response(
            {'erreur': 'Aucun template défini. Fournissez template_id ou liez un template à la campagne.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Vérifier que le template est utilisable
    if not template.est_utilisable():
        return Response(
            {
                'erreur': f'Le template "{template.nom}" n\'est pas approuvé.',
                'statut_actuel': template.get_statut_display()
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # Vérifier le nombre de variables
    if len(variables) != template.nombre_variables:
        return Response(
            {
                'erreur': f'Nombre de variables incorrect.',
                'attendu': template.nombre_variables,
                'fourni': len(variables),
                'variables_attendues': template.liste_variables()
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # Récupérer les clients
    clients = Client.objects.all()
    if not clients.exists():
        return Response(
            {'erreur': 'Aucun client dans la base de données'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # URL et Headers API Meta
    url = f"https://graph.facebook.com/v18.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        'Authorization': f'Bearer {settings.WHATSAPP_TOKEN}',
        'Content-Type': 'application/json'
    }

    succes = 0
    echecs = 0

    for client in clients:
        numero = normaliser_numero(client.numero)
        payload = construire_payload(template, numero, variables)

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=META_REQUEST_TIMEOUT)
            result = response.json()

            if 200 <= response.status_code < 300:
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
                succes += 1
            else:
                erreur_msg = result.get('error', {}).get('message', 'Erreur inconnue')
                Envoi.objects.update_or_create(
                    campagne=campagne,
                    client=client,
                    defaults={
                        'statut': 'echec',
                        'erreur': erreur_msg,
                        'date_envoi': timezone.now(),
                    }
                )
                echecs += 1

        except Exception as e:
            Envoi.objects.update_or_create(
                campagne=campagne,
                client=client,
                defaults={
                    'statut': 'echec',
                    'erreur': str(e),
                    'date_envoi': timezone.now(),
                }
            )
            echecs += 1

    # Mettre à jour le statut de la campagne
    # - tout est passé -> terminee
    # - rien n'est passé -> echec
    # - mélange de succès et d'échecs -> partiel (pour ne pas masquer les erreurs)
    if echecs == 0:
        campagne.statut = 'terminee'
    elif succes == 0:
        campagne.statut = 'echec'
    else:
        campagne.statut = 'partiel'

    campagne.save()

    return Response({
        'message': 'Campagne terminée !',
        'campagne': campagne.nom,
        'template_utilise': template.nom,
        'total_clients': clients.count(),
        'succes': succes,
        'echecs': echecs,
        'statut_final': campagne.get_statut_display()
    })


# ============================================================
# 5. API TEST ENVOI UNIQUE
# ============================================================

@api_view(['POST'])
def envoyer_test_unique(request):
    """
    Envoyer un message test à UN SEUL numéro (pour déboguer).
    Gère les templates via le modèle Django TemplateWhatsApp.

    Body JSON :
    {
        "to": "212689312392",
        "template_id": 1,
        "variables": ["Ikram", "30%"]
    }
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
                'erreur': f'Nombre de variables incorrect.',
                'attendu': template.nombre_variables,
                'fourni': len(variables),
                'variables_attendues': template.liste_variables()
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    numero = normaliser_numero(numero)
    payload = construire_payload(template, numero, variables)

    url = f"https://graph.facebook.com/v18.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        'Authorization': f'Bearer {settings.WHATSAPP_TOKEN}',
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=META_REQUEST_TIMEOUT)
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
