from waitress import serve
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Stage_backend.settings')
django.setup()

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

if __name__ == '__main__':
    print("Démarrage du serveur Waitress sur http://127.0.0.1:8001")
    serve(application, host='127.0.0.1', port=8001, threads=8)