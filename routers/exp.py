from datetime import datetime

from fastapi import APIRouter, Depends, status, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from models import Experiment
from schemas import CreateExperiment
from database.db_depends import get_db
from typing import Annotated

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")



router = APIRouter(prefix='/experiments', tags=['Experiments'])

# Получить все эксперименты
@router.get("/experiments")
async def get_experiments(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    experiments = await db.scalars(select(Experiment))
    return templates.TemplateResponse("experiments.html", {"request":request, "experiments":experiments.all()})

# Создать эксперимент
@router.post("/experiments", status_code=status.HTTP_201_CREATED)
async def create_experiments(
        db: Annotated[AsyncSession, Depends(get_db)],
        delivered: datetime = Form(...),
        name: str = Form(...),
        task: str = Form(...),
        manufacture: datetime = Form(...),
        result: bool = Form(...),
        creator: str = Form(...),
        conducted: str = Form(...),
):
    creates = CreateExperiment(
        delivered=delivered,
        name=name,
        task=task,
        manufacture=manufacture,
        result=result,
        creator=creator,
        conducted=conducted,
    )

    await db.execute(insert(Experiment).values(**creates.model_dump()))
    await db.commit()

    return {"transaction": "Successful"}
