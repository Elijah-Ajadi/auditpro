#!/bin/bash
# Install dependencies
python3.12 -m pip install -r requirements.txt

# Run migrations (Optional: Can be done manually for safety)
# python3.12 manage.py migrate --noinput

# Collect static files
python3.12 manage.py collectstatic --noinput
