# Etape 1 - Comprendre `campagnes/models.py`

Dans Django, un `model` represente une table dans la base de donnees.

Si tu ecris :

```python
class Client(models.Model):
    nom = models.CharField(max_length=100)
```

Django comprend :

```text
Je dois creer une table Client avec une colonne nom.
```

Dans ton application WhatsApp, `models.py` decrit les objets importants du
metier.

## 1. `TemplateWhatsApp`

Un template WhatsApp est un modele de message cree et approuve chez Meta.

Exemple :

```text
Bonjour {{1}}, votre commande {{2}} est prete.
```

Ici, `{{1}}` et `{{2}}` sont des variables. Au moment de l'envoi, on les
remplace par de vraies valeurs.

Cette table stocke :

- le nom du template chez Meta ;
- sa categorie : marketing, utilitaire, authentification ;
- sa langue ;
- son statut : approuve, en attente, rejete, suspendu ;
- le contenu du body ;
- le nombre de variables.

Pourquoi c'est important ?

Parce que WhatsApp n'autorise pas l'envoi marketing libre a n'importe qui.
Pour une campagne, on doit utiliser un template approuve.

## 2. `Client`

Un client est une personne a qui on peut envoyer un message WhatsApp.

Cette table stocke :

- son nom ;
- son numero WhatsApp ;
- son email si disponible ;
- la date d'ajout.

Dans ton cas, les clients peuvent venir d'un fichier Excel.

## 3. `Campagne`

Une campagne represente une operation d'envoi.

Exemple :

```text
Campagne : Soldes juin 2026
Template : promo
Clients : tous les clients importes
```

Une campagne ne contient pas directement 500 messages. Elle dit plutot :

```text
Je veux envoyer tel template a une liste de clients.
```

Cette table stocke :

- le nom de la campagne ;
- le template utilise ;
- les variables du template ;
- la date de creation ;
- la date d'envoi programmee ;
- le statut : brouillon, en cours, terminee, echec.

## 4. `Envoi`

Un envoi est le resultat pour un client precis.

Si une campagne cible 500 clients, on aura jusqu'a 500 lignes `Envoi`.

Exemple :

```text
Campagne Soldes juin -> Client Ahmed -> envoye
Campagne Soldes juin -> Client Ikram -> echec
```

Cette table stocke :

- la campagne ;
- le client ;
- le statut du message ;
- la date d'envoi ;
- l'identifiant du message chez WhatsApp ;
- l'erreur si l'envoi echoue.

## 5. Relation entre les tables

La logique globale :

```text
TemplateWhatsApp
        ^
        |
Campagne -----> Envoi <----- Client
```

En phrase simple :

```text
Une campagne utilise un template.
Une campagne cree plusieurs envois.
Chaque envoi concerne un seul client.
```

## 6. Exemple complet

Imaginons une campagne de soldes pour 3 clients.

```text
TemplateWhatsApp
  nom = promo
  contenu = Bonjour {{1}}, profitez de nos soldes.

Client
  Ahmed
  Ikram
  Sara

Campagne
  nom = Soldes ete
  template = promo

Envoi
  Soldes ete -> Ahmed -> envoye
  Soldes ete -> Ikram -> envoye
  Soldes ete -> Sara -> echec
```

Ce schema est le coeur de ton backend.

Avant de comprendre l'API WhatsApp, il faut bien comprendre ces 4 tables.
