#
# GENERAL
#

import logging
import os, re
import sys


def find_files(directory, pattern):
    """
    Recursively find all files matching a certain regex under a given
    directory path
    """
    p = re.compile(pattern)
    for root, dirs, files in os.walk(directory):
        for basename in files:
            if p.match(basename):
                filename = os.path.join(root, basename)
                yield filename


def setup_logging(level, file=None):
    """
    Setup logging options
    """
    # TODO: make dirs if not existing?
    format = '[%(levelname)s] %(asctime)s : %(message)s'

    if file:
        logging.basicConfig(level=level, filename=file.name, format=format)
    else:
        logging.basicConfig(level=level, format=format)


def filter_digits(str):
    """
    Extract the numeric characters of a string and return it as an integer

    """
    return int(''.join(x for x in str if x.isdigit()))


def bundled_app():
    """ Checks if an app is running as bundled """
    return hasattr(sys, '_MEIPASS')


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if bundled_app():
        return os.path.join(sys._MEIPASS, relative_path)

    return os.path.join(os.path.abspath("."), relative_path)


#
# NAMING
#
FILENAME_BATCH_IDS_RE = re.compile('^plate_[0-9]+_b([0-9]+)_p([0-9]+)_(?:template|results)\.xlsx?$')

def get_batch_ids(filename):
    m = FILENAME_BATCH_IDS_RE.match(filename)

    try:
        bait_batch_id, prey_batch_id = [int(x) for x in m.groups()]
    except Exception as exc:
        raise ValueError("No values for batch bait/prey ids could be extracted from the filename ('{}')".format(filename))

    return bait_batch_id, prey_batch_id

#
# PANDAS
#
def assert_empty_df(df, message, columns=None, n_lines=10):
    '''
    Assert that a data frame is empty or raise a ValueError exception otherwise

    :param df: the dataframe
    :param message: an error message to display
    :param columns: columns to display as part of the generated exception message
    :param n_lines: number of lines from the dataframe to display in the error message
    '''
    if not df.empty:
        if not columns:
            columns = df.columns

        exc_message = message
        if n_lines > 0:
            exc_message += "\n" + df[:n_lines].to_string(columns=columns, index=False) + "\n"
            if len(df) > n_lines:
                exc_message += "... displaying {} of a total of {} "\
                               "(check log for a complete list)".format(n_lines, len(df))
                # Show full list in the error log

        logging.error(message + ":\n" + df.to_string(columns=columns))

        raise ValueError(exc_message)


#
# DATE & TIME
#
from datetime import datetime

def timestamp():
    """
    Get local date and time as a string with the default format
    """
    return format_date(get_current_time())


def get_current_time():
    """
    Returns the current local time
    """
    return datetime.now()


def format_date(dt):
    """
    Formats a basic datetime for display
    """
    return dt.strftime("%Y/%m/%d %H:%M:%S")


def pretty_date(dt, default=None):
    """
    Returns string representing "time since" e.g. 3 days ago, 5 hours ago etc.
    Ref: https://bitbucket.org/danjac/newsmeme/src/a281babb9ca3/newsmeme/
    """
    if default is None:
        default = 'just now'

    now = datetime.utcnow()
    diff = now - dt

    periods = (
        (diff.days / 365, 'year', 'years'),
        (diff.days / 30, 'month', 'months'),
        (diff.days / 7, 'week', 'weeks'),
        (diff.days, 'day', 'days'),
        (diff.seconds / 3600, 'hour', 'hours'),
        (diff.seconds / 60, 'minute', 'minutes'),
        (diff.seconds, 'second', 'seconds'),
    )

    for period, singular, plural in periods:
        if not period:
            continue
        if period == 1:
            return u'%d %s ago' % (period, singular)
        else:
            return u'%d %s ago' % (period, plural)

    return default

