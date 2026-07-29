import os
import sys

# For 3ds Max 2027, we need to ensure that the PYTHONPATH is set
# correctly before importing any modules.
new_python_paths = []
for path in os.getenv("MAX_PYTHONPATH", "").split(os.pathsep):
    if not path:
        continue
    norm_path = os.path.normpath(path)
    if os.path.isdir(norm_path) and norm_path not in new_python_paths:
        new_python_paths.append(norm_path)

existing_pythonpath = [
    p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p
]
existing_pythonpath_norm = {os.path.normpath(p) for p in existing_pythonpath}

for path in new_python_paths:
    if path not in existing_pythonpath_norm:
        existing_pythonpath.insert(0, path)
        existing_pythonpath_norm.add(path)

    # 3ds Max 2027 may ignore PYTHONPATH on startup; update runtime import path.
    if path not in sys.path:
        sys.path.insert(0, path)

os.environ["PYTHONPATH"] = os.pathsep.join(existing_pythonpath)


from ayon_max.api import MaxHost  # noqa: E402
from ayon_core.pipeline import install_host  # noqa: E402

host = MaxHost()
install_host(host)
