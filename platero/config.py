import os
import logging

class BaseConfig(object):
    APP_TITLE = 'Platero'
    APP_VERSION = '0.0.1'

    PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

    TESTING = False
    DEBUG = False

    LOG_FOLDER = os.path.join(PROJECT_ROOT, 'log')

class DefaultConfig(BaseConfig):
    LOG_FILE = os.path.join(BaseConfig.LOG_FOLDER, 'platero.log')
    LOG_LEVEL = logging.INFO

    SQLITE_FILE = os.path.join(BaseConfig.PROJECT_ROOT, 'db/platero.db')
    SQLALCHEMY_DB = "sqlite:///{}".format(SQLITE_FILE)
    SQLALCHEMY_ECHO = False

class DebugConfig(DefaultConfig):
    DEBUG = True
    LOG_LEVEL = logging.DEBUG
    SQLALCHEMY_ECHO = True

class TestConfig(BaseConfig):
    TESTING = True

    LOG_FILE = os.path.join(BaseConfig.LOG_FOLDER, 'tests.log')
    LOG_LEVEL = logging.WARNING

    SQLALCHEMY_DB = 'sqlite:///:memory:'

