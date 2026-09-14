# This module is for utility functions that are used across the package and commonly used functions that are auto-imported into the package namespace.
# Don't introduce package dependencies here without updating the dependencies in pyproject.toml

import logging

logger = logging.getLogger(__name__)

# This function stops the script if the passed argument isn't True
def stop_if_not(check, check_name = "Check"):

    if check:
        logger.debug("%s PASSED", check_name)
        return
    else:
        raise ValueError(f"{check_name} failed.")
