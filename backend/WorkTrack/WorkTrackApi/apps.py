from django.apps import AppConfig

class WorkTrackApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'WorkTrackApi'

    def ready(self):
        import WorkTrackApi.signals  # 👈 Načítanie signálov
        from WorkTrackApi.utils.attendance_utils import handle_night_shift
