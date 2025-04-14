"""
Logger configuration for the YouTube Summarizer Bot.
Uses loguru for better logging capabilities.
"""
import os
import sys
from loguru import logger
from src.config.settings import LOGGING_LEVEL

def setup_logger():
    """
    Configures and returns a loguru logger instance.
    
    Returns:
        logger: Configured loguru logger
    """
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Remove default handlers
    logger.remove()
    
    # Add console handler
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=LOGGING_LEVEL,
        colorize=True
    )
    
    # Add file handler with rotation
    logger.add(
        "logs/youtube_summarizer.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=LOGGING_LEVEL,
        rotation="5 MB",
        compression="zip",
        retention=5
    )
    
    logger.info(f"Logging configured with level: {logger.level(LOGGING_LEVEL).name}")
    
    return logger 