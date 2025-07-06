#!/usr/bin/env python3
"""
Simple test script for the FileHandler class.
"""

import os
import tempfile
import gzip
from src.utils.file_handler import FileHandler

def test_file_handler():
    """Test the FileHandler functionality"""
    handler = FileHandler()
    
    print("Testing FileHandler...")
    
    # Test 1: Create a simple text file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
        f.write("This is a test log file\nWith multiple lines\nAnd some content")
        test_file = f.name
    
    try:
        # Test file info
        info = handler.get_file_info(test_file)
        print(f"✓ File info: {info}")
        
        # Test file validation
        is_valid, reason, val_info = handler.validate_file_for_viewing(test_file)
        print(f"✓ File validation: {is_valid}, {reason}")
        
        # Test file reading
        success, content, read_info = handler.read_file_safe(test_file)
        print(f"✓ File reading: {success}")
        print(f"  Content: {repr(content)}")
        
    finally:
        os.unlink(test_file)
    
    # Test 2: Create a compressed file
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.log.gz', delete=False) as f:
        with gzip.open(f, 'wt') as gz:
            gz.write("This is a compressed log file\nWith content")
        compressed_file = f.name
    
    try:
        # Test compressed file
        info = handler.get_file_info(compressed_file)
        print(f"✓ Compressed file info: {info}")
        
        success, content, read_info = handler.read_file_safe(compressed_file)
        print(f"✓ Compressed file reading: {success}")
        print(f"  Content: {repr(content)}")
        
    finally:
        os.unlink(compressed_file)
    
    # Test 3: Test extension checking
    test_files = [
        "test.log",
        "test.txt",
        "test.out",
        "test.err",
        "test.gz",
        "test.bz2",
        "test.zip",
        "test.exe",
        "test.bin"
    ]
    
    print("\nTesting file extension detection:")
    for test_file in test_files:
        is_log = FileHandler.is_log_file(test_file)
        is_compressed = FileHandler.is_compressed(test_file)
        print(f"  {test_file}: log={is_log}, compressed={is_compressed}")
    
    print("\n✓ All tests completed!")

if __name__ == "__main__":
    test_file_handler() 