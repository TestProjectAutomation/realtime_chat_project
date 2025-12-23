# urls.py - إضافة مسارات جديدة

from django.urls import path, include
from django.views.i18n import set_language
from . import views

app_name = 'chat'

urlpatterns = [
    # Main views
    path('', views.index, name='index'),
    path('room/<int:room_id>/', views.room_detail, name='room_detail'),
    path('start-chat/<int:user_id>/', views.start_chat, name='start_chat'),
    path('create-group/', views.create_group_chat, name='create_group_chat'),
    path('profile/', views.update_profile, name='update_profile'),
    path('notifications/', views.notifications, name='notifications'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    
    # Message actions
    path('message/<int:message_id>/send/', views.send_message, name='send_message'),
    path('message/<int:message_id>/react/', views.react_to_message, name='react_to_message'),
    path('message/<int:message_id>/delete/', views.delete_message, name='delete_message'),
    path('message/<int:message_id>/pin/', views.pin_message, name='pin_message'),
    # path('message/<int:message_id>/edit/', views.edit_message, name='edit_message'),
    # path('message/<int:message_id>/forward/', views.forward_message, name='forward_message'),
    
    # API endpoints
    path('api/unread-count/', views.get_unread_count, name='unread_count'),
    path('api/search/', views.search_messages, name='search_messages'),
    # path('api/search-users/', views.search_users, name='search_users'),
    # path('api/room/<int:room_id>/messages/', views.get_messages, name='get_messages'),
    
    # Group management
    path('group/<int:room_id>/invite/', views.invite_to_group, name='invite_to_group'),
    path('invitation/<str:token>/accept/', views.accept_invitation, name='accept_invitation'),
    # path('group/<int:room_id>/add-member/', views.add_group_member, name='add_group_member'),
    # path('group/<int:room_id>/remove-member/<int:user_id>/', views.remove_group_member, name='remove_group_member'),
    # path('group/<int:room_id>/settings/', views.group_settings, name='group_settings'),

    # File handling
    # path('upload-file/', views.upload_file, name='upload_file'),
    # path('send-voice/', views.send_voice_message, name='send_voice'),
    
    # Authentication
    path('login/', views.custom_login, name='login'),
    path('signup/', views.signup, name='signup'),
    # path('logout/', views.custom_logout, name='logout'),
    
    # Internationalization
    path('i18n/setlang/', set_language, name='set_language'),
    
    # WebSocket endpoints (for Django Channels)
    # path('ws/chat/<int:room_id>/', views.ChatRoomView.as_view(), name='chat_ws'),
    # path('ws/notifications/', views.NotificationView.as_view(), name='notifications_ws'),
    # path('ws/call/<int:room_id>/', views.CallView.as_view(), name='call_ws'),
]