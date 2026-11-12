from django.apps import AppConfig


class SettingsAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "settings_app"
    verbose_name = "Application Settings"

    def ready(self):
        from django.db import OperationalError, ProgrammingError

        try:
            from .services import ensure_tasks_exist, ensure_templates_exist
            from .models import EmailSettings

            ensure_tasks_exist()
            ensure_templates_exist()
            EmailSettings.load().apply_to_django_settings()
        except (OperationalError, ProgrammingError):
            # DB not yet migrated — skip seeding
            pass
