#!/usr/bin/env python
import os
import sys
import django
from django.core.management import execute_from_command_line

if __name__ == "__main__":
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chat_app.settings')
    django.setup()
    
    print("Setting up Real-Time Chat Application...")
    
    # Run migrations
    print("\n1. Running migrations...")
    execute_from_command_line(['manage.py', 'makemigrations'])
    execute_from_command_line(['manage.py', 'migrate'])
    
    # Collect static files
    print("\n2. Collecting static files...")
    execute_from_command_line(['manage.py', 'collectstatic', '--noinput'])
    
    # Create superuser
    print("\n3. Creating superuser...")
    from django.contrib.auth.models import User
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
        print("Superuser created: admin/admin123")
    
    # Compile translations
    print("\n4. Compiling translations...")
    execute_from_command_line(['manage.py', 'compilemessages'])
    
    print("\n✅ Setup complete!")
    print("\nTo run the application:")
    print("1. Start Redis: redis-server")
    print("2. Start Django: python manage.py runserver")
    print("3. Start Daphne: daphne chat_app.asgi:application")
    print("\nOr use: python manage.py runserver with Channels")