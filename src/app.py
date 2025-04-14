"""
Main entry point for the YouTube Summarizer Bot.
"""
import asyncio
import sys
from loguru import logger
from src.bot.telegram_bot import TelegramBot

async def main():
    """Main entry point for the application."""
    try:
        logger.info("Starting YouTube Summarizer Bot")
        bot = TelegramBot()
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (KeyboardInterrupt)")
    except Exception as e:
        logger.critical(f"Critical error starting bot: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
