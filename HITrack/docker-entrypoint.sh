#!/bin/bash
set -e
cd /opt/src

if [ "$1" = 'service' ]; then
	python manage.py collectstatic --no-input
	python manage.py migrate
	python manage.py init
	gunicorn -b=0.0.0.0:80 -w="$WORKERS" HITrack.wsgi:application

elif [ "$1" = 'dev' ]; then
	python manage.py collectstatic --no-input
	python manage.py migrate
	python manage.py init
	python manage.py runserver 0.0.0.0:8000

elif [ "$1" = 'worker-light' ]; then
	: "${LIGHT_WORKERS:=4}"
	: "${LIGHT_MAX_TASKS_PER_CHILD:=100}"
	celery -A hitrack_celery worker \
		--queues=light \
		--concurrency="$LIGHT_WORKERS" \
		--max-tasks-per-child="$LIGHT_MAX_TASKS_PER_CHILD" \
		--loglevel=info \
		-n light@%h

elif [ "$1" = 'worker-scan' ]; then
	: "${SCAN_WORKERS:=2}"
	: "${SCAN_MAX_TASKS_PER_CHILD:=20}"
	celery -A hitrack_celery worker \
		--queues=scan \
		--concurrency="$SCAN_WORKERS" \
		--max-tasks-per-child="$SCAN_MAX_TASKS_PER_CHILD" \
		--loglevel=info \
		-n scan@%h

elif [ "$1" = 'worker-enrichment' ]; then
	: "${ENRICHMENT_WORKERS:=2}"
	: "${ENRICHMENT_MAX_TASKS_PER_CHILD:=25}"
	celery -A hitrack_celery worker \
		--queues=enrichment \
		--concurrency="$ENRICHMENT_WORKERS" \
		--max-tasks-per-child="$ENRICHMENT_MAX_TASKS_PER_CHILD" \
		--loglevel=info \
		-n enrichment@%h

elif [ "$1" = 'beat' ]; then
	celery -A hitrack_celery beat \
		--scheduler django_celery_beat.schedulers:DatabaseScheduler \
		--loglevel=info

fi
