from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from database.db import Base

class Experiment(Base):
    __tablename__ = "experiments"
    id = Column(Integer, primary_key=True, index=True) # Всегда должен быть
    delivered = Column(DateTime, nullable=False) # Время, когда принесли
    name = Column(String(100), nullable=False) # Название замеса
    task = Column(String(255), nullable=False) # Что нужно сделать
    manufacture = Column(DateTime, nullable=False) # Время, когда приготовили
    result = Column(String, nullable=False, default="В работе") # Выполнена/не выполнена/ в работе задача
    creator = Column(String(100), nullable=False) # Кто сделал
    conducted = Column(String(100), nullable=False) # Кто провел эксперимент
    comment = Column(String(255), nullable=True) # Комментарий к опыту
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True) #связь с тем, кто сделал


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    post = Column(String)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    is_director = Column(Boolean, default=False)
    is_slave = Column(Boolean, default=True)
