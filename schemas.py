from pydantic import BaseModel
from datetime import datetime

class CreateExperiment(BaseModel):
    delivered : datetime
    name : str
    task : str
    manufacture : datetime
    result : str = "В работе"
    creator : str
    conducted : str
    comment: str


class CreateUser(BaseModel):
    name: str
    post: str
    password: str