from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy.model import Model as FlaskModel

from sqlalchemy import func, Column, Integer, DateTime, String, Float, ForeignKey
from sqlalchemy.orm import relationship


class BaseModel(FlaskModel):
    """
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
        'mysql_collate': 'utf8_general_ci'
    }
    """
    id = Column(Integer, primary_key=True)
    node_id = Column(Integer, nullable=False)
    node_entity_id = Column(Integer)
    created_at = Column(DateTime, default=func.now())

db = SQLAlchemy(model_class=BaseModel)

class Plant(db.Model):
    __tablename__ = 'plants'

    name = Column(String)

    def __repr__(self):
        return f'{self.name} ({self.id})'

class MMType(db.Model):
    __tablename__ = 'types'

    name = Column(String)

    def __repr__(self):
        return f'{self.name} ({self.id})'


class Point(db.Model):
    __tablename__ = 'points'

    value = Column(Float)
    time = Column(DateTime, server_default=func.now())
    plant_id = Column(Integer, ForeignKey('plants.id'))
    type_id = Column(Integer, ForeignKey('types.id'))

    plant = relationship("Plant", back_populates="points")
    mm_type = relationship("MMType", back_populates="points")

    def __str__(self):
        return f'[Point {self.time} {self.value}]'

Plant.points = relationship("Point", back_populates="plant")
MMType.points = relationship("Point", back_populates="mm_type")

