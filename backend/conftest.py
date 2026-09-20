import sys
from pathlib import Path

# Ensure backend directory is in sys.path so 'app' package is always resolvable
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
