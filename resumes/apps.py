from django.apps import AppConfig


class ResumesConfig(AppConfig):
    """Register resume storage, analysis, and coaching features with Django."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "resumes"
