import os
import re
import platform
import time
from typing import Dict, List, Set, Tuple
from .logging_manager import LoggingManager

logger = LoggingManager.get_logger('utils.directory_finder')

class DirectoryFinder:
    """Utility class for finding log directories based on application name."""
    
    # Maximum allowed depth (safety limit)
    MAX_ALLOWED_DEPTH = 4
    
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
    def should_skip_directory(dir_path: str, base_dir: str, max_depth: int) -> Tuple[bool, str]:
        """
        Check if a directory should be skipped based on various criteria.
        
        Args:
            dir_path: The directory path to check
            base_dir: The base directory we're searching from
            max_depth: Maximum allowed depth
            
        Returns:
            Tuple of (should_skip, reason)
        """
        # Calculate current depth relative to base directory
        rel_path = os.path.relpath(dir_path, base_dir)
        current_depth = len(rel_path.split(os.sep)) if rel_path != '.' else 0
        
        # Check hard depth limit
        if current_depth > DirectoryFinder.MAX_ALLOWED_DEPTH:
            raise RuntimeError(f"Directory depth {current_depth} exceeds maximum allowed depth {DirectoryFinder.MAX_ALLOWED_DEPTH}: {dir_path}")
        
        # Check requested depth limit
        if current_depth > max_depth:
            return True, f"Directory depth {current_depth} exceeds requested depth {max_depth}"
        
        # Skip system directories and hidden folders
        if any(part.startswith('.') for part in dir_path.split(os.sep)):
            return True, "Hidden directory"
        
        # Skip known system directories
        if any(skip_dir in dir_path.split(os.sep) for skip_dir in DirectoryFinder.SKIP_DIRS):
            return True, "System directory"
        
        return False, ""
    
    @staticmethod
    def find_log_directories(app_name: str, max_depth: int = 2) -> Dict[str, List[str]]:
        """
        Find potential log directories for the given application name.
        
        Args:
            app_name: The name of the application to search for
            max_depth: Maximum directory depth to search (default: 2)
            
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
        
        # First, search in app data directories
        app_data_dirs = DirectoryFinder.get_app_data_directories()
        logger.debug(f"Searching in app data directories: {', '.join(app_data_dirs)}")
        
        for base_dir in app_data_dirs:
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
                    
                    # Check if this directory contains log files
                    has_log_files = False
                    for file in files:
                        if any(file.lower().endswith(ext) for ext in DirectoryFinder.LOG_EXTENSIONS):
                            has_log_files = True
                            break
                    
                    if not has_log_files:
                        continue
                    
                    # Check directory name against patterns
                    dir_name = os.path.basename(root).lower()
                    
                    # Check for exact matches
                    if app_name_lower in dir_name:
                        logger.info(f"Found exact match: {root}")
                        exact_matches.add(root)
                        continue
                    
                    # Check for potential matches
                    if any(re.search(pattern, dir_name, re.IGNORECASE) for pattern in DirectoryFinder.LOG_PATTERNS):
                        # Only add as potential match if the app name is in the path
                        if app_name_lower in root.lower():
                            logger.info(f"Found potential match: {root}")
                            potential_matches.add(root)
                
                base_time = time.time() - base_start_time
                logger.debug(f"Completed search in {base_dir} in {base_time:.2f}s")
            
            except PermissionError as e:
                logger.error(f"Permission error accessing {base_dir}: {str(e)}")
                continue
            except RuntimeError as e:
                # Re-raise RuntimeError (depth limit exceeded)
                raise
            except Exception as e:
                # Log other errors but continue
                logger.error(f"Error accessing {base_dir}: {str(e)}")
                continue
        
        # If we found matches in app data directories, return them
        if exact_matches or potential_matches:
            total_time = time.time() - start_time
            logger.info(f"Found matches in app data directories: {len(exact_matches)} exact, {len(potential_matches)} potential")
            logger.debug(f"Search completed in {total_time:.2f}s (checked {dirs_checked} dirs, skipped {dirs_skipped} dirs)")
            return {
                'exact_matches': sorted(list(exact_matches)),
                'potential_matches': sorted(list(potential_matches))
            }
        
        # If no matches found in app data, search in Program Files (Windows only)
        if platform.system() == 'Windows':
            logger.debug("No matches in app data, searching Program Files")
            program_files_dirs = [
                os.path.expandvars('%ProgramFiles%'),
                os.path.expandvars('%ProgramFiles(x86)%')
            ]
            
            for base_dir in program_files_dirs:
                if not os.path.exists(base_dir):
                    continue
                
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
                        
                        # Check if this directory contains log files
                        has_log_files = False
                        for file in files:
                            if any(file.lower().endswith(ext) for ext in DirectoryFinder.LOG_EXTENSIONS):
                                has_log_files = True
                                break
                        
                        if not has_log_files:
                            continue
                        
                        # Check directory name against patterns
                        dir_name = os.path.basename(root).lower()
                        
                        # Check for exact matches
                        if app_name_lower in dir_name:
                            logger.info(f"Found exact match: {root}")
                            exact_matches.add(root)
                            continue
                        
                        # Check for potential matches
                        if any(re.search(pattern, dir_name, re.IGNORECASE) for pattern in DirectoryFinder.LOG_PATTERNS):
                            # Only add as potential match if the app name is in the path
                            if app_name_lower in root.lower():
                                logger.info(f"Found potential match: {root}")
                                potential_matches.add(root)
                    
                    base_time = time.time() - base_start_time
                    logger.debug(f"Completed search in {base_dir} in {base_time:.2f}s")
                
                except PermissionError as e:
                    logger.error(f"Permission error accessing {base_dir}: {str(e)}")
                    continue
                except RuntimeError as e:
                    # Re-raise RuntimeError (depth limit exceeded)
                    raise
                except Exception as e:
                    # Log other errors but continue
                    logger.error(f"Error accessing {base_dir}: {str(e)}")
                    continue
        
        total_time = time.time() - start_time
        logger.info(f"Search complete. Found {len(exact_matches)} exact matches and {len(potential_matches)} potential matches")
        logger.debug(f"Total search time: {total_time:.2f}s (checked {dirs_checked} dirs, skipped {dirs_skipped} dirs)")
        
        return {
            'exact_matches': sorted(list(exact_matches)),
            'potential_matches': sorted(list(potential_matches))
        } 