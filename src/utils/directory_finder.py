import os
import re
import platform
import time
import json
from typing import Dict, List, Set, Tuple
from .logging_manager import LoggingManager
from .utils import Utils

logger = LoggingManager.get_logger('utils.directory_finder')

class DirectoryFinder:
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
    
    # Common log file extensions
    LOG_EXTENSIONS = [
        '.log',
        '.txt',
        '.csv',
        '.json',
        '.xml',
        '.yaml',
        '.yml',
        '.ini',
        '.conf',
        '.cfg'
    ]
    
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
            if os.path.exists(DirectoryFinder.CACHE_FILE):
                with open(DirectoryFinder.CACHE_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading custom directories: {str(e)}")
        return []
    
    @staticmethod
    def _save_custom_directories(directories: List[str]) -> None:
        """Save custom log directories to cache file."""
        try:
            os.makedirs(os.path.dirname(DirectoryFinder.CACHE_FILE), exist_ok=True)
            with open(DirectoryFinder.CACHE_FILE, 'w') as f:
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
            custom_dirs = DirectoryFinder._load_custom_directories()
            
            # Check if directory is already in the list
            if directory in custom_dirs:
                return False, f"Directory already in custom directories: {directory}"
            
            # Add directory to list
            custom_dirs.append(directory)
            
            # Save updated list
            DirectoryFinder._save_custom_directories(custom_dirs)
            
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
            custom_dirs = DirectoryFinder._load_custom_directories()
            
            # Check if directory is in the list
            if directory not in custom_dirs:
                return False, f"Directory not found in custom directories: {directory}"
            
            # Remove directory from list
            custom_dirs.remove(directory)
            
            # Save updated list
            DirectoryFinder._save_custom_directories(custom_dirs)
            
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
        return DirectoryFinder._load_custom_directories()
    
    @staticmethod
    def get_app_data_directories() -> List[str]:
        """Get the application data directories for the current OS."""
        app_data_dirs = []
        
        if platform.system() == 'Windows':
            # Windows app data directories
            app_data_dirs.extend([
                os.path.expandvars('%LOCALAPPDATA%'),
                os.path.expandvars('%APPDATA%'),
                os.path.expandvars('%PROGRAMDATA%')
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
        for skip_dir in DirectoryFinder.SKIP_DIRS:
            if skip_dir.lower() in app_name_lower or app_name_lower in skip_dir.lower():
                return False, f"Search term '{app_name}' matches system directory '{skip_dir}'. Please use manual directory selection."
        
        return True, ""
    
    @staticmethod
    def find_log_directories(app_name: str, max_depth: int = 3) -> Dict[str, List[str]]:
        """
        Find potential log directories for the given application name.
        
        Args:
            app_name: The name of the application to search for
            max_depth: Maximum directory depth to search (default: 3)
            
        Returns:
            Dictionary containing 'exact_matches' and 'potential_matches' lists
        """
        start_time = time.time()
        
        # Validate search query
        is_valid, reason = DirectoryFinder.validate_search_query(app_name)
        if not is_valid:
            logger.warning(f"Invalid search query: {reason}")
            return {'exact_matches': [], 'potential_matches': []}
        
        # Ensure max_depth doesn't exceed the hard limit
        max_depth = min(max_depth, DirectoryFinder.MAX_ALLOWED_DEPTH)
        logger.info(f"Starting directory search for application: {app_name} (max depth: {max_depth})")
        
        # Convert app name to lowercase for case-insensitive matching
        app_name_lower = app_name.lower()
        
        exact_matches = set()
        potential_matches = set()
        dirs_checked = 0
        dirs_skipped = 0
        
        # Store directory information for potential matches
        # Key: directory basename (lowercase), Value: list of full paths
        potential_dirs: Dict[str, List[str]] = {}
        
        def should_skip_dir(dir_path: str, base_dir: str) -> bool:
            """Helper function to check if a directory should be skipped"""
            try:
                rel_path = os.path.relpath(dir_path, base_dir)
                current_depth = len(rel_path.split(os.sep)) if rel_path != '.' else 0
                
                if current_depth > DirectoryFinder.MAX_ALLOWED_DEPTH:
                    raise RuntimeError(f"Directory depth {current_depth} exceeds maximum allowed depth {DirectoryFinder.MAX_ALLOWED_DEPTH}: {dir_path}")
                
                if current_depth > max_depth:
                    return True
                
                if any(part.startswith('.') for part in dir_path.split(os.sep)):
                    return True
                
                if any(skip_dir in dir_path.split(os.sep) for skip_dir in DirectoryFinder.SKIP_DIRS):
                    return True
                
                return False
            except Exception as e:
                logger.error(f"Error checking directory {dir_path}: {str(e)}")
                raise
        
        def search_directory(base_dir: str, check_exact_only: bool = False) -> None:
            """Search a directory and its subdirectories for log directories"""
            nonlocal dirs_checked
            
            try:
                logger.debug(f"Starting search in: {base_dir}")
                base_start_time = time.time()
                last_log_time = time.time()
                
                # Walk through the directory tree with depth limit
                for root, dirs, files in os.walk(base_dir):
                    current_time = time.time()
                    dirs_checked += 1
                    
                    # Log progress every 2 seconds
                    if current_time - last_log_time >= 2:
                        logger.debug(f"Still searching... Currently in: {root}")
                        last_log_time = current_time
                    
                    # Filter out directories that should be skipped BEFORE os.walk continues
                    dirs[:] = [d for d in dirs if not should_skip_dir(os.path.join(root, d), base_dir)]
                    
                    try:
                        # Check if directory exists and is accessible
                        if not os.path.isdir(root):
                            continue
                        
                        # Check directory name against patterns FIRST (cheap check)
                        dir_name = os.path.basename(root).lower()
                        
                        # Check for exact matches (case-insensitive)
                        if dir_name == app_name_lower:
                            # Found a matching directory name, now check for log files in this directory and its subdirectories
                            has_log_files = False
                            try:
                                # Check current directory
                                for file in os.listdir(root):
                                    if os.path.isfile(os.path.join(root, file)):
                                        if any(file.lower().endswith(ext) for ext in DirectoryFinder.LOG_EXTENSIONS):
                                            has_log_files = True
                                            break
                                
                                # If no log files in current directory, check subdirectories up to max_depth
                                if not has_log_files:
                                    for subdir, _, files in os.walk(root):
                                        # Calculate depth relative to the matching directory
                                        rel_path = os.path.relpath(subdir, root)
                                        current_depth = len(rel_path.split(os.sep)) if rel_path != '.' else 0
                                        
                                        if current_depth > max_depth:
                                            continue
                                        
                                        for file in files:
                                            if any(file.lower().endswith(ext) for ext in DirectoryFinder.LOG_EXTENSIONS):
                                                has_log_files = True
                                                break
                                        
                                        if has_log_files:
                                            break
                            except PermissionError:
                                continue
                            
                            if has_log_files:
                                logger.info(f"Found exact match with log files: {root}")
                                exact_matches.add(root)
                            else:
                                logger.info(f"Found exact match without log files: {root}")
                                # Still add as potential match since the name matches
                                if dir_name not in potential_dirs:
                                    potential_dirs[dir_name] = []
                                potential_dirs[dir_name].append(root)
                            continue
                        
                        # If we're only checking for exact matches, continue to next directory
                        if check_exact_only:
                            continue
                        
                        # Store directory for potential match checking
                        if dir_name not in potential_dirs:
                            potential_dirs[dir_name] = []
                        potential_dirs[dir_name].append(root)
                        
                        # Only check for log files if we're interested in this directory
                        try:
                            files = os.listdir(root)
                        except PermissionError:
                            continue
                        
                        # Check for log files
                        has_log_files = False
                        for file in files:
                            if os.path.isfile(os.path.join(root, file)):
                                if any(file.lower().endswith(ext) for ext in DirectoryFinder.LOG_EXTENSIONS):
                                    has_log_files = True
                                    break
                        
                        if not has_log_files:
                            # Remove from potential matches if no log files found
                            if dir_name in potential_dirs:
                                potential_dirs[dir_name].remove(root)
                                if not potential_dirs[dir_name]:
                                    del potential_dirs[dir_name]
                    
                    except Exception as e:
                        logger.error(f"Error checking directory {root}: {str(e)}")
                
                base_time = time.time() - base_start_time
                logger.debug(f"Completed search in {base_dir} in {base_time:.2f}s")
            
            except PermissionError as e:
                logger.error(f"Permission error accessing {base_dir}: {str(e)}")
            except RuntimeError as e:
                # Re-raise RuntimeError (depth limit exceeded)
                raise
            except Exception as e:
                # Log other errors but continue
                logger.error(f"Error accessing {base_dir}: {str(e)}")
        
        def check_potential_matches() -> None:
            """Check stored directories for potential matches"""
            app_name_is_long_enough = len(app_name_lower) > 6
            for dir_name, paths in potential_dirs.items():
                for path in paths:
                    # Check for potential matches using multiple criteria
                    is_potential_match = False
                    
                    # 1. Check if directory name matches log patterns
                    if any(re.search(pattern, dir_name, re.IGNORECASE) for pattern in DirectoryFinder.LOG_PATTERNS):
                        # Only add as potential match if the app name is in the path
                        if app_name_lower in path.lower():
                            is_potential_match = True
                    
                    # 2. For longer strings, also check if they're similar using Utils.is_similar_strings
                    if app_name_is_long_enough and len(dir_name) > 6:
                        if Utils.is_similar_strings(dir_name, app_name_lower):
                            is_potential_match = True
                    
                    if is_potential_match:
                        logger.info(f"Found potential match: {path}")
                        potential_matches.add(path)
        
        # First, check custom directories for exact matches only
        custom_dirs = DirectoryFinder.get_custom_directories()
        if custom_dirs:
            logger.debug(f"Checking custom directories: {', '.join(custom_dirs)}")
            for custom_dir in custom_dirs:
                search_directory(custom_dir, check_exact_only=True)
        
        # If we found exact matches in custom directories, return them
        if exact_matches:
            total_time = time.time() - start_time
            logger.info(f"Found exact matches in custom directories: {len(exact_matches)}")
            logger.debug(f"Search completed in {total_time:.2f}s (checked {dirs_checked} dirs)")
            return {
                'exact_matches': sorted(list(exact_matches)),
                'potential_matches': []
            }
        
        # If no exact matches in custom directories, search in app data directories
        app_data_dirs = DirectoryFinder.get_app_data_directories()
        logger.debug(f"Searching in app data directories: {', '.join(app_data_dirs)}")
        
        for base_dir in app_data_dirs:
            search_directory(base_dir, check_exact_only=True)
        
        # If we found exact matches in app data directories, return them
        if exact_matches:
            total_time = time.time() - start_time
            logger.info(f"Found exact matches in app data directories: {len(exact_matches)}")
            logger.debug(f"Search completed in {total_time:.2f}s (checked {dirs_checked} dirs, skipped {dirs_skipped} dirs)")
            return {
                'exact_matches': sorted(list(exact_matches)),
                'potential_matches': []
            }
        
        # If no exact matches found in app data, search in Program Files (Windows only)
        if platform.system() == 'Windows':
            logger.debug("No exact matches in app data, searching Program Files")
            program_files_dirs = [
                os.path.expandvars('%ProgramFiles%'),
                os.path.expandvars('%ProgramFiles(x86)%')
            ]
            
            for base_dir in program_files_dirs:
                if os.path.exists(base_dir):
                    search_directory(base_dir, check_exact_only=True)
        
        # If we found exact matches in Program Files, return them
        if exact_matches:
            total_time = time.time() - start_time
            logger.info(f"Found exact matches in Program Files: {len(exact_matches)}")
            logger.debug(f"Search completed in {total_time:.2f}s (checked {dirs_checked} dirs, skipped {dirs_skipped} dirs)")
            return {
                'exact_matches': sorted(list(exact_matches)),
                'potential_matches': []
            }
        
        # If no exact matches found anywhere, check for potential matches
        check_potential_matches()
        
        total_time = time.time() - start_time
        logger.info(f"Search complete. Found {len(exact_matches)} exact matches and {len(potential_matches)} potential matches")
        logger.debug(f"Total search time: {total_time:.2f}s (checked {dirs_checked} dirs, skipped {dirs_skipped} dirs)")
        
        return {
            'exact_matches': sorted(list(exact_matches)),
            'potential_matches': sorted(list(potential_matches))
        } 