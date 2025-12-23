from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _
from django.db.models import Q, Count, Max
from django.core.paginator import Paginator
from .models import ChatRoom, Message, UserProfile

from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm


@login_required
def index(request):
    """
    Main chat dashboard
    """
    # Get or create user profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Get all chat rooms for the user
    chat_rooms = ChatRoom.objects.filter(
        participants=request.user,
        is_active=True
    ).annotate(
        last_message_time=Max('messages__created'),
        unread_count=Count('messages', filter=Q(messages__is_read=False) & ~Q(messages__sender=request.user))
    ).order_by('-last_message_time')
    
    # Get other users for starting new chats
    other_users = User.objects.exclude(id=request.user.id).annotate(
        has_chat=Count('chat_rooms', filter=Q(chat_rooms__participants=request.user) & Q(chat_rooms__room_type='direct'))
    )
    
    context = {
        'chat_rooms': chat_rooms,
        'other_users': other_users,
        'profile': profile,
    }
    
    return render(request, 'chat/index.html', context)


@login_required
def room_detail(request, room_id):
    """
    Chat room detail view
    """
    room = get_object_or_404(ChatRoom, id=room_id, participants=request.user, is_active=True)
    
    # Get messages with pagination
    messages = room.messages.all().order_by('created')
    paginator = Paginator(messages, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Mark unread messages as read
    room.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
    
    context = {
        'room': room,
        'page_obj': page_obj,
        'other_participant': room.get_other_participant(request.user),
    }
    
    return render(request, 'chat/room.html', context)


@login_required
def start_chat(request, user_id):
    """
    Start a new chat with a user
    """
    other_user = get_object_or_404(User, id=user_id)
    
    # Check if a direct chat already exists
    chat_room = ChatRoom.objects.filter(
        participants=request.user,
        room_type='direct'
    ).filter(participants=other_user).first()
    
    if not chat_room:
        # Create new chat room
        chat_room = ChatRoom.objects.create(room_type='direct')
        chat_room.participants.add(request.user, other_user)
    
    return redirect('chat:room_detail', room_id=chat_room.id)


@login_required
def create_group_chat(request):
    """
    Create a new group chat
    """
    if request.method == 'POST':
        name = request.POST.get('name')
        participant_ids = request.POST.getlist('participants')
        
        chat_room = ChatRoom.objects.create(
            name=name,
            room_type='group'
        )
        chat_room.participants.add(request.user, *participant_ids)
        
        return redirect('chat:room_detail', room_id=chat_room.id)
    
    users = User.objects.exclude(id=request.user.id)
    return render(request, 'chat/create_group.html', {'users': users})


@login_required
def get_unread_count(request):
    """
    API endpoint to get unread message count
    """
    count = Message.objects.filter(
        room__participants=request.user,
        is_read=False
    ).exclude(sender=request.user).count()
    
    return JsonResponse({'unread_count': count})


@login_required
def update_profile(request):
    """
    Update user profile (theme, language, etc.)
    """
    if request.method == 'POST':
        profile = request.user.profile
        profile.language = request.POST.get('language', 'en')
        profile.theme = request.POST.get('theme', 'dark')
        
        if 'profile_picture' in request.FILES:
            profile.profile_picture = request.FILES['profile_picture']
        
        profile.save()
        
        # Set language in session
        request.session['django_language'] = profile.language
        
        return redirect('chat:index')
    
    return render(request, 'chat/profile.html')




def custom_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember = request.POST.get('remember')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            
            if not remember:
                request.session.set_expiry(0)
            
            next_url = request.GET.get('next', 'chat:index')
            return redirect(next_url)
        else:
            # Add error message
            messages.error(request, _('Invalid username or password'))
    
    return render(request, 'auth/login.html')

def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Create user profile
            from chat.models import UserProfile
            UserProfile.objects.create(
                user=user,
                language=request.POST.get('language', 'en'),
                theme='dark'
            )
            
            # Auto login
            login(request, user)
            return redirect('chat:index')
    else:
        form = UserCreationForm()
    
    return render(request, 'auth/signup.html', {'form': form})
