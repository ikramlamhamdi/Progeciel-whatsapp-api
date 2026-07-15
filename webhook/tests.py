from django.test import TestCase

# Create your tests here.

# webhook/tests.py
import hashlib
import hmac
import json

from django.test import TestCase, Client as DjangoTestClient
from django.urls import reverse
from django.test import override_settings

from campagnes.models import Client, Campagne, Envoi
from .models import MessageRecu


class ValidationSignatureHmacTests(TestCase):
    """
    Vérifie que le webhook Meta rejette toute requête POST dont la
    signature HMAC (X-Hub-Signature-256) est absente ou invalide,
    et accepte celles correctement signées avec WHATSAPP_APP_SECRET.
    """

    def setUp(self):
        self.client = DjangoTestClient()
        self.url = reverse('webhook_whatsapp')
        self.secret = 'secret_de_test'
        self.corps_requete = json.dumps({
            "entry": [{"changes": [{"value": {}}]}]
        }).encode('utf-8')

    def _signature_valide(self, corps: bytes) -> str:
        return 'sha256=' + hmac.new(
            self.secret.encode(), corps, hashlib.sha256
        ).hexdigest()

    @override_settings(WHATSAPP_APP_SECRET='secret_de_test')
    def test_requete_sans_signature_est_rejetee(self):
        response = self.client.post(
            self.url,
            data=self.corps_requete,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    @override_settings(WHATSAPP_APP_SECRET='secret_de_test')
    def test_requete_avec_signature_invalide_est_rejetee(self):
        response = self.client.post(
            self.url,
            data=self.corps_requete,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256='sha256=' + 'a' * 64,
        )
        self.assertEqual(response.status_code, 403)

    @override_settings(WHATSAPP_APP_SECRET='secret_de_test')
    def test_requete_avec_signature_valide_est_acceptee(self):
        signature = self._signature_valide(self.corps_requete)
        response = self.client.post(
            self.url,
            data=self.corps_requete,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=signature,
        )
        self.assertEqual(response.status_code, 200)


class TraitementStatutRegressionRangTests(TestCase):
    """
    Vérifie que _traiter_statut() ne fait jamais régresser un Envoi
    d'un statut "avancé" (ex: lu) vers un statut "moins avancé"
    (ex: envoye), même si Meta envoie les événements dans le désordre.
    """

    def setUp(self):
        self.client_test = Client.objects.create(
            nom='Client Test', numero='212600000001'
        )
        self.campagne = Campagne.objects.create(nom='Campagne Test')
        self.envoi = Envoi.objects.create(
            campagne=self.campagne,
            client=self.client_test,
            statut='lu',
            message_id_whatsapp='wamid.test123',
        )

    def test_statut_envoye_recu_apres_lu_ne_fait_pas_regresser(self):
        from webhook.views import _traiter_statut

        _traiter_statut({
            "id": "wamid.test123",
            "status": "sent",
        })

        self.envoi.refresh_from_db()
        self.assertEqual(
            self.envoi.statut, 'lu',
            "Le statut ne doit pas régresser de 'lu' vers 'envoye'."
        )

    def test_statut_lu_apres_envoye_progresse_normalement(self):
        from webhook.views import _traiter_statut

        self.envoi.statut = 'envoye'
        self.envoi.save(update_fields=['statut'])

        _traiter_statut({
            "id": "wamid.test123",
            "status": "read",
        })

        self.envoi.refresh_from_db()
        self.assertEqual(self.envoi.statut, 'lu')

    def test_echec_est_toujours_enregistre_avec_le_detail_erreur(self):
        from webhook.views import _traiter_statut

        self.envoi.statut = 'envoye'
        self.envoi.save(update_fields=['statut'])

        _traiter_statut({
            "id": "wamid.test123",
            "status": "failed",
            "errors": [{
                "code": 131049,
                "title": "Message not delivered",
                "message": "Ecosystem engagement limit"
            }]
        })

        self.envoi.refresh_from_db()
        self.assertEqual(self.envoi.statut, 'echec')
        self.assertIn('131049', self.envoi.erreur)


class ChangerStatutStateMachineTests(TestCase):
    """
    Vérifie que MessageRecu.changer_statut() respecte bien
    TRANSITIONS_AUTORISEES quand forcer=False, et que forcer=True
    bypass correctement la règle (comportement voulu pour n8n).
    """

    def setUp(self):
        self.message = MessageRecu.objects.create(
            wa_message_id='wamid.msg001',
            from_number='212600000002',
            type_message='text',
            contenu_texte='Bonjour',
            statut='nouveau',
        )

    def test_transition_autorisee_reussit(self):
        # nouveau → lu est autorisé
        self.message.changer_statut('lu', forcer=False)
        self.assertEqual(self.message.statut, 'lu')

    def test_transition_interdite_leve_value_error(self):
        # nouveau → repondu_manuel n'est PAS dans TRANSITIONS_AUTORISEES['nouveau']
        with self.assertRaises(ValueError):
            self.message.changer_statut('repondu_manuel', forcer=False)

        # le statut ne doit pas avoir changé après l'échec
        self.message.refresh_from_db()
        self.assertEqual(self.message.statut, 'nouveau')

    def test_forcer_true_bypass_la_transition_interdite(self):
        # nouveau → repondu_manuel est interdit, mais forcer=True doit passer
        self.message.changer_statut('repondu_manuel', forcer=True)
        self.assertEqual(self.message.statut, 'repondu_manuel')

    def test_transition_depuis_escalade_vers_repondu_manuel(self):
        self.message.statut = 'escalade'
        self.message.save(update_fields=['statut'])

        self.message.changer_statut('repondu_manuel', forcer=False)
        self.assertEqual(self.message.statut, 'repondu_manuel')