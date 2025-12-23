# models.py - إضافة تحسينات

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel
from django.core.validators import FileExtensionValidator
import os


class ChatRoom(TimeStampedModel):
    ROOM_TYPES = (
        ('direct', _('Direct Message')),
        ('group', _('Group Chat')),
    )
    
    name = models.CharField(max_length=255, null=True, blank=True)
    room_type = models.CharField(max_length=10, choices=ROOM_TYPES, default='direct')
    participants = models.ManyToManyField(User, related_name='chat_rooms')
    is_active = models.BooleanField(default=True)
    admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_rooms')
    avatar = models.ImageField(upload_to='room_avatars/', null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    is_encrypted = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-modified']
        verbose_name = _('Chat Room')
        verbose_name_plural = _('Chat Rooms')
        indexes = [
            models.Index(fields=['room_type', 'modified']),
        ]
    
    def __str__(self):
        if self.name:
            return self.name
        return f"{self.room_type} chat - {self.id}"
    
    @property
    def last_message(self):
        return self.messages.filter(is_deleted=False).order_by('-created').first()
    
    def get_other_participant(self, user):
        if self.room_type == 'direct':
            other_participants = self.participants.exclude(id=user.id)
            if other_participants.exists():
                return other_participants.first()
        return None
    
    def get_unread_count(self, user):
        return self.messages.filter(
            is_read=False,
            is_deleted=False
        ).exclude(sender=user).count()
    
    def add_participant(self, user, added_by=None):
        if user not in self.participants.all():
            self.participants.add(user)
            # Create system message
            if added_by:
                Message.objects.create(
                    room=self,
                    sender=added_by,
                    content=f"{added_by.username} added {user.username}",
                    is_system=True
                )
            return True
        return False
    
    def remove_participant(self, user, removed_by=None):
        if user in self.participants.all():
            self.participants.remove(user)
            # Create system message
            if removed_by:
                Message.objects.create(
                    room=self,
                    sender=removed_by,
                    content=f"{removed_by.username} removed {user.username}",
                    is_system=True
                )
            return True
        return False


class Message(TimeStampedModel):
    MESSAGE_TYPES = (
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File'),
        ('voice', 'Voice'),
        ('system', 'System'),
    )
    
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField()
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text')
    file = models.FileField(upload_to='chat_files/%Y/%m/%d/', null=True, blank=True,
                           validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'gif', 'mp4', 
                                                              'pdf', 'doc', 'docx', 'mp3', 'wav'])])
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    is_system = models.BooleanField(default=False)
    replied_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name='replies')
    
    class Meta:
        ordering = ['created']
        indexes = [
            models.Index(fields=['room', 'created']),
            models.Index(fields=['sender', 'created']),
            models.Index(fields=['is_read']),
        ]
        verbose_name = _('Message')
        verbose_name_plural = _('Messages')
    
    def __str__(self):
        return f"{self.sender.username}: {self.content[:50]}"
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
    
    def soft_delete(self):
        self.is_deleted = True
        self.content = "[Deleted message]"
        self.file.delete(save=False)
        self.save()
    
    @property
    def file_name(self):
        if self.file:
            return os.path.basename(self.file.name)
        return None
    
    @property
    def file_size(self):
        if self.file and self.file.size:
            return self.file.size
        return 0
    
    @property
    def file_extension(self):
        if self.file:
            return os.path.splitext(self.file.name)[1].lower()
        return ''


class UserProfile(models.Model):
    THEME_CHOICES = [
        ('light', 'Light'),
        ('dark', 'Dark'),
        ('auto', 'Auto'),
    ]
    
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('ar', 'Arabic'),
        ('fr', 'French'),
        ('es', 'Spanish'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)
    profile_picture = models.ImageField(upload_to='profile_pics/%Y/%m/%d/', null=True, blank=True)
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='en')
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default='auto')
    status = models.CharField(max_length=100, blank=True, null=True)
    last_online = models.DateTimeField(null=True, blank=True)
    typing_in_room = models.ForeignKey(ChatRoom, on_delete=models.SET_NULL, null=True, blank=True)
    notifications_enabled = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.user.username} Profile"
    
    @property
    def is_online(self):
        if self.online:
            return True
        if self.last_seen:
            return (timezone.now() - self.last_seen).seconds < 300  # 5 minutes
        return False
    
    @property
    def online_status(self):
        if self.is_online:
            return 'online'
        elif self.last_seen:
            minutes_ago = (timezone.now() - self.last_seen).seconds // 60
            if minutes_ago < 60:
                return f'last seen {minutes_ago} minutes ago'
            else:
                hours_ago = minutes_ago // 60
                return f'last seen {hours_ago} hours ago'
        return 'offline'


class MessageReaction(models.Model):
    REACTION_CHOICES = [
        ('like', '👍'),
        ('love', '❤️'),
        ('haha', '😂'),
        ('wow', '😮'),
        ('sad', '😢'),
        ('angry', '😠'),
    ]
    
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='message_reactions')
    reaction = models.CharField(max_length=10, choices=REACTION_CHOICES)
    created = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['message', 'user']
        verbose_name = _('Message Reaction')
        verbose_name_plural = _('Message Reactions')
    
    def __str__(self):
        return f"{self.user.username} reacted with {self.reaction}"


class ChatRoomInvitation(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='invitations')
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invitations')
    invited_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_invitations')
    token = models.CharField(max_length=100, unique=True)
    is_accepted = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        verbose_name = _('Chat Room Invitation')
        verbose_name_plural = _('Chat Room Invitations')
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def accept(self):
        if not self.is_expired() and not self.is_accepted:
            self.room.participants.add(self.invited_user)
            self.is_accepted = True
            self.save()
            return True
        return False