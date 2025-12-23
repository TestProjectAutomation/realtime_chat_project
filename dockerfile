FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    redis-tools \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Run migrations
RUN python manage.py migrate

# Create non-root user
RUN useradd -m -u 1000 django && chown -R django:django /app
USER django

# Run the application
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "chat_app.asgi:application"]