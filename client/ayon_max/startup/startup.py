import logging

from ayon_max.api import MaxHost
from ayon_core.pipeline import install_host

log = logging.getLogger(__name__)

log.info("Installing AYON Max Host (startup.py)")
host = MaxHost()
install_host(host)
