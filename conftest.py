"""Root test configuration ensuring backend and app packages are in sys.path."""

import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent
backend_dir = repo_root / "backend"
app_dir = backend_dir / "app"

for path_entry in [str(repo_root), str(backend_dir), str(app_dir)]:
    if path_entry not in sys.path:
        sys.path.insert(0, path_entry)
