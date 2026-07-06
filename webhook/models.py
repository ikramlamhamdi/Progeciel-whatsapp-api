from django.db import models


class MessageRecu(models.Model):
    TYPE_CHOICES = [
        ('text', 'Texte'),
        ('audio', 'Vocal'),
        ('other', 'Autre'),
    ]

    STATUT_CHOICES = [
        ('nouveau', 'Nouveau'),
        ('lu', 'Lu'),
        ('en_traitement', 'En traitement'),
        ('repondu_auto', 'Répondu automatiquement'),
        ('repondu_manuel', 'Répondu manuellement'),
        ('escalade', 'Escaladé'),
        ('echec', 'Échec technique'),
    ]

    # Transitions autorisées : {statut_actuel: {statuts_suivants_possibles}}
    TRANSITIONS_AUTORISEES = {
        'nouveau': {'lu', 'en_traitement', 'escalade', 'echec'},
        'lu': {'en_traitement', 'repondu_manuel', 'escalade'},
        'en_traitement': {'repondu_auto', 'escalade', 'echec'},
        'repondu_auto': {'escalade'},
        'repondu_manuel': {'escalade'},
        'escalade': {'repondu_manuel', 'lu'},
        'echec': {'nouveau', 'en_traitement'},
    }

    wa_message_id   = models.CharField(max_length=255, unique=True)
    from_number     = models.CharField(max_length=20)
    type_message    = models.CharField(max_length=10, choices=TYPE_CHOICES)
    contenu_texte   = models.TextField(blank=True)
    media_id        = models.CharField(max_length=255, blank=True)
    statut          = models.CharField(max_length=20, choices=STATUT_CHOICES, default='nouveau')
    reponse_envoyee = models.TextField(blank=True)
    recu_le         = models.DateTimeField(auto_now_add=True)

    def changer_statut(self, nouveau_statut, *, forcer=False):
        """
        Change le statut en respectant les transitions autorisées.
        forcer=True permet de bypasser la règle (utile pour n8n qui est
        la source de vérité sur l'issue du traitement LLM).
        """
        if not forcer and nouveau_statut not in self.TRANSITIONS_AUTORISEES.get(self.statut, set()):
            raise ValueError(f'Transition interdite : {self.statut} → {nouveau_statut}')
        self.statut = nouveau_statut
        self.save(update_fields=['statut'])

    def __str__(self):
        return f"{self.from_number} — {self.type_message} — {self.statut}"