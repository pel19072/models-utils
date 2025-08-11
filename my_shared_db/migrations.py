import subprocess

def run_migration():
    """Run Alembic migrations from Python code"""
    subprocess.run(["alembic", "upgrade", "head"], check=True)