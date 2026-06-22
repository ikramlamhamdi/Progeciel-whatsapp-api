# campagnes/models.py

from django.db import models


class TemplateWhatsApp(models.Model):
    """
    Représente un template WhatsApp approuvé (ou en attente) chez Meta.
    Permet de savoir quels templates sont disponibles pour l'envoi.
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

    nom = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nom du template (Meta)"
    )
    categorie = models.CharField(
        max_length=20,
        choices=CATEGORIE_CHOICES,
        verbose_name="Catégorie"
    )
    langue = models.CharField(
        max_length=10,
        default='en_US',
        verbose_name="Code langue (ex: en_US, fr, ar)"
    )
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default='en_attente',
        verbose_name="Statut Meta"
    )
    contenu_body = models.TextField(
        verbose_name="Contenu du body",
        help_text="Ex: Bonjour {{1}}, votre commande {{2}} est prête."
    )
    contenu_header = models.CharField(
        max_length=60,
        blank=True,
        verbose_name="Contenu du header (optionnel)",
        help_text="Texte affiché en gras au-dessus du message. Max 60 caractères."
    )
    contenu_footer = models.CharField(
        max_length=60,
        blank=True,
        verbose_name="Contenu du footer (optionnel)",
        help_text="Ex: Répondez STOP pour vous désabonner."
    )
    nombre_variables = models.PositiveIntegerField(
        default=0,
        verbose_name="Nombre de variables ({{1}}, {{2}}...)"
    )
    date_creation_meta = models.DateTimeField(
        blank=True, null=True,
        verbose_name="Date de création chez Meta"
    )
    date_approbation = models.DateTimeField(
        blank=True, null=True,
        verbose_name="Date d'approbation Meta"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description / Usage"
    )

    class Meta:
        verbose_name = "Template WhatsApp"
        verbose_name_plural = "Templates WhatsApp"
        ordering = ['-date_approbation', 'nom']

    def __str__(self):
        return f"{self.nom} ({self.categorie}) - {self.get_statut_display()}"

    def est_utilisable(self):
        """Vérifie si le template peut être utilisé pour l'envoi."""
        return self.statut == 'approuve'

    def liste_variables(self):
        """Retourne la liste des variables attendues."""
        return [f"{{{{{i}}}}}" for i in range(1, self.nombre_variables + 1)]


class Client(models.Model):
    """
    Représente un client de Progeciel System.
    Stocke le nom, le numéro WhatsApp et l'email.
    """
    nom = models.CharField(max_length=100, verbose_name="Nom complet")
    numero = models.CharField(max_length=20, unique=True, verbose_name="Numéro WhatsApp")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    date_ajout = models.DateTimeField(auto_now_add=True, verbose_name="Date d'ajout")

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        ordering = ['-date_ajout']

    def __str__(self):
        return f"{self.nom} ({self.numero})"


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

    # Valeurs des variables du template, dans l'ordre ({{1}}, {{2}}, ...)
    variables_template = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Valeurs des variables",
        help_text='["Ikram", "#CMD-1234", "250"]'
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
