import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

from ..utils.config_manager import ConfigManager
from ..utils.directory_finder import DirectoryFinder
from ..utils.logging_manager import LoggingManager

logger = LoggingManager.get_logger('internal.tracker')

class Tracker:
    def __init__(self, name: str, description: str = "", config_manager: Optional[ConfigManager] = None):
        self.name = name
        self.description = description
        self.log_directories: Set[str] = set()  # Set of log directory paths
        self.created_at = datetime.now()
        self.config_manager = config_manager or ConfigManager()
        
        # Create tracker directory
        self.tracker_dir = Path(self.config_manager.config_dir) / "trackers" / name
        self.tracker_dir.mkdir(parents=True, exist_ok=True)
    
    def save_metadata(self) -> None:
        """Save tracker metadata to a JSON file"""
        metadata = {
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "log_directories": list(self.log_directories)  # Convert set to list for JSON serialization
        }
        
        metadata_file = self.tracker_dir / "metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4)
    
    def add_log_directory(self, directory: str) -> bool:
        """Add a log directory to the tracker"""
        if not os.path.exists(directory):
            raise ValueError(f"Directory does not exist: {directory}")
        
        if not os.path.isdir(directory):
            raise ValueError(f"Path is not a directory: {directory}")
        
        # Add directory to set
        self.log_directories.add(directory)
        self.save_metadata()
        return True
    
    def remove_log_directory(self, directory: str) -> None:
        """Remove a log directory from the tracker"""
        if directory in self.log_directories:
            self.log_directories.remove(directory)
            self.save_metadata()
    
    def get_log_files(self) -> List[Dict[str, Any]]:
        """Get all log files in the tracked directories"""
        log_files = []
        for directory in self.log_directories:
            try:
                for file in os.listdir(directory):
                    if any(file.lower().endswith(ext) for ext in DirectoryFinder.LOG_EXTENSIONS):
                        file_path = os.path.join(directory, file)
                        if os.path.isfile(file_path):
                            log_files.append({
                                "path": file_path,
                                "last_modified": os.path.getmtime(file_path)
                            })
            except Exception as e:
                logger.error(f"Error reading directory {directory}: {e}")
        return log_files
    
    def get_log_directories(self) -> List[str]:
        """Get all log directories in the tracker"""
        return list(self.log_directories)
    
    def search_logs(self, query: str) -> List[Dict[str, Any]]:
        """Search through all log files for a specific query"""
        results = []
        for log_file in self.get_log_files():
            try:
                with open(log_file["path"], "r", encoding="utf-8") as f:
                    for line_num, line in enumerate(f, 1):
                        if query.lower() in line.lower():
                            results.append({
                                "file": log_file["path"],
                                "line": line_num,
                                "content": line.strip()
                            })
            except Exception as e:
                logger.error(f"Error reading file {log_file['path']}: {e}")
        return results
    
    @classmethod
    def load(cls, name: str, config_manager: Optional[ConfigManager] = None) -> Optional['Tracker']:
        """Load a tracker from disk"""
        config_manager = config_manager or ConfigManager()
        tracker_dir = Path(config_manager.config_dir) / "trackers" / name
        
        if not tracker_dir.exists():
            return None
        
        metadata_file = tracker_dir / "metadata.json"
        if not metadata_file.exists():
            return None
        
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            
            tracker = cls(metadata["name"], metadata["description"], config_manager)
            tracker.created_at = datetime.fromisoformat(metadata["created_at"])
            tracker.log_directories = set(metadata.get("log_directories", []))
            return tracker
        except Exception as e:
            return None
    
    @classmethod
    def list_trackers(cls, config_manager: Optional[ConfigManager] = None) -> List['Tracker']:
        """List all available trackers"""
        config_manager = config_manager or ConfigManager()
        trackers_dir = Path(config_manager.config_dir) / "trackers"
        
        if not trackers_dir.exists():
            return []
        
        trackers = []
        for name in os.listdir(trackers_dir):
            tracker = cls.load(name, config_manager)
            if tracker:
                trackers.append(tracker)
        return trackers 