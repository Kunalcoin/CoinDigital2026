#!/bin/sh
python manage.py migrate --no-input
python manage.py collectstatic --no-input
# Copy static files to the shared volume that nginx can access
cp -r /app/staticfiles/* /static/ 2>/dev/null || true
gunicorn RoyaltyWebsite.wsgi:application --bind 0.0.0.0:8000 --timeout 1000
