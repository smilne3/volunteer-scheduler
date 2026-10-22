class InputError(Exception):
    """A problem with the input files, written for the coordinator to read.

    The command line prints the message as-is (no traceback) and exits with 1.
    """
