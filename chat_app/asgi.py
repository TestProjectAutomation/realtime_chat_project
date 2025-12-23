import os
import django
from django.core.asgi import get_asgi_application

# Set Django settings module first
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chat_app.settings')

# Setup Django
django.setup()

# Now import channels and routing
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from chat.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                websocket_urlpatterns
            )
        )
    ),
})