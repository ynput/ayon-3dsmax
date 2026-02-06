from ayon_max.api import MaxHost
from ayon_core.pipeline import install_host

print("Installing AYON Max Host (startup.py)")
host = MaxHost()
install_host(host)
