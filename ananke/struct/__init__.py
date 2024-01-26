import logging
import os

logging.basicConfig(
    level=os.environ.get("ANANKE_LOG_LEVEL"),
    filename=os.environ.get("ANANKE_LOG_FILE"),
    filemode="a",
)
