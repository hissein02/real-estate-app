from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

INTERNAL_IPS = ["127.0.0.1"]

# Show emails in console during development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Disable password validation in dev for convenience
AUTH_PASSWORD_VALIDATORS = []

# More verbose logging in dev
LOGGING["root"]["level"] = "DEBUG"  # noqa: F405
