#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
python manage.py makemigrations core
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
