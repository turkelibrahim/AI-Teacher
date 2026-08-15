from workers.app import celery_app
import time

@celery_app.task(name="system.ping")
def ping(message: str = "pong"):
    time.sleep(1) # simulate work
    return {"status": "ok", "message": message}
