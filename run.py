import sys

if "--smoke-test" in sys.argv[1:]:
    # Before any other app import: modules resolve their paths as they load.
    from src.utils.smoke_test import isolate_environment
    isolate_environment()

from src.main import main

if __name__ == "__main__":
    main()
