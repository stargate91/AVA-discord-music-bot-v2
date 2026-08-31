import logging
from logging.handlers import RotatingFileHandler
import sys
import os
from colorama import init, Fore, Style

init(autoreset=True)

class ColoredFormatter(logging.Formatter):
    def format(self, record):
        level_colors = {
            logging.DEBUG: Fore.CYAN,
            logging.INFO: Fore.GREEN,
            logging.WARNING: Fore.YELLOW,
            logging.ERROR: Fore.RED,
            logging.CRITICAL: Fore.RED + Style.BRIGHT,
        }
        color = level_colors.get(record.levelno, Fore.WHITE)
        record.levelname = f"{color}{record.levelname}{Style.RESET_ALL}"
        record.msg = f"{Style.BRIGHT}{record.msg}{Style.RESET_ALL}" if record.levelno >= logging.WARNING else record.msg
        return super().format(record)

log = logging.getLogger("RadioBot")
_console_handler_added = False

def setup_logging(
    level_name: str = "INFO", 
    instance_name: str = "", 
    max_bytes: int = 10 * 1024 * 1024, 
    backup_count: int = 5
):
    global _console_handler_added
    level = getattr(logging, level_name.upper(), logging.INFO)
    log.setLevel(level)

    os.makedirs("data", exist_ok=True)
    inst = instance_name or os.getenv("INSTANCE_NAME", "")
    target_log_file = f"data/{inst}_radio.log" if inst else "data/radio.log"

    # Remove existing FileHandlers
    for h in list(log.handlers):
        if isinstance(h, (logging.FileHandler, RotatingFileHandler)):
            log.removeHandler(h)
            h.close()

    # Add specific RotatingFileHandler
    if not os.getenv("MANAGED_LOGGING"):
        file_handler = RotatingFileHandler(
            target_log_file, 
            maxBytes=max_bytes, 
            backupCount=backup_count, 
            encoding="utf-8"
        )
        file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        log.addHandler(file_handler)

    # Add Console Handler once
    if not _console_handler_added:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(ColoredFormatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
        log.addHandler(console_handler)
        _console_handler_added = True
