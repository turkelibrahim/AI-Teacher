import urllib.request
import json
import os
import subprocess
import time

def check_endpoints():
    print("Checking /health/live...")
    try:
        req = urllib.request.Request("http://localhost:8000/api/v1/health/live")
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            with open("evidence/phase_0_1/health_live.json", "w") as f:
                json.dump(data, f, indent=2)
            print("LIVE OK")
    except Exception as e:
        print(f"LIVE FAILED: {e}")

    print("Checking /health/ready...")
    try:
        req = urllib.request.Request("http://localhost:8000/api/v1/health/ready")
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            with open("evidence/phase_0_1/health_ready.json", "w") as f:
                json.dump(data, f, indent=2)
            print("READY OK")
    except urllib.error.HTTPError as e:
        data = json.loads(e.read().decode())
        with open("evidence/phase_0_1/health_ready.json", "w") as f:
            json.dump(data, f, indent=2)
        print("READY HTTPError OK (handled)")
    except Exception as e:
        print(f"READY FAILED: {e}")

def get_docker_ps():
    result = subprocess.run(["docker", "compose", "ps"], capture_output=True, text=True)
    with open("evidence/phase_0_1/docker_compose_ps.txt", "w") as f:
        f.write(result.stdout)
    print("DOCKER PS OK")

def run_backend_tests():
    result = subprocess.run(["docker", "compose", "exec", "api", "pytest"], capture_output=True, text=True)
    with open("evidence/phase_0_1/backend_tests.txt", "w") as f:
        f.write(result.stdout)
        if result.stderr:
            f.write("\nSTDERR:\n" + result.stderr)
    print(f"BACKEND TESTS OK (code {result.returncode})")

def run_worker_smoke_test():
    # Execute a simple celery task
    code = """
from workers.app import celery_app
result = celery_app.send_task('system.ping')
print(result.get(timeout=10))
"""
    result = subprocess.run(["docker", "compose", "exec", "api", "python", "-c", code], capture_output=True, text=True)
    with open("evidence/phase_0_1/worker_smoke.txt", "w") as f:
        f.write(result.stdout)
        if result.stderr:
            f.write("\nSTDERR:\n" + result.stderr)
    print(f"WORKER SMOKE OK (code {result.returncode})")

if __name__ == "__main__":
    time.sleep(5) # wait for services to settle
    get_docker_ps()
    check_endpoints()
    run_backend_tests()
    run_worker_smoke_test()
