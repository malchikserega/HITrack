#!/bin/bash
set -e
cd /opt/src

if [ "$1" = 'service' ]; then
	python manage.py collectstatic --no-input
	python manage.py migrate
	python manage.py init
	gunicorn -b=0.0.0.0:80 -w="$WORKERS" config.wsgi

elif [ "$1" = 'dev' ]; then
	python manage.py collectstatic --no-input
	python manage.py migrate
	python manage.py init
	python manage.py runserver 0.0.0.0:8000


elif [ "$1" = 'worker' ]; then
	celery -A hitrack_celery worker \
		--concurrency="$WORKERS" \
		--beat \
		--scheduler django \
		--loglevel=info \
		-n worker

fi