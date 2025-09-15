import json
import os
from pathlib import Path
from typing import Any, Dict

from ..utils.logging_setup import get_logger

logger = get_logger('utils.config_manager')

class ConfigManager:
    def __init__(self):
        self.app_name = "Protokoll"
        self.config_dir = Path(os.path.expanduser("~")) / ".protokoll"
        self.config_file = self.config_dir / "config.json"
        self.cache_dir = self.config_dir / "cache"
        
        # Create necessary directories
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Default configuration
        self.default_config = {
            "window": {
                "width": 1024,
                "height": 768,
                "x": None,
                "y": None
            },
            "recent_trackers": [],
            "last_tracker": None,
            "theme": "light",
            "log_viewer": {
                "font_size": 12,
                "font_family": "Consolas",
                "line_wrap": True
            }
        }
        
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default if not exists"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Merge with default config to ensure all keys exist
                    return {**self.default_config, **config}
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                return self.default_config.copy()
        return self.default_config.copy()
    
    def save_config(self) -> None:
        """Save current configuration to file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value"""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self.save_config()
    
    def add_recent_tracker(self, tracker_name: str) -> None:
        """Add a tracker to recent trackers list"""
        recent = self.get('recent_trackers', [])
        if tracker_name in recent:
            recent.remove(tracker_name)
        recent.insert(0, tracker_name)
        recent = recent[:10]  # Keep only 10 most recent
        self.set('recent_trackers', recent)
    
    def get_cache_path(self, name: str) -> Path:
        """Get path for a cache file"""
        return self.cache_dir / f"{name}.cache"
    
    def save_cache(self, name: str, data: Any) -> None:
        """Save data to cache"""
        cache_file = self.get_cache_path(name)
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Error saving cache {name}: {e}")
    
    def load_cache(self, name: str, default: Any = None) -> Any:
        """Load data from cache"""
        cache_file = self.get_cache_path(name)
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading cache {name}: {e}")
        return default 