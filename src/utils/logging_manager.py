import logging
import sys

class LoggingManager:
    """Manages application-wide logging configuration."""
    
    @staticmethod
    def setup_logging(level=logging.INFO):
        """
        Set up logging configuration for the application.
        
        Args:
            level: The logging level to use (default: INFO)
        """
        # Create logger
        logger = logging.getLogger('protokoll')
        logger.setLevel(level)
        
        # Create console handler with formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(console_handler)
        
        return logger
    
    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """
        Get a logger instance for a specific module.
        
        Args:
            name: The name of the module (e.g., 'ui.tracker_dialog')
            
        Returns:
            A logger instance configured for the module
        """
        return logging.getLogger(f'protokoll.{name}') 