import asyncio
import os
import sys
import re
import argparse
from utils.config import load_config
from utils.logger import log, setup_logging
from bot import RadioBot

def parse_arguments():
    parser = argparse.ArgumentParser(description="Discord Radio Bot Instance")
    parser.add_argument("instance", nargs="?", default="", help="Name of this bot instance (e.g. 1, 2, bot1)")
    parser.add_argument("--config", help="Specific config file path")
    return parser.parse_args()

async def main():
    args = parse_arguments()
    
    instance_name = args.instance
    if not instance_name and args.config:
        m = re.search(r"config([a-zA-Z0-9_-]+)\.json", args.config)
        if m:
            instance_name = m.group(1)
    
    if instance_name:
        os.environ["INSTANCE_NAME"] = instance_name

    config_file = args.config if args.config else (f"config{instance_name}.json" if instance_name else "config.json")
    
    try:
        config = load_config(config_file, instance_name=instance_name)
        setup_logging(config.log_level, instance_name=instance_name)
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_file}' not found.")
        sys.exit(1)

    bot = RadioBot(config, instance_name=instance_name)
    
    try:
        async with bot:
            await bot.start(config.token)
    except (asyncio.CancelledError, KeyboardInterrupt):
        log.info("Shutdown initiated...")
    finally:
        if not bot.is_closed():
            await bot.close()
        log.info("Shutdown complete.")

        if os.getenv("BOT_RESTART") == "1":
            log.info("Process restart initiated via execv...")
            os.environ["BOT_RESTART"] = "0"
            os.execv(sys.executable, [sys.executable] + sys.argv)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
