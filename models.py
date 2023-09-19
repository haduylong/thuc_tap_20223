from sqlalchemy import Boolean, Column, Integer, String, ForeignKey
from database import Base
from sqlalchemy.orm import relationship

class Device(Base):
    __tablename__ = 'devices'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True) # name of device
    ipaddress = Column(String(255), unique=True)
    port = Column(Integer)
    username = Column(String(255), default='admin')
    password = Column(String(255), default='songnam@123')

    subnet = Column(String(255))
    macaddress = Column(String(255), unique=True)
    datelimit = Column(Integer)
    timelimit = Column(Integer)
    records = relationship('Record', back_populates='device')

class Record(Base):
    __tablename__ = 'records'

    id = Column(Integer, primary_key=True, index=True)
    timestart = Column(String(255))
    timeend = Column(String(255))
    macaddress = Column(String(255), ForeignKey('devices.macaddress'))
    storage = Column(String(255))

    device = relationship('Device', back_populates='records')
