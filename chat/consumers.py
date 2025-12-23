import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.utils import timezone
from .models import ChatRoom, Message, UserProfile


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        self.user = self.scope['user']
        
        if self.user.is_authenticated:
            # Join room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            await self.accept()
            
            # Update user online status
            await self.update_user_status(True)
            
            # Notify others in the room
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_status',
                    'user_id': self.user.id,
                    'username': self.user.username,
                    'online': True,
                }
            )
    
    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            
            # Update user online status
            await self.update_user_status(False)
            
            # Notify others in the room
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_status',
                    'user_id': self.user.id,
                    'username': self.user.username,
                    'online': False,
                }
            )
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'chat_message':
            content = data['message']
            
            # Save message to database
            message = await self.save_message(content)
            
            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message_id': message.id,
                    'sender_id': self.user.id,
                    'sender': self.user.username,
                    'content': content,
                    'timestamp': message.created.isoformat(),
                }
            )
        
        elif message_type == 'typing':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'typing_indicator',
                    'user_id': self.user.id,
                    'username': self.user.username,
                    'is_typing': data['is_typing'],
                }
            )
        
        elif message_type == 'read_receipt':
            message_id = data['message_id']
            await self.mark_message_as_read(message_id)
            
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'read_receipt',
                    'message_id': message_id,
                    'user_id': self.user.id,
                    'username': self.user.username,
                }
            )
    
    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message_id': event['message_id'],
            'sender': event['sender'],
            'sender_id': event['sender_id'],
            'content': event['content'],
            'timestamp': event['timestamp'],
        }))
    
    async def typing_indicator(self, event):
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'user_id': event['user_id'],
            'username': event['username'],
            'is_typing': event['is_typing'],
        }))
    
    async def user_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_status',
            'user_id': event['user_id'],
            'username': event['username'],
            'online': event['online'],
        }))
    
    async def read_receipt(self, event):
        await self.send(text_data=json.dumps({
            'type': 'read_receipt',
            'message_id': event['message_id'],
            'user_id': event['user_id'],
            'username': event['username'],
        }))
    
    @database_sync_to_async
    def save_message(self, content):
        room = ChatRoom.objects.get(id=self.room_id)
        message = Message.objects.create(
            room=room,
            sender=self.user,
            content=content
        )
        return message
    
    @database_sync_to_async
    def update_user_status(self, online):
        profile, created = UserProfile.objects.get_or_create(user=self.user)
        profile.online = online
        profile.last_seen = timezone.now()
        profile.save()
    
    @database_sync_to_async
    def mark_message_as_read(self, message_id):
        try:
            message = Message.objects.get(id=message_id)
            message.mark_as_read()
        except Message.DoesNotExist:
            pass


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        
        if self.user.is_authenticated:
            self.notification_group_name = f'user_{self.user.id}_notifications'
            
            await self.channel_layer.group_add(
                self.notification_group_name,
                self.channel_name
            )
            
            await self.accept()
    
    async def disconnect(self, close_code):
        if hasattr(self, 'notification_group_name'):
            await self.channel_layer.group_discard(
                self.notification_group_name,
                self.channel_name
            )
    
    async def send_notification(self, event):
        await self.send(text_data=json.dumps(event))