import sys
from pathlib import Path

# Ensure backend and app directories are in sys.path so 'app', 'config', 'providers', etc. are resolvable
backend_dir = Path(__file__).resolve().parent
app_dir = backend_dir / "app"

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

