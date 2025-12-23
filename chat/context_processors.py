from django.conf import settings


def language_rtl(request):
    """
    Add RTL language information to template context
    """
    rtl_languages = ['ar', 'he', 'fa', 'ur']
    current_language = request.LANGUAGE_CODE
    
    return {
        'is_rtl': current_language in rtl_languages,
        'current_language': current_language,
        'languages': settings.LANGUAGES,
    }