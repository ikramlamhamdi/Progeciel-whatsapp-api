from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .models import Campagne, Client, Envoi, TemplateWhatsApp
from .views import creer_template, envoyer_campagne, normaliser_numero, synchroniser_templates


class FakeMetaResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.payload = payload or {}

    def json(self):
        return self.payload


class TemplateWhatsAppApiTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch('campagnes.views.requests.post')
    def test_creer_template_avec_variables_envoie_exemples_meta(self, post_mock):
        post_mock.return_value = FakeMetaResponse(200, {'id': 'meta-template-id'})

        request = self.factory.post(
            '/templates/creer/',
            {
                'nom': 'Promo ete',
                'categorie': 'MARKETING',
                'langue': 'fr',
                'contenu_body': 'Bonjour {{1}}, reduction de {{2}}%.',
                'nombre_variables': 2,
                'exemples_variables': ['Ikram', '30'],
                'contenu_header': 'Offre speciale',
                'contenu_footer': 'STOP pour arreter',
            },
            format='json'
        )

        response = creer_template(request)

        self.assertEqual(response.status_code, 201)
        template = TemplateWhatsApp.objects.get(nom='promo_ete')
        self.assertEqual(template.nombre_variables, 2)
        payload = post_mock.call_args.kwargs['json']
        body = next(component for component in payload['components'] if component['type'] == 'BODY')
        self.assertEqual(body['example'], {'body_text': [['Ikram', '30']]})
        self.assertEqual(post_mock.call_args.kwargs['timeout'], 15)

    @patch('campagnes.views.requests.post')
    def test_creer_template_refuse_nombre_variables_incoherent(self, post_mock):
        request = self.factory.post(
            '/templates/creer/',
            {
                'nom': 'Promo incoherente',
                'categorie': 'MARKETING',
                'contenu_body': 'Bonjour {{1}}.',
                'nombre_variables': 2,
            },
            format='json'
        )

        response = creer_template(request)

        self.assertEqual(response.status_code, 400)
        post_mock.assert_not_called()
        self.assertFalse(TemplateWhatsApp.objects.filter(nom='promo_incoherente').exists())

    @patch('campagnes.views.requests.get')
    def test_synchroniser_templates_met_a_jour_les_statuts_meta(self, get_mock):
        get_mock.return_value = FakeMetaResponse(200, {
            'data': [
                {
                    'name': 'promo_meta',
                    'status': 'APPROVED',
                    'category': 'MARKETING',
                    'language': 'fr',
                    'components': [
                        {'type': 'HEADER', 'format': 'TEXT', 'text': 'Offre'},
                        {'type': 'BODY', 'text': 'Bonjour {{1}}, offre {{2}}.'},
                        {'type': 'FOOTER', 'text': 'STOP'},
                    ],
                }
            ]
        })

        request = self.factory.post('/templates/synchroniser/', {}, format='json')

        response = synchroniser_templates(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['templates_crees'], 1)
        template = TemplateWhatsApp.objects.get(nom='promo_meta')
        self.assertEqual(template.statut, 'approuve')
        self.assertEqual(template.nombre_variables, 2)
        self.assertEqual(template.contenu_header, 'Offre')
        self.assertEqual(template.contenu_footer, 'STOP')
        self.assertIsNotNone(template.date_approbation)


class EnvoiWhatsAppTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.client_whatsapp = Client.objects.create(
            nom='Ikram',
            numero='+212612345678',
            email='ikram@example.com'
        )
        self.template = TemplateWhatsApp.objects.create(
            nom='hello_template',
            categorie='MARKETING',
            langue='fr',
            statut='approuve',
            contenu_body='Bonjour {{1}}.',
            nombre_variables=1,
        )
        self.campagne = Campagne.objects.create(
            nom='Campagne test',
            template=self.template,
            variables_template=['Ikram']
        )

    def test_normaliser_numero_gere_plus_indicatif_et_zero(self):
        self.assertEqual(normaliser_numero('+212612345678'), '+212612345678')
        self.assertEqual(normaliser_numero('212612345678'), '+212612345678')
        self.assertEqual(normaliser_numero('0612345678'), '+212612345678')

    @patch('campagnes.views.requests.post')
    def test_envoyer_campagne_peut_etre_relancee_sans_doublon_envoi(self, post_mock):
        post_mock.return_value = FakeMetaResponse(200, {'messages': [{'id': 'wamid.test'}]})

        def build_request():
            return self.factory.post(
                f'/campagnes/{self.campagne.id}/envoyer/',
                {'template_id': self.template.id, 'variables': ['Ikram']},
                format='json'
            )

        first_response = envoyer_campagne(build_request(), self.campagne.id)
        second_response = envoyer_campagne(build_request(), self.campagne.id)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(Envoi.objects.count(), 1)
        envoi = Envoi.objects.get()
        self.assertEqual(envoi.statut, 'envoye')
        self.assertEqual(envoi.message_id_whatsapp, 'wamid.test')
