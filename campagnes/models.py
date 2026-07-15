# campagnes/models.py

from django.db import models
from django.core.exceptions import ValidationError
import re

class TemplateWhatsApp(models.Model):
    """
    Représente un template WhatsApp approuvé ou en attente chez Meta.
    Structure réelle : Header optionnel, Body obligatoire, Footer optionnel, Buttons optionnels.
    """

    STATUT_CHOICES = [
        ('en_attente', 'En attente de validation'),
        ('approuve', 'Approuvé'),
        ('rejete', 'Rejeté'),
        ('suspendu', 'Suspendu'),
    ]

    CATEGORIE_CHOICES = [
        ('MARKETING', 'Marketing'),
        ('UTILITY', 'Utilitaire'),
        ('AUTHENTICATION', 'Authentification'),
    ]

    TYPE_HEADER_CHOICES = [
        ('NONE', 'Aucun'),
        ('TEXT', 'Texte'),
        ('IMAGE', 'Image'),
        ('VIDEO', 'Vidéo'),
        ('DOCUMENT', 'Document'),
    ]

    nom = models.CharField(max_length=100, unique=True, verbose_name="Nom du template Meta")
    categorie = models.CharField(max_length=20, choices=CATEGORIE_CHOICES, verbose_name="Catégorie")
    langue = models.CharField(max_length=10, default='en_US', verbose_name="Code langue")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente', verbose_name="Statut Meta")
    template_id_meta = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="ID Meta du template",
        help_text="ID retourné par Meta à la création (obligatoire pour éditer le template ensuite)."
    )

    type_header = models.CharField(
        max_length=20,
        choices=TYPE_HEADER_CHOICES,
        default='NONE',
        verbose_name="Type de header"
    )
    contenu_header = models.CharField(
        max_length=60,
        blank=True,
        verbose_name="Texte du header",
        help_text="Utilisé seulement si le type de header est TEXT. Max 60 caractères."
    )
    fichier_header_exemple = models.FileField(
        upload_to='whatsapp/templates/headers/',
        blank=True,
        null=True,
        verbose_name="Fichier exemple du header",
        help_text="Image, vidéo ou document exemple pour les headers média."
    )

    contenu_body = models.TextField(
        verbose_name="Contenu du body",
        help_text="Ex: Bonjour {{1}}, votre commande {{2}} est prête.",
        blank=True,
        default=""
    )
    nombre_variables = models.PositiveIntegerField(
        default=0,
        verbose_name="Nombre de variables dans le body"
    )
    exemples_variables_body = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Exemples des variables body",
        help_text='Ex: ["Ali", "CMD-123"]'
    )

    contenu_footer = models.CharField(
        max_length=60,
        blank=True,
        verbose_name="Contenu du footer",
        help_text="Texte optionnel affiché sous le body. Max 60 caractères."
    )
    # ==========================
    # Champs spécifiques AUTHENTICATION
    # ==========================

    add_security_recommendation = models.BooleanField(
        default=True,
        verbose_name="Ajouter la recommandation de sécurité"
    )

    code_expiration_minutes = models.PositiveSmallIntegerField(
        default=10,
        blank=True,
        null=True,
        verbose_name="Durée d'expiration du code"
    )

    OTP_TYPE_CHOICES = [
        ('COPY_CODE', 'Copy Code'),
        ('ONE_TAP', 'One Tap'),
        ('ZERO_TAP', 'Zero Tap'),
    ]

    otp_type = models.CharField(
        max_length=20,
        choices=OTP_TYPE_CHOICES,
        default='COPY_CODE'
    )

    otp_button_text = models.CharField(
        max_length=25,
        default='Copier le code'
    )

    date_creation_meta = models.DateTimeField(blank=True, null=True, verbose_name="Date de création chez Meta")
    date_approbation = models.DateTimeField(blank=True, null=True, verbose_name="Date d'approbation Meta")
    description = models.TextField(blank=True, verbose_name="Description / Usage")

    class Meta:
        verbose_name = "Template WhatsApp"
        verbose_name_plural = "Templates WhatsApp"
        ordering = ['-date_approbation', 'nom']

    def __str__(self):
        return f"{self.nom} ({self.categorie}) - {self.get_statut_display()}"

    def clean(self):
        if self.categorie == "AUTHENTICATION":
            return
        errors = {}

        if self.type_header == 'TEXT' and not self.contenu_header:
            errors['contenu_header'] = "Le texte du header est obligatoire si le header est de type TEXT."

        if self.type_header in ['IMAGE', 'VIDEO', 'DOCUMENT'] and self.contenu_header:
            errors['contenu_header'] = "Un header média ne doit pas avoir de texte header."

        if self.type_header == 'NONE' and (self.contenu_header or self.fichier_header_exemple):
            errors['type_header'] = "Choisissez un type de header si vous ajoutez un contenu header."

        if errors:
            raise ValidationError(errors)

    def est_utilisable(self):
        return self.statut == 'approuve'

    def liste_variables(self):
        return [f"{{{{{i}}}}}" for i in range(1, self.nombre_variables + 1)]

    def composants_meta(self):
        """
        Construit les composants attendus par Meta.

        - MARKETING
        - UTILITY
        - AUTHENTICATION
        """

        # =====================================================
        # AUTHENTICATION
        # =====================================================

        if self.categorie == "AUTHENTICATION":

            composants = [
                {
                    "type": "BODY",
                    "add_security_recommendation": self.add_security_recommendation
                }
            ]

            if self.code_expiration_minutes:
                composants.append({
                    "type": "FOOTER",
                    "code_expiration_minutes": self.code_expiration_minutes
                })

            composants.append({
                "type": "BUTTONS",
                "buttons": [
                    {
                        "type": "OTP",
                        "otp_type": self.otp_type,
                        "text": self.otp_button_text
                    }
                ]
            })

            return composants

        # =====================================================
        # MARKETING / UTILITY
        # =====================================================

        composants = []

        if self.type_header != 'NONE':

            header = {
                "type": "HEADER",
                "format": self.type_header,
            }

            if self.type_header == "TEXT":
                header["text"] = self.contenu_header

            composants.append(header)

        composants.append({
            "type": "BODY",
            "text": self.contenu_body,
        })

        if self.contenu_footer:
            composants.append({
                "type": "FOOTER",
                "text": self.contenu_footer,
            })

        boutons = [
            bouton.as_meta_button()
            for bouton in self.boutons.all().order_by("ordre")
        ]

        if boutons:
            composants.append({
                "type": "BUTTONS",
                "buttons": boutons
            })

        return composants


class BoutonTemplateWhatsApp(models.Model):
    TYPE_BOUTON_CHOICES = [
        ('QUICK_REPLY', 'Réponse rapide'),
        ('URL', 'Lien'),
        ('PHONE_NUMBER', 'Numéro de téléphone'),
    ]

    template = models.ForeignKey(
        TemplateWhatsApp,
        on_delete=models.CASCADE,
        related_name='boutons',
        verbose_name="Template WhatsApp"
    )
    ordre = models.PositiveSmallIntegerField(default=1, verbose_name="Ordre")
    type_bouton = models.CharField(max_length=20, choices=TYPE_BOUTON_CHOICES, verbose_name="Type de bouton")
    texte = models.CharField(max_length=25, verbose_name="Texte du bouton")

    url = models.URLField(blank=True, verbose_name="URL")
    numero_telephone = models.CharField(max_length=30, blank=True, verbose_name="Numéro de téléphone")

    class Meta:
        verbose_name = "Bouton de template WhatsApp"
        verbose_name_plural = "Boutons de template WhatsApp"
        ordering = ['template', 'ordre']
        constraints = [
            models.UniqueConstraint(
                fields=['template', 'ordre'],
                name='unique_ordre_bouton_template_whatsapp'
            )
        ]

    def __str__(self):
        return f"{self.template.nom} - {self.texte}"

    def clean(self):
        errors = {}

        if self.ordre < 1 or self.ordre > 3:
            errors['ordre'] = "Un template WhatsApp ne doit pas dépasser 3 boutons."

        if self.template_id:
            boutons_existants = BoutonTemplateWhatsApp.objects.filter(template_id=self.template_id)
            if self.pk:
                boutons_existants = boutons_existants.exclude(pk=self.pk)

            if not self.pk and boutons_existants.count() >= 3:
                errors['template'] = "Ce template a déjà 3 boutons."

        if self.type_bouton == 'QUICK_REPLY':
            if self.url or self.numero_telephone:
                errors['type_bouton'] = "Un bouton QUICK_REPLY ne doit pas avoir d'URL ni de numéro."

        elif self.type_bouton == 'URL':
            if not self.url:
                errors['url'] = "L'URL est obligatoire pour un bouton URL."
            if self.numero_telephone:
                errors['numero_telephone'] = "Un bouton URL ne doit pas avoir de numéro."

        elif self.type_bouton == 'PHONE_NUMBER':
            if not self.numero_telephone:
                errors['numero_telephone'] = "Le numéro est obligatoire pour un bouton téléphone."
            if self.url:
                errors['url'] = "Un bouton téléphone ne doit pas avoir d'URL."

        if errors:
            raise ValidationError(errors)

    def as_meta_button(self):
        if self.type_bouton == 'QUICK_REPLY':
            return {
                "type": "QUICK_REPLY",
                "text": self.texte,
            }

        if self.type_bouton == 'URL':
            return {
                "type": "URL",
                "text": self.texte,
                "url": self.url,
            }

        if self.type_bouton == 'PHONE_NUMBER':
            return {
                "type": "PHONE_NUMBER",
                "text": self.texte,
                "phone_number": self.numero_telephone,
            }

        return {}


class Client(models.Model):
    """
    Représente un client de Progeciel System.
    """
    SEGMENT_CHOICES = [
        ('prospect', 'Prospect'),
        ('actif', 'Actif'),
        ('inactif', 'Inactif'),
        ('vip', 'VIP'),
    ]

    nom = models.CharField(max_length=100, verbose_name="Nom complet")
    numero = models.CharField(max_length=20, unique=True, verbose_name="Numéro WhatsApp")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    ville = models.CharField(max_length=100, blank=True, verbose_name="Ville")
    entreprise = models.CharField(max_length=100, blank=True, verbose_name="Entreprise")
    segment = models.CharField(
        max_length=20,
        choices=SEGMENT_CHOICES,
        default='prospect',
        verbose_name="Segment"
    )
    date_ajout = models.DateTimeField(auto_now_add=True, verbose_name="Date d'ajout")

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        ordering = ['-date_ajout']

    def __str__(self):
        return f"{self.nom} ({self.numero})"

    @staticmethod
    def normaliser_numero(numero):
        """Normalise vers 212XXXXXXXXX (12 chiffres, sans +). Retourne None si invalide."""
        brut = re.sub(r'[^\d+]', '', str(numero or '').strip())
        brut = brut.removeprefix('+')

        if brut.startswith('00'):
            brut = brut[2:]
        if brut.startswith('0'):
            brut = brut[1:]
        if not brut.startswith('212'):
            brut = f'212{brut}'

        if len(brut) != 12 or not brut.isdigit():
            return None

        return brut

    def save(self, *args, **kwargs):
        numero_normalise = self.normaliser_numero(self.numero)
        if numero_normalise:
            self.numero = numero_normalise
        super().save(*args, **kwargs)

class Campagne(models.Model):
    """
    Représente une campagne marketing WhatsApp.
    Le contenu réellement envoyé provient du TemplateWhatsApp lié,
    pas d'un texte libre (WhatsApp marketing impose l'usage de templates approuvés).
    """
    STATUT_CHOICES = [
        ('brouillon', 'Brouillon'),
        ('programmee', 'Programmée'),
        ('en_cours', 'En cours d\'envoi'),
        ('terminee', 'Terminée'),
        ('partiel', 'Terminée avec erreurs'),
        ('echec', 'Échec'),
    ]

    nom = models.CharField(max_length=200, verbose_name="Nom de la campagne")

    # Template WhatsApp utilisé pour cette campagne
    template = models.ForeignKey(
        TemplateWhatsApp,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campagnes',
        verbose_name="Template WhatsApp utilisé"
    )

    # Valeurs des variables du template, dans l'ordre ({{1}}, {{2}}, ...) — utilisé si pas de mapping
    variables_template = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Valeurs des variables (statique)",
        help_text='["Ikram", "#CMD-1234", "250"]'
    )

    # Mapping dynamique : chaque variable peut pointer vers un champ client ou une valeur fixe
    mapping_variables = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Mapping des variables",
        help_text='Ex: {"1": "client.nom", "2": "client.ville", "3": "fixe:Promo Été"}'
    )

    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    date_envoi = models.DateTimeField(blank=True, null=True, verbose_name="Date d'envoi programmée")
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default='brouillon',
        verbose_name="Statut"
    )

    class Meta:
        verbose_name = "Campagne"
        verbose_name_plural = "Campagnes"
        ordering = ['-date_creation']

    def __str__(self):
        return self.nom

    def statistiques(self):
        """
        Calcule les statistiques d'envoi à la volée depuis la table Envoi,
        en une seule requête SQL groupée. Toujours à jour, y compris après
        que les webhooks Meta aient mis à jour le statut de certains Envoi
        (ex: 'envoye' -> 'lu', ou un échec détecté tardivement).
        """
        compteurs = self.envois.values('statut').annotate(total=models.Count('id'))
        resultat = {'total': 0, 'en_attente': 0, 'envoye': 0, 'lu': 0, 'echec': 0}
        for ligne in compteurs:
            resultat[ligne['statut']] = ligne['total']
            resultat['total'] += ligne['total']
        return resultat


class Envoi(models.Model):
    """
    Représente un message envoyé à un client spécifique dans une campagne.
    C'est l'historique de chaque envoi.
    """
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('envoye', 'Envoyé'),
        ('lu', 'Lu par le client'),
        ('echec', 'Échec'),
    ]

    campagne = models.ForeignKey(
        Campagne,
        on_delete=models.CASCADE,
        related_name='envois',
        verbose_name="Campagne"
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='messages_recus',
        verbose_name="Client"
    )
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default='en_attente',
        verbose_name="Statut"
    )
    date_envoi = models.DateTimeField(blank=True, null=True, verbose_name="Date d'envoi")
    message_id_whatsapp = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="ID Message WhatsApp"
    )
    erreur = models.TextField(blank=True, null=True, verbose_name="Message d'erreur")

    class Meta:
        verbose_name = "Envoi de message"
        verbose_name_plural = "Envois de messages"
        ordering = ['-date_envoi']
        unique_together = ['campagne', 'client']

    def __str__(self):
        return f"{self.campagne.nom} → {self.client.nom} [{self.statut}]"