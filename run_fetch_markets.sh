#!/bin/bash

# Navigate to the Django project directory (current directory)
cd "$(dirname "$0")"

# Run the Django management command to fetch markets
python manage.py fetch_markets

# Run the Django management command to update value area
python manage.py update_value_area