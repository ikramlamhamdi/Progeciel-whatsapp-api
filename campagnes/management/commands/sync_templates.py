# campagnes/management/commands/sync_templates.py

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from campagnes.models import TemplateWhatsApp


class Command(BaseCommand):
    help = 'Synchronise les templates WhatsApp depuis Meta vers Django'

    def handle(self, *args, **options):
        self.stdout.write("🔄 Synchronisation des templates WhatsApp...")

        # URL de l'API Meta pour lister les templates
        url = f"https://graph.facebook.com/v18.0/{settings.WHATSAPP_WABA_ID}/message_templates"

        headers = {
            'Authorization': f'Bearer {settings.WHATSAPP_TOKEN}',
        }

        try:
            response = requests.get(url, headers=headers)
            result = response.json()

            if response.status_code != 200:
                self.stdout.write(self.style.ERROR(f"❌ Erreur API : {result}"))
                return

            templates_meta = result.get('data', [])
            self.stdout.write(f"📥 {len(templates_meta)} templates trouvés chez Meta")

            compteur_crees = 0
            compteur_mis_a_jour = 0

            for template_data in templates_meta:
                nom = template_data.get('name')
                statut_meta = template_data.get('status', 'PENDING').lower()
                categorie = template_data.get('category', 'UTILITY')
                langue = template_data.get('language', 'en_US')

                # Mapper le statut Meta vers ton modèle Django
                mapping_statut = {
                    'approved': 'approuve',
                    'pending': 'en_attente',
                    'rejected': 'rejete',
                    'paused': 'suspendu',
                    'disabled': 'suspendu',
                }
                statut_django = mapping_statut.get(statut_meta, 'en_attente')

                # Mapper la catégorie
                mapping_categorie = {
                    'MARKETING': 'MARKETING',
                    'UTILITY': 'UTILITY',
                    'AUTHENTICATION': 'AUTHENTICATION',
                }
                categorie_django = mapping_categorie.get(categorie.upper(), 'UTILITY')

                # Compter les variables dans le body
                body_text = ""
                nombre_variables = 0
                components = template_data.get('components', [])
                for comp in components:
                    if comp.get('type') == 'BODY':
                        body_text = comp.get('text', '')
                        # Compter les {{1}}, {{2}}...
                        nombre_variables = body_text.count('{{')

                # Créer ou mettre à jour le template dans Django
                template, cree = TemplateWhatsApp.objects.update_or_create(
                    nom=nom,
                    defaults={
                        'categorie': categorie_django,
                        'langue': langue,
                        'statut': statut_django,
                        'contenu_body': body_text,
                        'nombre_variables': nombre_variables,
                    }
                )

                if cree:
                    compteur_crees += 1
                    self.stdout.write(f"  ✅ Créé : {nom}")
                else:
                    compteur_mis_a_jour += 1
                    self.stdout.write(f"  🔄 Mis à jour : {nom}")

            self.stdout.write(self.style.SUCCESS(
                f"\n🎉 Terminé ! {compteur_crees} créés, {compteur_mis_a_jour} mis à jour."
            ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erreur : {str(e)}"))