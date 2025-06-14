from datetime import datetime

from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from models import Experiment, User, Composition
from database.db_depends import get_db
from typing import Annotated, List

from auth import get_current_user

from sqlalchemy import case

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

router = APIRouter(prefix='/experiments', tags=['Experiments'])

@router.get("/")
async def get_experiments(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    query = select(Experiment).options(selectinload(Experiment.conducted_user)).order_by(Experiment.id.desc())

    if not current_user.is_director:
        query = query.where(Experiment.conducted_user == current_user)

    result = await db.execute(query)
    experiments = result.scalars().all()

    return templates.TemplateResponse("experiments.html", {
        "request": request,
        "experiments": experiments,
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
    elements: List[str] = Form(...),
    percentages: List[float] = Form(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        delivered_dt = datetime.fromisoformat(delivered)
        manufacture_dt = datetime.fromisoformat(manufacture)

        # Получаем пользователей
        creator_result = await db.execute(select(User).where(User.id == creator_id))
        creator = creator_result.scalar_one_or_none()

        conducted_result = await db.execute(select(User).where(User.id == conducted_id))
        conducted = conducted_result.scalar_one_or_none()

        if not creator or not conducted:
            raise ValueError("Неверный ответственный или исполнитель")

        # Создание эксперимента
        db_experiment = Experiment(
            delivered=delivered_dt,
            name=name,
            task=task,
            manufacture=manufacture_dt,
            creator=creator.name,
            conducted_id=conducted_id
        )

        db.add(db_experiment)
        await db.flush()  # Получаем ID эксперимента до commit

        # Добавление состава
        for element, percentage in zip(elements, percentages):
            composition = Composition(
                experiment_id=db_experiment.id,
                element=element.strip(),
                percentage=percentage
            )
            db.add(composition)

        await db.commit()
        return RedirectResponse("/experiments", status_code=303)

    except Exception as e:
        result = await db.execute(select(User).where(User.is_slave == True, User.is_active == True))
        slaves = result.scalars().all()
        return templates.TemplateResponse("create_experiment.html",
                                          {"request": request, "error": str(e), "slaves": slaves},
                                          status_code=400)




@router.get("/stats", response_class=HTMLResponse)
async def experiments_stats(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    if not current_user.is_director:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    # Общая статистика
    total_exp = await db.scalar(select(func.count(Experiment.id)))
    success_exp = await db.scalar(select(func.count()).where(Experiment.result == "Успешно"))
    fail_exp = await db.scalar(select(func.count()).where(Experiment.result == "Неудача"))
    in_progress = await db.scalar(select(func.count()).where(Experiment.result == "В работе"))

    success_percent = round((success_exp or 0) / total_exp * 100, 2) if total_exp else 0

    # Группировка по исполнителю
    stmt = select(
        User.name,
        func.count(Experiment.id).label("total"),
        func.sum(case((Experiment.result == "Успешно", 1), else_=0)).label("success_count"),
        func.sum(case((Experiment.result == "Неудача", 1), else_=0)).label("fail_count")
    ).join(Experiment, Experiment.conducted_id == User.id).group_by(User.name)

    result = await db.execute(stmt)
    per_user = result.all()
    user_stats = [
        {
            "name": row[0],
            "total": row[1],
            "success": row[2],
            "fail": row[3],
            "success_percent": round(row[2] / row[1] * 100, 2) if row[1] else 0
        }
        for row in per_user
    ]

    experiments_result = await db.execute(
        select(Experiment).order_by(Experiment.id.desc())
    )
    experiments = experiments_result.scalars().all()

    # Сортируем по проценту успешности
    user_stats.sort(key=lambda x: x["success_percent"], reverse=True)

    return templates.TemplateResponse("experiment_stats.html", {
        "request": request,
        "total": total_exp,
        "success": success_exp,
        "fail": fail_exp,
        "in_progress": in_progress,
        "success_percent": success_percent,
        "user_stats": user_stats,
        "experiments": experiments
    })



@router.get("/compare")
async def compare_experiments(request: Request, id1: int, id2: int, db: AsyncSession = Depends(get_db)):
    # Получаем данные для первого эксперимента
    exp1 = await db.execute(
        select(Experiment)
        .options(selectinload(Experiment.conducted_user), selectinload(Experiment.compositions))
        .where(Experiment.id == id1)
    )
    exp1 = exp1.scalar_one_or_none()

    # Получаем данные для второго эксперимента
    exp2 = await db.execute(
        select(Experiment)
        .options(selectinload(Experiment.conducted_user), selectinload(Experiment.compositions))
        .where(Experiment.id == id2)
    )
    exp2 = exp2.scalar_one_or_none()

    if not exp1 or not exp2:
        return HTMLResponse(content="Один из экспериментов не найден", status_code=404)

    return templates.TemplateResponse("compare_experiments.html", {
        "request": request,
        "exp1": exp1,
        "exp2": exp2
    })




@router.get("/{id}")
async def get_on_id(request: Request, id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    experiment = await db.scalar(
        select(Experiment)
        .where(Experiment.id == id)
        .options(selectinload(Experiment.compositions))  # загрузка состава
    )
    if not experiment:
        return templates.TemplateResponse(
            "experiment_detail.html",
            {"request": request, "error": "Эксперимент не найден."},
            status_code=404
        )
    return templates.TemplateResponse(
        "experiment_detail.html",
        {"request": request, "experiment": experiment}
    )

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
