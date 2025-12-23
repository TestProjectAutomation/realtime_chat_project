# routing.py في مجلد chat

from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/chat/<int:room_id>/', consumers.EnhancedChatConsumer.as_asgi()),
    path('ws/notifications/', consumers.NotificationConsumer.as_asgi()),
    path('ws/call/<int:room_id>/', consumers.CallConsumer.as_asgi()),
]