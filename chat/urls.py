from django.urls import path
from django.views.i18n import set_language
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.index, name='index'),
    path('room/<int:room_id>/', views.room_detail, name='room_detail'),
    path('start-chat/<int:user_id>/', views.start_chat, name='start_chat'),
    path('create-group/', views.create_group_chat, name='create_group_chat'),
    path('profile/', views.update_profile, name='update_profile'),
    path('unread-count/', views.get_unread_count, name='unread_count'),
    path('i18n/setlang/', set_language, name='set_language'),
    path('login/', views.custom_login, name='login'),
    path('signup/', views.signup, name='signup'),

]