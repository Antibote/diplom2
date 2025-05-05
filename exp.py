from datetime import datetime

from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import APIRouter, Depends, Request, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import Experiment, User
from database.db_depends import get_db
from typing import Annotated

from auth import get_current_user

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

router = APIRouter(prefix='/experiments', tags=['Experiments'])

@router.get("/")
async def get_experiments(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    experiments = await db.scalars(select(Experiment))
    return templates.TemplateResponse("experiments.html", {
        "request": request,
        "experiments": experiments.all(),
        "current_user": current_user
    })


@router.get("/create", response_class=HTMLResponse)
async def show_form(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.is_slave == True, User.is_active == True))
    slaves = result.scalars().all()
    return templates.TemplateResponse("create_experiment.html", {
        "request": request,
        "slaves": slaves
    })


@router.post("/create")
async def create_experiment(
        request: Request,
        name: str = Form(...),
        task: str = Form(...),
        delivered: str = Form(...),
        manufacture: str = Form(...),
        creator_id: int = Form(...),
        conducted_id: int = Form(...),
        db: AsyncSession = Depends(get_db)
):
    try:
        delivered_dt = datetime.fromisoformat(delivered)
        manufacture_dt = datetime.fromisoformat(manufacture)

        # Получаем пользователей по id
        creator_result = await db.execute(select(User).where(User.id == creator_id))
        creator = creator_result.scalar_one_or_none()

        conducted_result = await db.execute(select(User).where(User.id == conducted_id))
        conducted = conducted_result.scalar_one_or_none()

        if not creator or not conducted:
            raise ValueError("Неверный ответственный или исполнитель")

        db_experiment = Experiment(
            delivered=delivered_dt,
            name=name,
            task=task,
            manufacture=manufacture_dt,
            creator=creator.name,
            conducted=conducted.name
        )

        db.add(db_experiment)
        await db.commit()

        return RedirectResponse("/experiments", status_code=303)


    except Exception as e:
        result = await db.execute(select(User).where(User.is_slave == True))
        slaves = result.scalars().all()
        return templates.TemplateResponse("create_experiment.html",
                                          {"request": request, "error": str(e), "slaves": slaves}, status_code=400)

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


