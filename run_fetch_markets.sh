#!/bin/bash

# Activate the virtual environment
source myenv/bin/activate

# Navigate to the Django project directory (current directory)
cd "$(dirname "$0")"

# Run the Django management command
python manage.py fetch_markets