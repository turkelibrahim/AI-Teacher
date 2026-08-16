import asyncio
import subprocess
import os

env = os.environ.copy()
env['POSTGRES_DB'] = 'phase4_migration_test'
env['POSTGRES_PASSWORD'] = 'password123'

# Run upgrade head
result = subprocess.run(
    ['alembic', 'upgrade', 'head'],
    capture_output=True, text=True, env=env
)
print('STDOUT:', result.stdout)
print('STDERR:', result.stderr)
print('Return code:', result.returncode)
