cd /src
q
exit
celery -A backend.app.core.celery_app inspect registered
exit
