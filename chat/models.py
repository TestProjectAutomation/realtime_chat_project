from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel


class ChatRoom(TimeStampedModel):
    """
    Represents a chat room with participants
    """
    ROOM_TYPES = (
        ('direct', _('Direct Message')),
        ('group', _('Group Chat')),
    )
    
    name = models.CharField(max_length=255, null=True, blank=True)
    room_type = models.CharField(max_length=10, choices=ROOM_TYPES, default='direct')
    participants = models.ManyToManyField(User, related_name='chat_rooms')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-modified']
        verbose_name = _('Chat Room')
        verbose_name_plural = _('Chat Rooms')
    
    def __str__(self):
        if self.name:
            return self.name
        return f"{self.room_type} chat - {self.id}"
    
    @property
    def last_message(self):
        return self.messages.order_by('-created').first()
    
    def get_other_participant(self, user):
        """
        For direct messages, get the other participant
        """
        if self.room_type == 'direct':
            return self.participants.exclude(id=user.id).first()
        return None

    def get_other_participant(self, user):
        """
        For direct messages, get the other participant
        """
        if self.room_type == 'direct':
            # هذه طريقة أكثر أماناً
            other_participants = self.participants.exclude(id=user.id)
            if other_participants.exists():
                return other_participants.first()
        return None


class Message(TimeStampedModel):
    """
    Represents a message in a chat room
    """
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['created']
        indexes = [
            models.Index(fields=['room', 'created']),
            models.Index(fields=['sender', 'created']),
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


class UserProfile(models.Model):
    """
    Extended user profile for chat features
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    language = models.CharField(max_length=10, choices=[('en', 'English'), ('ar', 'Arabic')], default='en')
    theme = models.CharField(max_length=10, choices=[('light', 'Light'), ('dark', 'Dark')], default='dark')
    
    def __str__(self):
        return f"{self.user.username} Profile"
    
    @property
    def is_online(self):
        return self.online