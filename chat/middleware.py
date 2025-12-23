# middleware.py

from django.utils import timezone
from .models import UserProfile
import threading

_local = threading.local()

class OnlineStatusMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            # Update online status
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            profile.online = True
            profile.last_seen = timezone.now()
            profile.save()
            
            # Store profile in request for easy access
            request.profile = profile
        
        response = self.get_response(request)
        
        # Clean up
        if hasattr(request, 'profile'):
            del request.profile
        
        return response
    
    def process_exception(self, request, exception):
        if hasattr(request, 'profile'):
            # Mark user as offline if there's an error
            try:
                request.profile.online = False
                request.profile.save()
            except:
                pass


class ThemeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            # Get user's theme preference
            try:
                profile = UserProfile.objects.get(user=request.user)
                request.theme = profile.theme
            except UserProfile.DoesNotExist:
                request.theme = 'auto'
        else:
            # Default theme for anonymous users
            request.theme = request.session.get('theme', 'auto')
        
        response = self.get_response(request)
        
        # Add theme to context
        if hasattr(response, 'context_data'):
            response.context_data['theme'] = getattr(request, 'theme', 'auto')
        
        return response