import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("realestate")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Scheduled tasks are managed via the database (django_celery_beat)
# and configured through the admin Scheduled Tasks page.
# See settings_app.services.TASK_REGISTRY for task definitions.
