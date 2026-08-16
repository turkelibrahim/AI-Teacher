$env:DOCKER_HOST="npipe:////./pipe/docker_engine"
docker compose logs api --tail 50 > C:\Projects\ai-teacher\evidence\phase_4\api_logs_before_rotation.txt
"C:\Users\ibrah\.gemini\antigravity-ide\brain\f4dfc8ba-3008-45c5-b5e0-f9aeaca4ce2c\scratch\rotate_pass.ps1" | Invoke-Expression
docker compose up -d --build
