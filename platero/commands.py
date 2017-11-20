"""
CLI utility classes and methods
"""

import os, sys
from time import time
import logging
import argparse

from .platero import config
from .utils import setup_logging

class CliCommand(object):
    short_description = "Basic command line interface program"

    @classmethod
    def _arg_parser(cls):
        '''
        return default argument parser
        '''
        return argparse.ArgumentParser()

    @classmethod
    def _parse_args(cls):
        parser = cls._arg_parser()
        add_default_args(parser)

        args = parser.parse_args()
        args.loglevel = parse_verbosity(args.loglevel)

        return args

    @classmethod
    def _main(cls, args):
        raise NotImplementedError("%s command class must implement a _main method" % cls.__name__)

    @classmethod
    def run(cls):
        args = cls._parse_args()

        setup_logging(args.loglevel, args.logfile)
        logging.info("--- Starting '{command}' ---".format(command=cls.short_description))
        start = time()

        cls._main(args)

        logging.info("--- '{command}' finished in {time:.5f} seconds ---".format(
            command=cls.short_description, time=(time() - start)))


def add_default_args(parser):
    ''' Adds common arguments to a script '''
    parser.add_argument('-l', '--logfile', type=argparse.FileType('a'), nargs='?', help='Log file', default=config.LOG_FILE)
    parser.add_argument('-v', '--verbosity', dest='loglevel', action='count', help='Increase program verbosity', default=3)


def arg_is_valid_directory(parser, arg):
    if not os.path.isdir(arg):
        parser.error('Invalid directory provided: {}'.format(arg))
    else:
        # File exists so return the directory
        return arg


def arg_int_in_range(parser, arg, min=None, max=None):
    x = int(arg)
    if (min and x < min) or  (max and x > max):
        parser.error('Value {} is out of range [{},{}]'.format(arg, min, max))
    else:
        return x


def parse_verbosity(verbosity):
    ''' Parse verbosity parameters '''
    try:
        log_level = [logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG][verbosity - 1]
    except IndexError:
        log_level = logging.INFO

    return log_level
