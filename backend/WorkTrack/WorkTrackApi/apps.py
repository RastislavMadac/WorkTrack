# WorkTrackApi/apps.py
from django.apps import AppConfig

class WorkTrackApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'WorkTrackApi'

    def ready(self):
        import WorkTrackApi.signals  # 👈 Načítanie signálov
