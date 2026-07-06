# campagnes/services.py
import re


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


def resoudre_variables_pour_client(client, mapping_variables, nombre_variables, variables_statiques=None):
    """
    Génère la liste de variables personnalisées pour UN client donné,
    à partir du mapping_variables de la campagne.

    mapping_variables format : {"1": "client.nom", "2": "client.ville", "3": "fixe:Promo Été"}
    Si mapping_variables est vide, retombe sur variables_statiques.
    """
    if not mapping_variables:
        return variables_statiques or []

    champs_autorises = {'nom', 'numero', 'email', 'ville', 'entreprise', 'segment'}
    resultat = []

    for index in range(1, nombre_variables + 1):
        cle = str(index)
        source = mapping_variables.get(cle, '')

        if source.startswith('client.'):
            champ = source.replace('client.', '').strip()
            if champ in champs_autorises:
                valeur = getattr(client, champ, '') or ''
                resultat.append(str(valeur))
            else:
                resultat.append('')
        elif source.startswith('fixe:'):
            resultat.append(source.replace('fixe:', '', 1))
        else:
            resultat.append('')

    return resultat


def construire_payload(template, numero, variables=None, header_url=None, header_media_id=None):
    """
    Construit le payload JSON pour l'API WhatsApp.
    Gère les headers TEXT, IMAGE, VIDEO, DOCUMENT et les boutons URL dynamiques.
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

    components = []

    if template.type_header == 'TEXT' and template.contenu_header:
        pass

    elif template.type_header in ('IMAGE', 'VIDEO', 'DOCUMENT') and (header_media_id or header_url):
        type_media = template.type_header.lower()

        if header_media_id:
            media_param = {"id": header_media_id}
        else:
            media_param = {"link": header_url}

        components.append({
            "type": "header",
            "parameters": [
                {
                    "type": type_media,
                    type_media: media_param
                }
            ]
        })

    if variables and template.nombre_variables > 0:
        components.append({
            "type": "body",
            "parameters": [
                {"type": "text", "text": str(v)} for v in variables
            ]
        })

    boutons_url_dynamiques = []
    for bouton in template.boutons.all():
        if bouton.type_bouton == 'URL' and '{{1}}' in (bouton.url or ''):
            boutons_url_dynamiques.append(bouton)

    for index, bouton in enumerate(boutons_url_dynamiques):
        suffixe_url = str(variables[-1]) if variables else ''
        components.append({
            "type": "button",
            "sub_type": "url",
            "index": str(index),
            "parameters": [
                {"type": "text", "text": suffixe_url}
            ]
        })

    if components:
        payload["template"]["components"] = components

    return payload