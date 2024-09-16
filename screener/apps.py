from django.apps import AppConfig
from django.core.management import call_command

class ScreenerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'screener'

    def ready(self):
        # Run the commands once when the server starts
        call_command('fetch_markets')