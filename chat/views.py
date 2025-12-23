# views.py - إضافة وظائف جديدة

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponseForbidden
from django.utils.translation import gettext_lazy as _
from django.db.models import Q, Count, Max, F, Subquery, OuterRef
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST, require_GET
from django.core.exceptions import PermissionDenied
import json
from datetime import timedelta
from django.utils import timezone
from .models import ChatRoom, Message, UserProfile, MessageReaction, ChatRoomInvitation
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import UserCreationForm

@login_required
def index(request):
    """Main chat dashboard with enhanced features"""
    # Get or create user profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Update online status
    if not profile.online:
        profile.online = True
        profile.save()
    
    # Get chat rooms with optimized queries
    chat_rooms = ChatRoom.objects.filter(
        participants=request.user,
        is_active=True
    ).annotate(
        last_message_time=Max('messages__created', filter=Q(messages__is_deleted=False)),
        unread_count=Count('messages', 
                          filter=Q(messages__is_read=False) & 
                                 Q(messages__is_deleted=False) & 
                                 ~Q(messages__sender=request.user))
    ).prefetch_related(
        'participants',
        'participants__profile'
    ).order_by('-last_message_time')
    
    # Get other users with online status
    other_users = User.objects.exclude(id=request.user.id).annotate(
        has_chat=Count('chat_rooms', filter=Q(chat_rooms__participants=request.user) & Q(chat_rooms__room_type='direct'))
    ).prefetch_related('profile')
    
    # Get online contacts count
    online_count = UserProfile.objects.filter(
        online=True,
        user__in=other_users
    ).count()
    
    # Get recent chats (last 7 days)
    recent_chats = chat_rooms.filter(
        last_message_time__gte=timezone.now() - timedelta(days=7)
    )[:10]
    
    context = {
        'chat_rooms': chat_rooms,
        'recent_chats': recent_chats,
        'other_users': other_users,
        'profile': profile,
        'online_count': online_count,
        'total_chats': chat_rooms.count(),
    }
    
    return render(request, 'chat/index.html', context)


@login_required
def room_detail(request, room_id):
    """Enhanced chat room detail view"""
    room = get_object_or_404(ChatRoom, id=room_id, participants=request.user, is_active=True)
    
    # Get messages with optimizations
    messages = room.messages.filter(is_deleted=False).select_related(
        'sender',
        'sender__profile'
    ).prefetch_related(
        'reactions',
        'reactions__user'
    ).order_by('created')
    
    # Pagination
    paginator = Paginator(messages, 100)  # Increased to 100 messages per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Mark unread messages as read
    unread_messages = room.messages.filter(
        is_read=False,
        is_deleted=False
    ).exclude(sender=request.user)
    
    if unread_messages.exists():
        unread_messages.update(is_read=True, read_at=timezone.now())
    
    # Get other participant for direct chats
    other_participant = None
    if room.room_type == 'direct':
        other_participant = room.get_other_participant(request.user)
    
    # Get pinned messages
    pinned_messages = room.messages.filter(
        is_deleted=False,
        is_pinned=True
    ).order_by('-created')[:5]
    
    context = {
        'room': room,
        'page_obj': page_obj,
        'other_participant': other_participant,
        'pinned_messages': pinned_messages,
        'participants': room.participants.all().prefetch_related('profile'),
        'is_admin': room.admin == request.user,
    }
    
    return render(request, 'chat/room.html', context)


@login_required
def start_chat(request, user_id):
    """Start a new chat with enhanced functionality"""
    other_user = get_object_or_404(User, id=user_id)
    
    if other_user == request.user:
        messages.error(request, _("You cannot start a chat with yourself"))
        return redirect('chat:index')
    
    # Check if a direct chat already exists
    chat_room = ChatRoom.objects.filter(
        participants=request.user,
        room_type='direct'
    ).filter(participants=other_user).first()
    
    if not chat_room:
        # Create new chat room
        chat_room = ChatRoom.objects.create(room_type='direct')
        chat_room.participants.add(request.user, other_user)
        
        # Send welcome message
        welcome_message = _(f"Hello {other_user.username}! You are now connected with {request.user.username}.")
        Message.objects.create(
            room=chat_room,
            sender=request.user,
            content=welcome_message,
            is_system=True
        )
    
    return redirect('chat:room_detail', room_id=chat_room.id)


@login_required
def create_group_chat(request):
    """Enhanced group chat creation"""
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        participant_ids = request.POST.getlist('participants')
        avatar = request.FILES.get('avatar')
        
        # Validate name
        if not name or len(name.strip()) < 3:
            messages.error(request, _("Group name must be at least 3 characters"))
            return redirect('chat:create_group_chat')
        
        # Create group chat
        chat_room = ChatRoom.objects.create(
            name=name.strip(),
            room_type='group',
            description=description.strip(),
            admin=request.user,
            avatar=avatar
        )
        
        # Add participants
        participants = [request.user]
        if participant_ids:
            participants.extend(User.objects.filter(id__in=participant_ids))
        
        chat_room.participants.add(*participants)
        
        # Send system message
        system_message = _(f"Group '{name}' was created by {request.user.username}")
        Message.objects.create(
            room=chat_room,
            sender=request.user,
            content=system_message,
            is_system=True
        )
        
        messages.success(request, _("Group chat created successfully!"))
        return redirect('chat:room_detail', room_id=chat_room.id)
    
    users = User.objects.exclude(id=request.user.id).select_related('profile')
    return render(request, 'chat/create_group.html', {'users': users})


@login_required
@require_POST
def send_message(request, room_id):
    """Send message with attachments"""
    room = get_object_or_404(ChatRoom, id=room_id, participants=request.user, is_active=True)
    
    content = request.POST.get('message', '').strip()
    file = request.FILES.get('file')
    message_type = request.POST.get('message_type', 'text')
    reply_to_id = request.POST.get('reply_to')
    
    if not content and not file:
        return JsonResponse({'error': _('Message cannot be empty')}, status=400)
    
    # Validate file
    if file and file.size > 10 * 1024 * 1024:  # 10MB limit
        return JsonResponse({'error': _('File size exceeds 10MB limit')}, status=400)
    
    # Create message
    message = Message.objects.create(
        room=room,
        sender=request.user,
        content=content if content else '[File]',
        message_type=message_type,
        file=file
    )
    
    # Handle reply
    if reply_to_id:
        try:
            replied_message = Message.objects.get(id=reply_to_id, room=room)
            message.replied_to = replied_message
            message.save()
        except Message.DoesNotExist:
            pass
    
    # Prepare response
    response_data = {
        'id': message.id,
        'content': message.content,
        'sender': request.user.username,
        'sender_id': request.user.id,
        'timestamp': message.created.isoformat(),
        'message_type': message.message_type,
        'file_url': message.file.url if message.file else None,
        'file_name': message.file_name,
    }
    
    return JsonResponse(response_data)


@login_required
@require_POST
def react_to_message(request, message_id):
    """Add reaction to message"""
    message = get_object_or_404(Message, id=message_id, room__participants=request.user)
    reaction_type = request.POST.get('reaction')
    
    if reaction_type not in dict(MessageReaction.REACTION_CHOICES):
        return JsonResponse({'error': _('Invalid reaction')}, status=400)
    
    # Update or create reaction
    reaction, created = MessageReaction.objects.update_or_create(
        message=message,
        user=request.user,
        defaults={'reaction': reaction_type}
    )
    
    return JsonResponse({
        'success': True,
        'reaction': reaction.reaction,
        'created': created,
        'reaction_count': message.reactions.count(),
    })


@login_required
@require_GET
def search_messages(request, room_id):
    """Search messages in a room"""
    room = get_object_or_404(ChatRoom, id=room_id, participants=request.user)
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    messages = room.messages.filter(
        Q(content__icontains=query) | 
        Q(sender__username__icontains=query)
    ).filter(is_deleted=False).select_related('sender').order_by('-created')[:50]
    
    results = [{
        'id': msg.id,
        'content': msg.content,
        'sender': msg.sender.username,
        'timestamp': msg.created.isoformat(),
        'is_system': msg.is_system,
    } for msg in messages]
    
    return JsonResponse({'results': results})


@login_required
@require_POST
def delete_message(request, message_id):
    """Delete a message (soft delete)"""
    message = get_object_or_404(Message, id=message_id)
    
    # Check permissions
    if message.sender != request.user and not message.room.admin == request.user:
        return JsonResponse({'error': _('You are not allowed to delete this message')}, status=403)
    
    message.soft_delete()
    return JsonResponse({'success': True})


@login_required
@require_POST
def pin_message(request, message_id):
    """Pin/Unpin a message"""
    message = get_object_or_404(Message, id=message_id, room__participants=request.user)
    
    # Check if user is admin (for group chats)
    if message.room.room_type == 'group' and message.room.admin != request.user:
        return JsonResponse({'error': _('Only group admin can pin messages')}, status=403)
    
    message.is_pinned = not message.is_pinned
    message.save()
    
    return JsonResponse({
        'success': True,
        'is_pinned': message.is_pinned,
    })


@login_required
@require_POST
def invite_to_group(request, room_id):
    """Invite user to group"""
    room = get_object_or_404(ChatRoom, id=room_id, room_type='group')
    
    # Check if user is admin
    if room.admin != request.user:
        return JsonResponse({'error': _('Only group admin can invite users')}, status=403)
    
    user_id = request.POST.get('user_id')
    invited_user = get_object_or_404(User, id=user_id)
    
    # Check if user is already a member
    if room.participants.filter(id=user_id).exists():
        return JsonResponse({'error': _('User is already a member')}, status=400)
    
    # Create invitation
    import secrets
    import uuid
    
    invitation = ChatRoomInvitation.objects.create(
        room=room,
        invited_by=request.user,
        invited_user=invited_user,
        token=str(uuid.uuid4()),
        expires_at=timezone.now() + timedelta(days=7)
    )
    
    # In real app, send email notification here
    
    return JsonResponse({
        'success': True,
        'invitation_id': invitation.id,
        'token': invitation.token,
    })


@login_required
def accept_invitation(request, token):
    """Accept group invitation"""
    invitation = get_object_or_404(ChatRoomInvitation, token=token, invited_user=request.user)
    
    if invitation.is_expired():
        messages.error(request, _('Invitation has expired'))
        return redirect('chat:index')
    
    if invitation.accept():
        messages.success(request, _(f'You have joined {invitation.room.name}'))
        return redirect('chat:room_detail', room_id=invitation.room.id)
    else:
        messages.error(request, _('Failed to accept invitation'))
        return redirect('chat:index')


@login_required
def get_unread_count(request):
    """Enhanced unread count API"""
    total_unread = request.user.messages_received.filter(is_read=False).count()
    count = Message.objects.filter(
        room__participants=request.user,
        is_read=False,
        is_deleted=False
    ).exclude(sender=request.user).count()
    
    # Also count unread mentions
    mention_count = Message.objects.filter(
        room__participants=request.user,
        content__icontains=f"@{request.user.username}",
        is_read=False,
        is_deleted=False
    ).exclude(sender=request.user).count()
    
    return JsonResponse({
        'unread_count': count,
        'total_unread': total_unread,
        'mention_count': mention_count,
        'total': count + mention_count
    })


@login_required
def update_profile(request):
    """Enhanced profile update"""
    profile = request.user.profile
    
    if request.method == 'POST':
        # Handle JSON requests (for theme updates)
        if request.headers.get('Content-Type') == 'application/json':
            try:
                data = json.loads(request.body)
                if 'theme' in data:
                    profile.theme = data['theme']
                    profile.save()
                    
                    # Update session theme
                    request.session['theme'] = data['theme']
                    
                    return JsonResponse({'success': True, 'theme': profile.theme})
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        # Handle form submissions
        profile.language = request.POST.get('language', profile.language)
        profile.theme = request.POST.get('theme', profile.theme)
        profile.status = request.POST.get('status', profile.status)
        
        if 'profile_picture' in request.FILES:
            # Delete old profile picture if exists
            if profile.profile_picture:
                profile.profile_picture.delete(save=False)
            profile.profile_picture = request.FILES['profile_picture']
        
        profile.save()
        
        # Update language in session
        if profile.language:
            request.session['django_language'] = profile.language
        
        messages.success(request, _('Profile updated successfully!'))
        return redirect('chat:index')
    
    return render(request, 'chat/profile.html', {'profile': profile})


@login_required
def notifications(request):
    """User notifications page"""
    # Get recent notifications (mentions, reactions, etc.)
    mentions = Message.objects.filter(
        room__participants=request.user,
        content__icontains=f"@{request.user.username}",
        is_deleted=False
    ).exclude(sender=request.user).order_by('-created')[:20]
    
    # Get reactions to user's messages
    user_messages = Message.objects.filter(sender=request.user, is_deleted=False)
    reactions = MessageReaction.objects.filter(
        message__in=user_messages
    ).exclude(user=request.user).select_related('user', 'message').order_by('-created')[:20]
    
    # Get group invitations
    invitations = ChatRoomInvitation.objects.filter(
        invited_user=request.user,
        is_accepted=False,
        expires_at__gt=timezone.now()
    ).select_related('room', 'invited_by')[:10]
    
    context = {
        'mentions': mentions,
        'reactions': reactions,
        'invitations': invitations,
        'unread_notifications': mentions.filter(is_read=False).count(),
    }
    
    return render(request, 'chat/notifications.html', context)


@login_required
def mark_all_read(request):
    """Mark all notifications as read"""
    Message.objects.filter(
        room__participants=request.user,
        is_read=False
    ).exclude(sender=request.user).update(is_read=True, read_at=timezone.now())
    
    return JsonResponse({'success': True})




# New authentication views




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
