from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from database.db import Base
from sqlalchemy.orm import relationship


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True, index=True)
    delivered = Column(DateTime, nullable=False)
    name = Column(String(100), nullable=False)
    task = Column(String(255), nullable=False)
    manufacture = Column(DateTime, nullable=False)
    result = Column(String, nullable=False, default="В работе")
    creator = Column(String(100), nullable=False)

    # Новый внешний ключ
    conducted_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    conducted_user = relationship("User", foreign_keys=[conducted_id])

    comment = Column(String(255), nullable=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)


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

    # Отношение: эксперименты, которые пользователь провёл
    experiments_conducted = relationship("Experiment", back_populates="conducted_user", foreign_keys="Experiment.user_id")

