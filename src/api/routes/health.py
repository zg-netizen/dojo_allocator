"""
Health check endpoints.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.models.base import get_db
from datetime import datetime
import redis

router = APIRouter()

@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint.
    Verifies database connectivity.
    """
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "disconnected",
            "error": str(e)
        }

@router.get("/celery/status")
def celery_status():
    """
    Celery worker status endpoint.
    Checks Redis connectivity and worker count.
    """
    try:
        # Connect to Redis
        r = redis.Redis(host='redis', port=6379, decode_responses=True)
        
        # Check if Celery is active by looking for task metadata
        celery_keys = r.keys('celery-task-meta-*')
        worker_count = len(celery_keys) if celery_keys else 0
        
        # Also check for active workers in the celery set
        try:
            workers = r.smembers('celery')
            worker_count = max(worker_count, len(workers))
        except:
            pass
        
        return {
            "status": "healthy" if worker_count > 0 else "idle",
            "workers": worker_count,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "workers": 0,
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }
