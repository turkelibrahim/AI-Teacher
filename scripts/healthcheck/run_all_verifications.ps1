python scripts\healthcheck\verify.py
python scripts\healthcheck\verify_frontend.py > evidence\phase_0_1\frontend_runtime_verification.txt
docker compose config > evidence\phase_0_1\docker_compose_config.txt

cmd /c "cd apps\web && npm.cmd run lint > ..\..\evidence\phase_0_1\frontend_lint.txt"
cmd /c "cd apps\web && npm.cmd run build > ..\..\evidence\phase_0_1\frontend_build.txt"
