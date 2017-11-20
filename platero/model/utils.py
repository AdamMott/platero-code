
from sqlalchemy.sql.elements import ClauseElement
from sqlalchemy import Column, DateTime
from platero.utils import get_current_time

# TODO: Make methods thread safe?
def update_or_create(db_session, model, values=None, **kwargs):
    """
    Update an existing instance of a model if found, or create new
    otherwise
    """
    instance = db_session.query(model).filter_by(**kwargs).first()
    if instance:
        db_session.query(model).filter_by(**kwargs).update(values)
        return instance, False
    else:
        params = dict((k, v) for k, v in kwargs.items() if not isinstance(v, ClauseElement))
        params.update(values or {})
        instance = model(**params)
        db_session.add(instance)
        return instance, True

def get_or_create(db_session, model, defaults=None, **kwargs):
    """
    Get an existing instance of a model if found, or create new
    otherwise
    """
    instance = db_session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance, False
    else:
        params = dict((k, v) for k, v in kwargs.items() if not isinstance(v, ClauseElement))
        params.update(defaults or {})
        instance = model(**params)
        db_session.add(instance)
        return instance, True

class TimestampMixin(object):
    """
    A table mixing to add timestamp columns to any entity
    """
    created_at = Column(DateTime, default=get_current_time)
    updated_at = Column(DateTime, onupdate=get_current_time)