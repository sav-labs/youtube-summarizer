"""
Main entry point for the YouTube Summarizer Bot.
"""
import asyncio
import signal
import sys
from loguru import logger
from src.bot.telegram_bot import TelegramBot

# Global variable to hold the bot instance
bot_instance = None

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    if bot_instance:
        # Cancel all running tasks
        for task in asyncio.all_tasks():
            task.cancel()
    sys.exit(0)

async def main():
    """Main entry point for the application with enhanced error handling."""
    global bot_instance
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        logger.info("Starting YouTube Summarizer Bot")
        bot_instance = TelegramBot()
        await bot_instance.start()
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (KeyboardInterrupt)")
        
    except Exception as e:
        logger.critical(f"Critical error starting bot: {str(e)}", exc_info=True)
        return 1  # Return error code instead of sys.exit
        
    finally:
        logger.info("Cleaning up resources...")
        # Add any cleanup code here if needed
        
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
