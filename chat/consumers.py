# consumers.py - إضافة ميزات جديدة

import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.contrib.auth.models import User
from django.utils import timezone
from .models import ChatRoom, Message, UserProfile, MessageReaction
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class EnhancedChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        self.user = self.scope['user']
        self.user_id = str(self.user.id)
        
        if self.user.is_authenticated:
            # Add to room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            # Add to user's personal group for notifications
            self.user_group_name = f'user_{self.user_id}'
            await self.channel_layer.group_add(
                self.user_group_name,
                self.channel_name
            )
            
            await self.accept()
            
            # Update user status
            await self.update_user_status(True)
            
            # Send user joined notification
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_joined',
                    'user_id': self.user_id,
                    'username': self.user.username,
                    'timestamp': timezone.now().isoformat(),
                }
            )
            
            # Send online users list
            await self.send_online_users()
    
    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            # Remove from groups
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )
            
            # Update user status
            await self.update_user_status(False)
            
            # Send user left notification
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_left',
                    'user_id': self.user_id,
                    'username': self.user.username,
                    'timestamp': timezone.now().isoformat(),
                }
            )
    
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'chat_message':
                await self.handle_chat_message(data)
            
            elif message_type == 'typing':
                await self.handle_typing(data)
            
            elif message_type == 'read_receipt':
                await self.handle_read_receipt(data)
            
            elif message_type == 'reaction':
                await self.handle_reaction(data)
            
            elif message_type == 'delete_message':
                await self.handle_delete_message(data)
            
            elif message_type == 'pin_message':
                await self.handle_pin_message(data)
            
            elif message_type == 'edit_message':
                await self.handle_edit_message(data)
            
            elif message_type == 'forward_message':
                await self.handle_forward_message(data)
            
            elif message_type == 'call':
                await self.handle_call(data)
            
        except json.JSONDecodeError:
            logger.error('Invalid JSON received')
        except Exception as e:
            logger.error(f'Error processing message: {e}')
    
    async def handle_chat_message(self, data):
        content = data.get('message', '').strip()
        message_type = data.get('message_type', 'text')
        reply_to_id = data.get('reply_to')
        
        if not content and message_type == 'text':
            return
        
        # Save message to database
        message = await self.save_message(
            content=content,
            message_type=message_type,
            reply_to_id=reply_to_id
        )
        
        if message:
            # Send to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message_id': message.id,
                    'sender_id': self.user_id,
                    'sender': self.user.username,
                    'content': content,
                    'message_type': message_type,
                    'reply_to': reply_to_id,
                    'timestamp': message.created.isoformat(),
                }
            )
            
            # Send notification to other users
            await self.send_notifications(message)
    
    async def handle_typing(self, data):
        is_typing = data.get('is_typing', False)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'user_id': self.user_id,
                'username': self.user.username,
                'is_typing': is_typing,
            }
        )
    
    async def handle_read_receipt(self, data):
        message_id = data.get('message_id')
        
        await self.mark_message_as_read(message_id)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'read_receipt',
                'message_id': message_id,
                'user_id': self.user_id,
                'username': self.user.username,
                'timestamp': timezone.now().isoformat(),
            }
        )
    
    async def handle_reaction(self, data):
        message_id = data.get('message_id')
        reaction = data.get('reaction')
        
        reaction_obj = await self.add_reaction(message_id, reaction)
        
        if reaction_obj:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_reaction',
                    'message_id': message_id,
                    'user_id': self.user_id,
                    'username': self.user.username,
                    'reaction': reaction,
                    'timestamp': timezone.now().isoformat(),
                }
            )
    
    async def handle_delete_message(self, data):
        message_id = data.get('message_id')
        
        deleted = await self.delete_message(message_id)
        
        if deleted:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_deleted',
                    'message_id': message_id,
                    'user_id': self.user_id,
                    'username': self.user.username,
                    'timestamp': timezone.now().isoformat(),
                }
            )
    
    async def handle_pin_message(self, data):
        message_id = data.get('message_id')
        
        pinned = await self.pin_message(message_id)
        
        if pinned:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_pinned',
                    'message_id': message_id,
                    'user_id': self.user_id,
                    'username': self.user.username,
                    'timestamp': timezone.now().isoformat(),
                }
            )
    
    async def handle_edit_message(self, data):
        message_id = data.get('message_id')
        new_content = data.get('content')
        
        edited = await self.edit_message(message_id, new_content)
        
        if edited:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_edited',
                    'message_id': message_id,
                    'content': new_content,
                    'user_id': self.user_id,
                    'username': self.user.username,
                    'timestamp': timezone.now().isoformat(),
                }
            )
    
    async def handle_forward_message(self, data):
        message_id = data.get('message_id')
        target_rooms = data.get('rooms', [])
        
        forwarded = await self.forward_message(message_id, target_rooms)
        
        if forwarded:
            await self.channel_layer.group_send(
                self.user_group_name,
                {
                    'type': 'message_forwarded',
                    'message_id': message_id,
                    'rooms': target_rooms,
                    'timestamp': timezone.now().isoformat(),
                }
            )
    
    async def handle_call(self, data):
        call_type = data.get('call_type', 'voice')
        action = data.get('action')  # 'start', 'answer', 'end', 'reject'
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'call_event',
                'user_id': self.user_id,
                'username': self.user.username,
                'call_type': call_type,
                'action': action,
                'timestamp': timezone.now().isoformat(),
            }
        )
    
    # WebSocket event handlers
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message_id': event['message_id'],
            'sender': event['sender'],
            'sender_id': event['sender_id'],
            'content': event['content'],
            'message_type': event.get('message_type', 'text'),
            'reply_to': event.get('reply_to'),
            'timestamp': event['timestamp'],
        }))
    
    async def typing_indicator(self, event):
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'user_id': event['user_id'],
            'username': event['username'],
            'is_typing': event['is_typing'],
        }))
    
    async def user_joined(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_joined',
            'user_id': event['user_id'],
            'username': event['username'],
            'timestamp': event['timestamp'],
        }))
    
    async def user_left(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_left',
            'user_id': event['user_id'],
            'username': event['username'],
            'timestamp': event['timestamp'],
        }))
    
    async def read_receipt(self, event):
        await self.send(text_data=json.dumps({
            'type': 'read_receipt',
            'message_id': event['message_id'],
            'user_id': event['user_id'],
            'username': event['username'],
            'timestamp': event['timestamp'],
        }))
    
    async def message_reaction(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message_reaction',
            'message_id': event['message_id'],
            'user_id': event['user_id'],
            'username': event['username'],
            'reaction': event['reaction'],
            'timestamp': event['timestamp'],
        }))
    
    async def message_deleted(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message_deleted',
            'message_id': event['message_id'],
            'user_id': event['user_id'],
            'username': event['username'],
            'timestamp': event['timestamp'],
        }))
    
    async def message_pinned(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message_pinned',
            'message_id': event['message_id'],
            'user_id': event['user_id'],
            'username': event['username'],
            'timestamp': event['timestamp'],
        }))
    
    async def message_edited(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message_edited',
            'message_id': event['message_id'],
            'content': event['content'],
            'user_id': event['user_id'],
            'username': event['username'],
            'timestamp': event['timestamp'],
        }))
    
    async def call_event(self, event):
        await self.send(text_data=json.dumps({
            'type': 'call_event',
            'user_id': event['user_id'],
            'username': event['username'],
            'call_type': event['call_type'],
            'action': event['action'],
            'timestamp': event['timestamp'],
        }))
    
    async def online_users(self, event):
        await self.send(text_data=json.dumps({
            'type': 'online_users',
            'users': event['users'],
        }))
    
    # Database operations
    @database_sync_to_async
    def save_message(self, content, message_type='text', reply_to_id=None):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            
            message = Message.objects.create(
                room=room,
                sender=self.user,
                content=content,
                message_type=message_type
            )
            
            if reply_to_id:
                try:
                    replied_message = Message.objects.get(id=reply_to_id, room=room)
                    message.replied_to = replied_message
                    message.save()
                except Message.DoesNotExist:
                    pass
            
            return message
        except Exception as e:
            logger.error(f'Error saving message: {e}')
            return None
    
    @database_sync_to_async
    def update_user_status(self, online):
        try:
            profile, created = UserProfile.objects.get_or_create(user=self.user)
            profile.online = online
            profile.last_seen = timezone.now()
            
            if online:
                profile.last_online = timezone.now()
            
            profile.save()
            return True
        except Exception as e:
            logger.error(f'Error updating user status: {e}')
            return False
    
    @database_sync_to_async
    def mark_message_as_read(self, message_id):
        try:
            message = Message.objects.get(id=message_id, room__participants=self.user)
            message.mark_as_read()
            return True
        except Message.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f'Error marking message as read: {e}')
            return False
    
    @database_sync_to_async
    def add_reaction(self, message_id, reaction):
        try:
            message = Message.objects.get(id=message_id, room__participants=self.user)
            
            # Check if user already reacted
            existing = MessageReaction.objects.filter(
                message=message,
                user=self.user
            ).first()
            
            if existing:
                if existing.reaction == reaction:
                    # Remove reaction if same
                    existing.delete()
                    return None
                else:
                    # Update reaction
                    existing.reaction = reaction
                    existing.save()
                    return existing
            else:
                # Add new reaction
                return MessageReaction.objects.create(
                    message=message,
                    user=self.user,
                    reaction=reaction
                )
        except Exception as e:
            logger.error(f'Error adding reaction: {e}')
            return None
    
    @database_sync_to_async
    def delete_message(self, message_id):
        try:
            message = Message.objects.get(id=message_id, sender=self.user)
            message.soft_delete()
            return True
        except Message.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f'Error deleting message: {e}')
            return False
    
    @database_sync_to_async
    def pin_message(self, message_id):
        try:
            message = Message.objects.get(id=message_id, room__participants=self.user)
            
            # Check permissions (only group admins can pin in groups)
            if message.room.room_type == 'group' and message.room.admin != self.user:
                return False
            
            message.is_pinned = not message.is_pinned
            message.save()
            return True
        except Message.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f'Error pinning message: {e}')
            return False
    
    @database_sync_to_async
    def edit_message(self, message_id, new_content):
        try:
            message = Message.objects.get(id=message_id, sender=self.user)
            message.content = new_content
            message.save()
            return True
        except Message.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f'Error editing message: {e}')
            return False
    
    @database_sync_to_async
    def forward_message(self, message_id, target_rooms):
        try:
            original_message = Message.objects.get(id=message_id, sender=self.user)
            
            for room_id in target_rooms:
                try:
                    target_room = ChatRoom.objects.get(id=room_id, participants=self.user)
                    
                    # Create forwarded message
                    Message.objects.create(
                        room=target_room,
                        sender=self.user,
                        content=f"Forwarded: {original_message.content}",
                        message_type=original_message.message_type,
                        is_forwarded=True,
                        forwarded_from=original_message
                    )
                except ChatRoom.DoesNotExist:
                    continue
            
            return True
        except Exception as e:
            logger.error(f'Error forwarding message: {e}')
            return False
    
    @database_sync_to_async
    def get_online_users(self):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            online_users = UserProfile.objects.filter(
                user__in=room.participants.all(),
                online=True
            ).select_related('user')
            
            return [
                {
                    'id': str(profile.user.id),
                    'username': profile.user.username,
                    'full_name': profile.user.get_full_name(),
                    'avatar': profile.profile_picture.url if profile.profile_picture else None,
                }
                for profile in online_users
            ]
        except Exception as e:
            logger.error(f'Error getting online users: {e}')
            return []
    
    async def send_online_users(self):
        online_users = await self.get_online_users()
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'online_users',
                'users': online_users,
            }
        )
    
    async def send_notifications(self, message):
        # Send notifications to other users in the room
        room = await self.get_room()
        if not room:
            return
        
        participants = await self.get_participants()
        
        for participant in participants:
            if participant.id != self.user.id:
                # Send to user's personal notification channel
                await self.channel_layer.group_send(
                    f'user_{participant.id}',
                    {
                        'type': 'notification',
                        'room_id': self.room_id,
                        'room_name': room.name or f"Chat with {self.user.username}",
                        'sender': self.user.username,
                        'message_preview': message.content[:50],
                        'timestamp': timezone.now().isoformat(),
                    }
                )
    
    @database_sync_to_async
    def get_room(self):
        try:
            return ChatRoom.objects.get(id=self.room_id)
        except ChatRoom.DoesNotExist:
            return None
    
    @database_sync_to_async
    def get_participants(self):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            return list(room.participants.all())
        except ChatRoom.DoesNotExist:
            return []


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
            
            # Send pending notifications
            await self.send_pending_notifications()
    
    async def disconnect(self, close_code):
        if hasattr(self, 'notification_group_name'):
            await self.channel_layer.group_discard(
                self.notification_group_name,
                self.channel_name
            )
    
    async def notification(self, event):
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'room_id': event['room_id'],
            'room_name': event['room_name'],
            'sender': event['sender'],
            'message_preview': event['message_preview'],
            'timestamp': event['timestamp'],
        }))
    
    async def send_pending_notifications(self):
        pending = await self.get_pending_notifications()
        
        for notification in pending:
            await self.send(text_data=json.dumps({
                'type': 'notification',
                'room_id': notification['room_id'],
                'room_name': notification['room_name'],
                'sender': notification['sender'],
                'message_preview': notification['message_preview'],
                'timestamp': notification['timestamp'],
            }))
    
    @database_sync_to_async
    def get_pending_notifications(self):
        # Get unread messages from last 24 hours
        from datetime import timedelta
        
        cutoff = timezone.now() - timedelta(hours=24)
        
        unread_messages = Message.objects.filter(
            room__participants=self.user,
            is_read=False,
            created__gte=cutoff
        ).exclude(sender=self.user).select_related('room', 'sender')[:10]
        
        notifications = []
        for message in unread_messages:
            notifications.append({
                'room_id': message.room.id,
                'room_name': message.room.name or f"Chat with {message.sender.username}",
                'sender': message.sender.username,
                'message_preview': message.content[:50],
                'timestamp': message.created.isoformat(),
            })
        
        return notifications


class CallConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'call_{self.room_id}'
        self.user = self.scope['user']
        
        if self.user.is_authenticated:
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            await self.accept()
    
    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            
            # Notify others that user left the call
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'call_ended',
                    'user_id': str(self.user.id),
                    'username': self.user.username,
                }
            )
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')
        
        if action == 'offer':
            await self.handle_offer(data)
        elif action == 'answer':
            await self.handle_answer(data)
        elif action == 'ice_candidate':
            await self.handle_ice_candidate(data)
        elif action == 'join':
            await self.handle_join()
        elif action == 'leave':
            await self.handle_leave()
    
    async def handle_offer(self, data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'call_offer',
                'from': str(self.user.id),
                'offer': data['offer'],
                'username': self.user.username,
            }
        )
    
    async def handle_answer(self, data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'call_answer',
                'from': str(self.user.id),
                'answer': data['answer'],
            }
        )
    
    async def handle_ice_candidate(self, data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'ice_candidate',
                'from': str(self.user.id),
                'candidate': data['candidate'],
            }
        )
    
    async def handle_join(self):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_joined_call',
                'user_id': str(self.user.id),
                'username': self.user.username,
            }
        )
    
    async def handle_leave(self):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_left_call',
                'user_id': str(self.user.id),
                'username': self.user.username,
            }
        )
    
    async def call_offer(self, event):
        if str(self.user.id) != event['from']:
            await self.send(text_data=json.dumps({
                'type': 'offer',
                'offer': event['offer'],
                'from': event['from'],
                'username': event['username'],
            }))
    
    async def call_answer(self, event):
        if str(self.user.id) != event['from']:
            await self.send(text_data=json.dumps({
                'type': 'answer',
                'answer': event['answer'],
                'from': event['from'],
            }))
    
    async def ice_candidate(self, event):
        if str(self.user.id) != event['from']:
            await self.send(text_data=json.dumps({
                'type': 'ice_candidate',
                'candidate': event['candidate'],
                'from': event['from'],
            }))
    
    async def user_joined_call(self, event):
        if str(self.user.id) != event['user_id']:
            await self.send(text_data=json.dumps({
                'type': 'user_joined',
                'user_id': event['user_id'],
                'username': event['username'],
            }))
    
    async def user_left_call(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_left',
            'user_id': event['user_id'],
            'username': event['username'],
        }))
    
    async def call_ended(self, event):
        await self.send(text_data=json.dumps({
            'type': 'call_ended',
            'user_id': event['user_id'],
            'username': event['username'],
        }))