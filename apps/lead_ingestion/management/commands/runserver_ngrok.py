import os
from django.core.management.commands.runserver import Command as RunserverCommand
from django.conf import settings
from pyngrok import ngrok, conf

class Command(RunserverCommand):
    help = "Starts the Django development server and automatically establishes an ngrok tunnel."

    def handle(self, *args, **options):
        # Prevent starting ngrok twice (Django runserver runs twice due to the auto-reloader)
        if not os.environ.get('RUN_MAIN'):
            # Fetch auth token from settings or environment
            auth_token = getattr(settings, 'NGROK_AUTHTOKEN', os.environ.get('NGROK_AUTHTOKEN'))
            if auth_token:
                conf.get_default().auth_token = auth_token
            
            # Determine port
            port = options.get('port')
            if not port:
                # Parse port from addrport argument
                addrport = options.get('addrport')
                if addrport and ':' in addrport:
                    port = addrport.split(':')[-1]
                elif addrport and addrport.isdigit():
                    port = addrport
                else:
                    port = '8000'
            
            try:
                # Start ngrok tunnel
                tunnel = ngrok.connect(port)
                public_url = tunnel.public_url
                self.stdout.write(self.style.SUCCESS(f"\n================================================================="))
                self.stdout.write(self.style.SUCCESS(f"🚀 Ngrok tunnel successfully established!"))
                self.stdout.write(self.style.SUCCESS(f"🔗 Public URL: {public_url}"))
                self.stdout.write(self.style.SUCCESS(f"🎯 Webhook URL: {public_url}/api/v1/leads/webhook/<source>/"))
                self.stdout.write(self.style.SUCCESS(f"=================================================================\n"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"\n⚠️  Could not start ngrok tunnel: {str(e)}"))
                self.stdout.write(self.style.WARNING(f"👉 Make sure you configure NGROK_AUTHTOKEN in settings.py or run 'ngrok config add-authtoken <token>'.\n"))

        super().handle(*args, **options)
