from datetime import datetime

from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import APIRouter, Depends, Request, HTTPException, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import Experiment
from schemas import CreateExperiment
from database.db_depends import get_db
from typing import Annotated

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

router = APIRouter(prefix='/experiments', tags=['Experiments'])

# Получить все эксперименты
@router.get("/")
async def get_experiments(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    experiments = await db.scalars(select(Experiment))
    return templates.TemplateResponse("experiments.html", {"request":request, "experiments":experiments.all()})


@router.get("/create", response_class=HTMLResponse)
async def show_form(request: Request):
    return templates.TemplateResponse("create_experiment.html", {"request": request})


@router.post("/create")
async def create_experiment(
        request: Request,
        name: str = Form(...),
        task: str = Form(...),
        delivered: str = Form(...),
        manufacture: str = Form(...),
        creator: str = Form(...),
        conducted: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    try:
        delivered_dt = datetime.fromisoformat(delivered)
        manufacture_dt = datetime.fromisoformat(manufacture)

        db_experiment = Experiment(
            delivered=delivered_dt,
            name=name,
            task=task,
            manufacture=manufacture_dt,
            creator=creator,
            conducted=conducted
        )

        db.add(db_experiment)
        await db.commit()

        return RedirectResponse("/experiments", status_code=303)

    except Exception as e:
        await db.rollback()
        return templates.TemplateResponse("create_experiment.html",
                                          {"request": request, "error": str(e)},
                                          status_code=400)


@router.get("/{id}")
async def get_on_id(request: Request, id : int,db: Annotated[AsyncSession, Depends(get_db)]):
    experiment = await db.scalar(select(Experiment).where(Experiment.id == id))
    return templates.TemplateResponse("experiment_detail.html", {"request":request, "experiment":experiment})

@router.post("/{id}")
async def update_experiment(request: Request,
                             id: int,
                             comment: str = Form(...),
                             result: str = Form(...),
                             db: AsyncSession = Depends(get_db)):
    try:
        # 1. Найти существующий эксперимент
        db_experiment = await db.scalar(select(Experiment).where(Experiment.id == id))
        if not db_experiment:
            return templates.TemplateResponse(
                "experiment_detail.html",
                {"request": request, "error": "Эксперимент не найден."},
                status_code=404
            )

        # 2. Обновить поля
        db_experiment.comment = comment
        db_experiment.result = result

        # 3. Сохранить изменения
        await db.commit()
        await db.refresh(db_experiment)

        # 4. Редирект обратно
        return RedirectResponse("/experiments", status_code=303)

    except Exception as e:
        await db.rollback()
        return templates.TemplateResponse(
            "experiment_detail.html",
            {"request": request, "error": str(e)},
            status_code=400
        )


