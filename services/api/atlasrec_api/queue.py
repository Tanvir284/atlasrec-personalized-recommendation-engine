"""Lightweight queue publisher; importing this module never loads ML training."""
from celery import Celery

from .settings import settings

celery = Celery("atlasrec", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.update(worker_concurrency=settings.worker_concurrency, task_acks_late=True,
                   task_reject_on_worker_lost=True, worker_prefetch_multiplier=1,
                   task_track_started=True, task_soft_time_limit=settings.train_time_budget+90,
                   task_time_limit=settings.train_time_budget+120,
                   broker_connection_retry=False, broker_connection_max_retries=0,
                   broker_connection_retry_on_startup=True, broker_connection_timeout=1,
                   task_publish_retry=False,
                   broker_transport_options={"socket_connect_timeout": 1, "socket_timeout": 1, "max_retries": 0})

