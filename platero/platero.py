import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.scoping import scoped_session

from .config import DefaultConfig
from .utils import setup_logging
from .model.models import BaseModel

config = DefaultConfig()
logger = logging.getLogger()

# TODO: More elegant way for db connection handling could be used
# NOTE: the listener is necessary for SQLite to enforce foreign keys
from sqlalchemy.interfaces import PoolListener
class ForeignKeysListener(PoolListener):
    def connect(self, dbapi_con, con_record):
        db_cursor = dbapi_con.execute('pragma foreign_keys=ON')

from sqlalchemy.pool import StaticPool
__db_engine = create_engine('sqlite://',
                    connect_args={'check_same_thread':False},
                    poolclass=StaticPool,
                    listeners=[ForeignKeysListener()],
                    echo=config.SQLALCHEMY_ECHO)

# __db_engine = create_engine(config.SQLALCHEMY_DB, listeners=[ForeignKeysListener()], echo=config.SQLALCHEMY_ECHO)

BaseModel.metadata.bind = __db_engine

def db_init():
    BaseModel.metadata.create_all(__db_engine)

def db_reset(delete=False):

    if delete and os.path.exists(config.SQLITE_FILE):
        os.remove(config.SQLITE_FILE)

    for table in reversed(BaseModel.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    db_init()

DBSession = scoped_session(sessionmaker(bind=__db_engine))
db = DBSession()
db_init()










