# Apprendre le backend WhatsApp pas a pas

Ce projet est un backend Django qui sert de pont entre une application client et
l'API WhatsApp Cloud de Meta.

## 1. C'est quoi un environnement Python ?

Python est le moteur qui execute ton code.

Un environnement virtuel est une boite separee pour les bibliotheques d'un
projet. Exemple :

- Projet WhatsApp : Django, Celery, requests, openpyxl
- Autre projet : peut utiliser d'autres versions

Sans environnement virtuel, tous les projets partagent les memes bibliotheques,
et ca devient vite confus.

Dans ce dossier, il y avait avant deux anciens environnements :

- `venv` : pointe vers un ancien Python 3.10 qui n'existe plus.
- `.venv` : contient des bibliotheques, mais son Python est instable.

Ils ont ete supprimes pour garder le projet propre.

On garde maintenant un seul environnement propre :

```powershell
.venv_stage
```

Pour utiliser ce projet, on lance les commandes avec :

```powershell
.\.venv_stage\Scripts\python.exe
```

Exemple :

```powershell
.\.venv_stage\Scripts\python.exe manage.py check
```

## 2. Les dependances du projet

Les dependances sont les bibliotheques dont le projet a besoin.

Elles sont listees dans :

```text
requirements.txt
```

Les plus importantes :

- `Django` : construit le backend.
- `djangorestframework` : transforme Django en API REST.
- `django-cors-headers` : autorise le frontend React a appeler le backend.
- `openpyxl` : lit les fichiers Excel.
- `requests` : appelle l'API WhatsApp Cloud.
- `celery` : lance les envois en arriere-plan.
- `redis` : sert de file d'attente pour Celery.
- `python-dotenv` : permet de mettre les secrets dans un fichier `.env`.

## 3. Carte mentale du projet

Les fichiers principaux :

```text
Stage_backend/settings.py     -> configuration globale du projet
Stage_backend/urls.py         -> routes principales du projet
campagnes/models.py           -> tables de la base de donnees
campagnes/serializers.py      -> conversion Python <-> JSON
campagnes/views.py            -> endpoints API
campagnes/urls.py             -> routes de l'application campagnes
campagnes/tasks.py            -> envoi WhatsApp en arriere-plan
```

## 4. Les 4 tables importantes

Dans `campagnes/models.py` :

- `Client` : une personne a contacter sur WhatsApp.
- `TemplateWhatsApp` : un template approuve ou non chez Meta.
- `Campagne` : une operation d'envoi, par exemple "Soldes juin".
- `Envoi` : le resultat d'un message envoye a un client.

Une campagne n'est pas le message lui-meme. Une campagne utilise un template,
puis cree plusieurs envois.

## 5. Le chemin d'une campagne

```text
1. On importe des clients depuis Excel
2. On recupere ou cree des templates WhatsApp
3. On cree une campagne
4. On lance la campagne
5. Django cree une tache Celery pour chaque client
6. Celery appelle Meta avec requests
7. Le resultat est sauvegarde dans Envoi
```

## 6. Commandes utiles

Verifier que Django est coherent :

```powershell
.\.venv_stage\Scripts\python.exe manage.py check
```

Voir les migrations :

```powershell
.\.venv_stage\Scripts\python.exe manage.py showmigrations
```

Lancer le serveur Django :

```powershell
.\.venv_stage\Scripts\python.exe manage.py runserver
```

Synchroniser les templates depuis Meta :

```powershell
.\.venv_stage\Scripts\python.exe manage.py sync_templates
```

## 7. Ce qu'on doit comprendre ensuite

Ordre conseille :

1. Comprendre `models.py`
2. Comprendre `serializers.py`
3. Comprendre `urls.py`
4. Comprendre `views.py`
5. Comprendre l'appel a Meta avec `requests`
6. Comprendre Celery et Redis
7. Ajouter le webhook Meta pour les statuts
