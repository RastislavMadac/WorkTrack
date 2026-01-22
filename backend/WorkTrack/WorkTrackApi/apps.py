from django.apps import AppConfig

class WorkTrackApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'WorkTrackApi'

    def ready(self):
        # Načítanie signálov (aby fungovali triggery ako create_auth_token)
        import WorkTrackApi.signals