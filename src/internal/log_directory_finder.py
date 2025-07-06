from collections import deque
import json
import os
import re
import platform
from typing import Dict, List, Tuple

from ..utils.logging_manager import LoggingManager
from ..utils.utils import Utils
from ..utils.file_handler import FileHandler

logger = LoggingManager.get_logger('internal.directory_finder')

class LogDirectoryFinder:
    """Utility class for finding log directories based on application name."""
    
    # Maximum allowed depth (safety limit)
    MAX_ALLOWED_DEPTH = 10
    
    # Common log directory patterns
    LOG_PATTERNS = [
        r'logs?',
        r'logfiles?',
        r'logging',
        r'debug',
        r'trace',
        r'output',
        r'data',
        r'storage',
        r'cache',
        r'temp',
        r'tmp'
    ]
    
    # Common log file extensions (using FileHandler's extended list)
    LOG_EXTENSIONS = FileHandler.LOG_EXTENSIONS
    
    # Directories to skip (system directories, etc.)
    SKIP_DIRS = {
        'node_modules',
        'dist',
        'build',
        'target',
        'bin',
        'obj',
        'Debug',
        'Release',
        'x64',
        'x86',
        'amd64',
        'win32',
        'win64',
        '.git',
        '.svn',
        '.vs',
        '.idea',
        '__pycache__',
        'venv',
        'env',
        '.env',
        'virtualenv',
        'site-packages',
        'lib',
        'include',
        'share',
        'doc',
        'docs',
        'test',
        'tests',
        'examples',
        'samples',
        'templates',
        'cache',
        'temp',
        'tmp',
        'Application Data'  # Add this to prevent recursive Application Data directories
    }
    
    # Cache file for custom log directories
    CACHE_FILE = os.path.join(os.path.expanduser('~'), '.protokoll', 'custom_log_dirs.json')
    
    @staticmethod
    def _load_custom_directories() -> List[str]:
        """Load custom log directories from cache file."""
        try:
            if os.path.exists(LogDirectoryFinder.CACHE_FILE):
                with open(LogDirectoryFinder.CACHE_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading custom directories: {str(e)}")
        return []
    
    @staticmethod
    def _save_custom_directories(directories: List[str]) -> None:
        """Save custom log directories to cache file."""
        try:
            os.makedirs(os.path.dirname(LogDirectoryFinder.CACHE_FILE), exist_ok=True)
            with open(LogDirectoryFinder.CACHE_FILE, 'w') as f:
                json.dump(directories, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving custom directories: {str(e)}")
    
    @staticmethod
    def add_custom_directory(directory: str) -> Tuple[bool, str]:
        """
        Add a custom log directory to the shared list.
        
        Args:
            directory: The directory path to add
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Validate directory exists and is accessible
            if not os.path.exists(directory):
                return False, f"Directory does not exist: {directory}"
            if not os.path.isdir(directory):
                return False, f"Path is not a directory: {directory}"
            
            # Load existing directories
            custom_dirs = LogDirectoryFinder._load_custom_directories()
            
            # Check if directory is already in the list
            if directory in custom_dirs:
                return False, f"Directory already in custom directories: {directory}"
            
            # Add directory to list
            custom_dirs.append(directory)
            
            # Save updated list
            LogDirectoryFinder._save_custom_directories(custom_dirs)
            
            return True, f"Added custom directory: {directory}"
            
        except Exception as e:
            return False, f"Error adding custom directory: {str(e)}"
    
    @staticmethod
    def remove_custom_directory(directory: str) -> Tuple[bool, str]:
        """
        Remove a custom log directory from the shared list.
        
        Args:
            directory: The directory path to remove
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Load existing directories
            custom_dirs = LogDirectoryFinder._load_custom_directories()
            
            # Check if directory is in the list
            if directory not in custom_dirs:
                return False, f"Directory not found in custom directories: {directory}"
            
            # Remove directory from list
            custom_dirs.remove(directory)
            
            # Save updated list
            LogDirectoryFinder._save_custom_directories(custom_dirs)
            
            return True, f"Removed custom directory: {directory}"
            
        except Exception as e:
            return False, f"Error removing custom directory: {str(e)}"
    
    @staticmethod
    def get_custom_directories() -> List[str]:
        """
        Get the list of custom log directories.
        
        Returns:
            List of custom directory paths
        """
        return LogDirectoryFinder._load_custom_directories()
    
    @staticmethod
    def get_app_data_directories() -> List[str]:
        """Get the application data directories for the current OS."""
        app_data_dirs = []
        
        if platform.system() == 'Windows':
            # Windows app data directories
            app_data_dirs.extend([
                os.path.expandvars('%LOCALAPPDATA%'),
                os.path.expandvars('%APPDATA%'),
                os.path.expandvars('%PROGRAMDATA%'),
                os.path.join(os.path.expandvars('%USERPROFILE%'), 'AppData', 'LocalLow')
            ])
        elif platform.system() == 'Darwin':  # macOS
            app_data_dirs.extend([
                os.path.expanduser('~/Library/Application Support'),
                os.path.expanduser('~/Library/Logs'),
                os.path.expanduser('~/Library/Caches')
            ])
        else:  # Linux and other Unix-like
            app_data_dirs.extend([
                os.path.expanduser('~/.config'),
                os.path.expanduser('~/.local/share'),
                os.path.expanduser('~/.cache'),
                '/var/log'
            ])
        
        # Filter out non-existent directories
        return [d for d in app_data_dirs if os.path.exists(d)]
    
    @staticmethod
    def validate_search_query(app_name: str) -> Tuple[bool, str]:
        """
        Validate if the search query is allowed.
        
        Args:
            app_name: The name of the application to search for
            
        Returns:
            Tuple of (is_valid, reason)
        """
        if not app_name:
            return False, "No application name provided"
        
        app_name_lower = app_name.lower()
        
        # Check if the app name matches any system directory
        for skip_dir in LogDirectoryFinder.SKIP_DIRS:
            if skip_dir.lower() in app_name_lower or app_name_lower in skip_dir.lower():
                return False, f"Search term '{app_name}' matches system directory '{skip_dir}'. Please use manual directory selection."
        
        return True, ""

    @staticmethod
    def find_log_directories(app_name: str, max_depth: int = 3) -> Dict[str, List[str]]:
        """Refactored directory search with clear exact/potential match separation."""
        max_depth = min(max_depth, LogDirectoryFinder.MAX_ALLOWED_DEPTH)
        
        # Validate app name
        is_valid, reason = LogDirectoryFinder.validate_search_query(app_name)
        if not is_valid:
            logger.warning(f"Invalid search query: {reason}")
            return {'exact_matches': [], 'potential_matches': []}
        
        app_name_lower = app_name.lower()
        exact_matches = set()
        potential_matches = set()
        dirs_checked = 0
        dirs_skipped = 0

        # Define base directories to search
        base_dirs = (
            LogDirectoryFinder.get_custom_directories() +
            LogDirectoryFinder.get_app_data_directories()
        )
        if platform.system() == 'Windows':
            base_dirs.extend([
                os.path.expandvars('%ProgramFiles%'),
                os.path.expandvars('%ProgramFiles(x86)%')
            ])

        # 1. Search for exact matches
        logger.info(f"Searching for exact matches: {app_name}")
        for base_dir in base_dirs:
            if not os.path.exists(base_dir):
                continue
                
            for root, dirs, files in os.walk(base_dir):
                # Update skip counters
                new_dirs = []
                for d in dirs:
                    full_path = os.path.join(root, d)
                    if LogDirectoryFinder._should_skip(full_path, base_dir, max_depth):
                        dirs_skipped += 1
                    else:
                        new_dirs.append(d)
                dirs[:] = new_dirs
                
                # Process current directory
                dirs_checked += 1
                dir_name = os.path.basename(root).lower()
                
                # Check exact match
                if dir_name == app_name_lower:
                    if LogDirectoryFinder._has_log_files(root, max_depth):
                        exact_matches.add(root)
                        logger.info(f"Found exact match: {root}")
        
        # Return early if exact matches found
        if exact_matches:
            logger.info(f"Found {len(exact_matches)} exact matches")
            return {
                'exact_matches': sorted(exact_matches),
                'potential_matches': []
            }

        # 2. Search for potential matches
        logger.info("No exact matches found, searching for potential matches")
        for base_dir in base_dirs:
            if not os.path.exists(base_dir):
                continue
                
            for root, dirs, files in os.walk(base_dir):
                # Update skip counters
                new_dirs = []
                for d in dirs:
                    full_path = os.path.join(root, d)
                    if LogDirectoryFinder._should_skip(full_path, base_dir, max_depth):
                        dirs_skipped += 1
                    else:
                        new_dirs.append(d)
                dirs[:] = new_dirs
                
                # Process current directory
                dirs_checked += 1
                
                # Check potential candidate
                if LogDirectoryFinder._is_potential_candidate(root, app_name_lower):
                    if LogDirectoryFinder._has_log_files(root, max_depth):
                        potential_matches.add(root)
                        logger.info(f"Found potential match: {root}")
                    else:
                        logger.info(f"No log files found in potential match: {root}")

        # Return results
        logger.info(f"Found {len(potential_matches)} potential matches")
        return {
            'exact_matches': sorted(exact_matches),
            'potential_matches': sorted(potential_matches)
        }

    @staticmethod
    def _should_skip(dir_path: str, base_dir: str, max_depth: int) -> bool:
        """Determine if directory should be skipped during traversal."""
        try:
            rel_path = os.path.relpath(dir_path, base_dir)
            current_depth = rel_path.count(os.sep) if rel_path != '.' else 0
            
            # Skip based on depth
            if current_depth > max_depth:
                return True
            
            # Skip hidden/system directories
            if any(part.startswith('.') for part in dir_path.split(os.sep)):
                return True
                
            # Skip special directories
            if any(skip_dir in dir_path.split(os.sep) for skip_dir in LogDirectoryFinder.SKIP_DIRS):
                return True
                
            return False
        except Exception as e:
            logger.error(f"Error checking directory {dir_path}: {str(e)}")
            return True

    @staticmethod
    def _has_log_files(directory: str, max_depth: int) -> bool:
        """Check if directory contains log files using BFS with depth limit."""
        queue = deque([(directory, 0)])
        while queue:
            current_dir, depth = queue.popleft()
            try:
                for entry in os.listdir(current_dir):
                    entry_path = os.path.join(current_dir, entry)
                    if os.path.isfile(entry_path):
                        if any(entry.lower().endswith(ext) for ext in LogDirectoryFinder.LOG_EXTENSIONS):
                            return True
                    elif os.path.isdir(entry_path) and depth < max_depth:
                        queue.append((entry_path, depth + 1))
            except PermissionError:
                continue
        return False

    @staticmethod
    def _is_potential_candidate(dir_path: str, app_name_lower: str) -> bool:
        """Determine if directory is a potential log directory candidate."""
        dir_name = os.path.basename(dir_path).lower()
        dir_path_lower = dir_path.lower()
        
        # Match log patterns and app name in path
        if any(re.search(pattern, dir_name, re.IGNORECASE) for pattern in LogDirectoryFinder.LOG_PATTERNS):
            return app_name_lower in dir_path_lower
        
        # Check string similarity for longer names
        if len(app_name_lower) > 6 and len(dir_name) > 6:
            return Utils.is_similar_strings(dir_name, app_name_lower)
        
        return False
