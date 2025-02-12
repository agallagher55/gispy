""""
Create logger function via a decorator
May 25, 2022
"""

import datetime
import functools
import arcpy
import logging
import traceback

TODAY = datetime.datetime.today().date().strftime('%m%d%Y')
LOG_FILE = "logs/logs_{}.log".format(TODAY)

function_logger = logging.getLogger("__name__")
level = logging.DEBUG
function_logger.setLevel(level)

log_formatter = logging.Formatter(
    '%(asctime)s | %(levelname)s | FUNCTION: %(funcName)s | Msgs: %(message)s', datefmt='%d-%b-%y %H:%M:%S'
)

file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(log_formatter)
function_logger.addHandler(file_handler)

# https://stackoverflow.com/questions/13733552/logger-configuration-to-log-to-file-and-print-to-stdout
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
function_logger.addHandler(console_handler)  # print logs to console


def logger(callback):
    @functools.wraps(callback)
    def wrapper(*args, **kwargs):
        print(f"\nRunning: '{callback.__name__}' function... {datetime.datetime.now().strftime('%H:%M:%S - %m/%d/%Y')}")

        if len(args) > 0:
            print(f"Args: {args}")

        if len(list(kwargs.keys())) > 0:
            print(f"Kwargs: {[k + ':' + v for k, v in kwargs.items()]}")

        try:
            value = callback(*args, **kwargs)
            return value

        except arcpy.ExecuteError:
            error_msg = f"\t!ARCPY ERROR: {arcpy.GetMessages(2)}"
            print(error_msg)
            function_logger.error(error_msg)

        except Exception as error:
            traceback_msg = traceback.format_exception(etype=type(error), value=error, tb=error.__traceback__)
            print(f"\tERROR: {error}")
            function_logger.error(f"\tERROR: {error}")
            function_logger.error('\n\t'.join(traceback_msg))

    return wrapper


@logger
def run_processes(var):
    print(f"Running process with this variable '{var}'...")
    return f"Ran process with {var}"


def setupLog(log_file, log_to_console: bool = False):
    formatter = logging.Formatter(fmt='%(asctime)s - %(levelname)s: %(message)s', datefmt='%m-%d-%Y %H:%M:%S')

    handler = logging.FileHandler(log_file)
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger
