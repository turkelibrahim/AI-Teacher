import urllib.request
import time
import subprocess

def test_frontend():
    print("Waiting for frontend to be ready...")
    time.sleep(10) # give next.js dev server time to start
    try:
        req = urllib.request.Request("http://localhost:3000/")
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
            if 'Canlı Öğretmen AI' in html:
                print("FRONTEND SERVER IS UP AND SERVING CORRECT HTML")
            else:
                print("FRONTEND RUNNING BUT UNEXPECTED CONTENT")
    except Exception as e:
        print(f"FRONTEND FAILED: {e}")

if __name__ == '__main__':
    test_frontend()
