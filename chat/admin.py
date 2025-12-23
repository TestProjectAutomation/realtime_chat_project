# admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import ChatRoom, Message, UserProfile, MessageReaction, ChatRoomInvitation


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'


class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active']
    list_filter = ['is_staff', 'is_active', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ['sender', 'content', 'created', 'is_read']
    readonly_fields = ['created']
    ordering = ['-created']


class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'room_type', 'is_active', 'created', 'modified']
    list_filter = ['room_type', 'is_active', 'created']
    search_fields = ['name', 'participants__username']
    filter_horizontal = ['participants']
    inlines = [MessageInline]
    readonly_fields = ['created', 'modified']
    
    def get_participants_count(self, obj):
        return obj.participants.count()
    get_participants_count.short_description = 'Participants'


class MessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'room', 'content_preview', 'created', 'is_read', 'is_deleted']
    list_filter = ['is_read', 'is_deleted', 'created', 'message_type']
    search_fields = ['content', 'sender__username', 'room__name']
    readonly_fields = ['created', 'modified']
    date_hierarchy = 'created'
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'


class MessageReactionAdmin(admin.ModelAdmin):
    list_display = ['message', 'user', 'reaction', 'created']
    list_filter = ['reaction', 'created']
    search_fields = ['message__content', 'user__username']
    readonly_fields = ['created']


class ChatRoomInvitationAdmin(admin.ModelAdmin):
    list_display = ['room', 'invited_by', 'invited_user', 'is_accepted', 'created', 'expires_at']
    list_filter = ['is_accepted', 'created']
    search_fields = ['room__name', 'invited_by__username', 'invited_user__username']
    readonly_fields = ['created', 'token']


# Unregister the default User admin and register with custom
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# Register other models
admin.site.register(ChatRoom, ChatRoomAdmin)
admin.site.register(Message, MessageAdmin)
admin.site.register(UserProfile)
admin.site.register(MessageReaction, MessageReactionAdmin)
admin.site.register(ChatRoomInvitation, ChatRoomInvitationAdmin)