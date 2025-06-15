from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import selectinload
from fastapi.responses import HTMLResponse
from database.db_depends import get_db
from models import Experiment, User
from auth import get_current_user
from typing import Annotated

templates = Jinja2Templates(directory="templates")
router = APIRouter(prefix="/analytics", tags=["Analytics"])

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from sqlalchemy.orm import selectinload
from fastapi.templating import Jinja2Templates

from database.db_depends import get_db
from models import Experiment, User
from auth import get_current_user

templates = Jinja2Templates(directory="templates")
router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/", response_class=HTMLResponse, name="experiments_stats")
async def experiments_stats(
    request: Request,
    start: str | None = Query(None, description="Дата начала в ISO формате"),
    end:   str | None = Query(None, description="Дата конца в ISO формате"),
    db:    AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not current_user.is_director:
        raise HTTPException(403, "Доступ запрещён")

    # 1) Расчёт диапазона
    utc_now = datetime.utcnow()
    start_dt = datetime.fromisoformat(start) if start else utc_now - timedelta(days=30)
    end_dt   = datetime.fromisoformat(end) + timedelta(hours=23,minutes=59,seconds=59) if end else utc_now

    default_start = start_dt.date().isoformat()
    default_end   = end_dt.date().isoformat()

    # 2) Общая статистика за период
    total_exp = await db.scalar(
        select(func.count(Experiment.id))
        .where(Experiment.manufacture.between(start_dt, end_dt))
    )
    success_exp = await db.scalar(
        select(func.count())
        .where(
            Experiment.result == "Успешно",
            Experiment.manufacture.between(start_dt, end_dt)
        )
    )
    fail_exp = await db.scalar(
        select(func.count())
        .where(
            Experiment.result == "Неудача",
            Experiment.manufacture.between(start_dt, end_dt)
        )
    )
    in_progress = await db.scalar(
        select(func.count())
        .where(
            Experiment.result == "В работе",
            Experiment.manufacture.between(start_dt, end_dt)
        )
    )
    success_percent = round((success_exp or 0) / (total_exp or 1) * 100, 2)

    # 3) По‑пользователю статистика за период
    per_user_stmt = (
        select(
            User.name,
            func.count(Experiment.id).label("total"),
            func.sum(case((Experiment.result == "Успешно", 1), else_=0)).label("success_count"),
            func.sum(case((Experiment.result == "Неудача", 1), else_=0)).label("fail_count"),
            func.sum(case((Experiment.result == "В работе", 1), else_=0)).label("in_progress_count")
        )
        .join(Experiment, Experiment.conducted_id == User.id)
        .where(Experiment.manufacture.between(start_dt, end_dt))
        .group_by(User.name)
    )
    per_user = (await db.execute(per_user_stmt)).all()
    user_stats = [
        {
            "name": row[0],
            "total": row[1],
            "success": row[2],
            "fail": row[3],
            "in_progress": row[4],
            "success_percent": round(row[2] / row[1] * 100, 2) if row[1] else 0
        }
        for row in per_user
    ]
    user_stats.sort(key=lambda x: x["success_percent"], reverse=True)

    # 4) Все эксперименты для сравнения
    exps = await db.execute(select(Experiment).order_by(Experiment.id.desc()))
    experiments = exps.scalars().all()

    return templates.TemplateResponse(
        "experiment_stats.html",
        {
            "request": request,
            "current_user": current_user,
            "total": total_exp,
            "success": success_exp,
            "fail": fail_exp,
            "in_progress": in_progress,
            "success_percent": success_percent,
            "user_stats": user_stats,
            "experiments": experiments,
            "default_start": default_start,
            "default_end": default_end,
        },
    )

@router.get("/employee", name="employee_analytics")
async def employee_analytics(
    request: Request,
    employee_id: int = Query(..., alias="employee_id"),
    start: str | None = Query(None),
    end: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not current_user.is_director:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    # 1) Диапазон дат
    utc_now = datetime.utcnow()
    if start:
        start_dt = datetime.fromisoformat(start)
    else:
        start_dt = utc_now - timedelta(days=30)
    if end:
        # включаем весь день
        end_dt = datetime.fromisoformat(end) + timedelta(hours=23, minutes=59, seconds=59)
    else:
        end_dt = utc_now

    # 2) Считаем успешные и неудачные
    res = await db.execute(
        select(
            func.coalesce(func.sum(case((Experiment.result == "Успешно", 1), else_=0)), 0),
            func.coalesce(func.sum(case((Experiment.result == "Неудача", 1), else_=0)), 0),
        ).where(
            Experiment.conducted_id == employee_id,
            Experiment.manufacture.between(start_dt, end_dt),
        )
    )
    success_count, failure_count = res.one()

    # 3) Считаем «В работе»
    in_progress_count = await db.scalar(
        select(
            func.coalesce(func.sum(case((Experiment.result == "В работе", 1), else_=0)), 0)
        ).where(
            Experiment.conducted_id == employee_id,
            Experiment.manufacture.between(start_dt, end_dt),
        )
    )

    # 4) Процент успешности
    total = success_count + failure_count + in_progress_count
    success_rate = round(success_count / total * 100, 1) if total else 0

    # 5) Список сотрудников для селектора
    users = (await db.execute(
        select(User).where(User.is_slave == True, User.is_active == True)
    )).scalars().all()

    return templates.TemplateResponse(
        "employee_analytics.html",
        {
            "request": request,
            "current_user": current_user,
            "employees": users,
            "selected_id": employee_id,
            "start": start_dt.date().isoformat(),
            "end": end_dt.date().isoformat(),
            "success_count": success_count,
            "failure_count": failure_count,
            "in_progress_count": in_progress_count,
            "success_rate": success_rate,
        },
    )


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

