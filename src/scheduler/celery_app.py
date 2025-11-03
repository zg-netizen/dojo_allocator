"""
Celery application configuration.
"""
from celery import Celery
from celery.schedules import crontab
from config.settings import get_settings

settings = get_settings()

# Create Celery app
app = Celery(
    'dojo_allocator',
    broker=f'redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0',
    backend=f'redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0',
    include=['src.scheduler.tasks']
)

# Celery configuration
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes max per task
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Schedule configuration
app.conf.beat_schedule = {
    'ingest-data-daily': {
        'task': 'src.scheduler.tasks.ingest_all_data',
        'schedule': crontab(hour=6, minute=0),  # 6 AM UTC daily
    },
    'score-signals-daily': {
        'task': 'src.scheduler.tasks.score_all_signals',
        'schedule': crontab(hour=7, minute=0),  # 7 AM UTC daily
    },
    'allocate-capital-daily': {
        'task': 'src.scheduler.tasks.allocate_and_execute',
        'schedule': crontab(hour=8, minute=0),  # 8 AM UTC daily
    },
    'check-positions-hourly': {
        'task': 'src.scheduler.tasks.check_position_expiry',
        'schedule': crontab(minute=0),  # Every hour
    },
           'tier-escalation-review': {
               'task': 'src.scheduler.tasks.execute_review_cycle',
               'schedule': crontab(hour=9, minute=0),  # 9 AM UTC daily
           },
           'parallel-scenarios': {
               'task': 'src.scheduler.tasks.execute_parallel_scenarios',
               'schedule': crontab(hour=8, minute=30),  # 8:30 AM UTC daily (after main allocation)
           },
    'end-of-day-reconciliation': {
        'task': 'src.scheduler.tasks.end_of_day_reconciliation',
        'schedule': crontab(hour=22, minute=0),  # 10 PM UTC daily
    },
    # Live scenario unrealized updater (every 5 minutes)
    'update-scenario-unrealized-5min': {
        'task': 'src.scheduler.tasks.update_scenario_unrealized',
        'schedule': crontab(minute='*/5'),
    },
}

if __name__ == '__main__':
    app.start()
