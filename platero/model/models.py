from sqlalchemy import Column, ForeignKey, Integer, String, Boolean, Float, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from .naming import *

PROTEIN_ID_REGEX = 'AT[0-9]G[0-9]{5}(?:\.\w+)?'

BaseModel = declarative_base()

#  TODO: define a custom type for Protein Id and replace the fixed
#  length string. Could also be used for formatting booleans as Yes/No.

# TODO: TimestampMixin to Base?
class Protein(BaseModel):
    __tablename__ = 'protein'

    # TODO: force upper case
    id = Column(String(50), primary_key=True)
    # Insert order column ?
    symbol = Column(String(100))
    long_symbol = Column(Text)
    family = Column(String(100))
    subfamily = Column(String(100))
    description = Column(Text)
    nickname = Column(String(10), unique=True)
    # TODO: FP, RP, ECD

    @property
    def label(self):
        return self.symbol if self.symbol else self.id


class BatchProtein(BaseModel):
    __tablename__ = 'batch_protein'

    order = Column(Integer, nullable=False)

    # TODO: decide how to handle new versions of batches (e.g. 1 new)
    # maybe batch_name -> batch_id, batch_id -> batch_nr
    batch_name = Column(String(50), primary_key=True)
    batch_id = Column(String(50))
    protein_id = Column(String(50), ForeignKey('protein.id'), primary_key=True)

    # TODO: boolean? enum?
    cloned = Column(String(10))
    expression = Column(Float)
    ap_activity = Column(Float)

    protein = relationship(Protein)


class Plate(BaseModel):
    __tablename__ = 'plate'

    id = Column(Integer, primary_key=True)
    info = Column(Text, default='{}')
    imported_on = Column(DateTime)

    bait_batch_id = Column(Integer, nullable=False)
    prey_batch_id = Column(Integer, nullable=False)

    cells = relationship("PlateCell", cascade="all, delete, delete-orphan", backref="plate")

    @property
    def name(self):
        return screen_plate_name(self.id)


class PlateCell(BaseModel):
    __tablename__ = 'plate_cells'

    plate_id = Column(Integer, ForeignKey('plate.id'), primary_key=True)
    row = Column(Integer, nullable=False, primary_key=True)
    column = Column(Integer, nullable=False, primary_key=True)

    bait_id = Column(String(50), ForeignKey('protein.id'), nullable=True)
    prey_id = Column(String(50), ForeignKey('protein.id'), nullable=True)
    is_NC = Column(Boolean, default=False)
    is_PC = Column(Boolean, default=False)

    value = Column(Float)

    bait = relationship(Protein, foreign_keys=[bait_id])
    prey = relationship(Protein, foreign_keys=[prey_id])


