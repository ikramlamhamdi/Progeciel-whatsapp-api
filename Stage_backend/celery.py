# Stage_backend/celery.py

import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Stage_backend.settings')

app = Celery('Stage_backend')

app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-découvre les tâches dans les apps Django
app.autodiscover_tasks()