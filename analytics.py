from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import selectinload
from fastapi.responses import HTMLResponse, JSONResponse
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



COMPOSITION_RULES = {
    'X': 40.0,
    'Y': 20.0,
}

@router.get("/compare", response_class=HTMLResponse)
async def compare_experiments_html(request: Request, id1: int, id2: int,
                                   db: AsyncSession = Depends(get_db),
                                   current_user=Depends(get_current_user)):
    return templates.TemplateResponse(
        "compare_experiments.html",
        {"request": request, "id1": id1, "id2": id2}
    )
@router.get("/compare/data", name="compare_experiments_data")
async def compare_experiments_data(id1: int, id2: int,
                                   db: AsyncSession = Depends(get_db),
                                   current_user=Depends(get_current_user)):
    # Получаем оба эксперимента с составом и юзером
    stmt = select(Experiment).options(
        selectinload(Experiment.compositions),
        selectinload(Experiment.conducted_user)
    ).where(Experiment.id.in_([id1, id2]))
    result = await db.execute(stmt)
    exps = result.scalars().all()
    if len(exps) != 2:
        raise HTTPException(404, "Один из экспериментов не найден")
    exp1, exp2 = sorted(exps, key=lambda e: e.id)

    # Подготовка состава для графиков
    def comp_dict(exp):
        return {c.element: c.percentage for c in exp.compositions}
    comp1, comp2 = comp_dict(exp1), comp_dict(exp2)
    all_elements = sorted(set(comp1) | set(comp2))
    comp_data = {
        "labels": all_elements,
        "exp1": [comp1.get(el, 0) for el in all_elements],
        "exp2": [comp2.get(el, 0) for el in all_elements],
    }

    # Анализ состава: предупреждения по правилам
    comp_warnings = []
    for elem, threshold in COMPOSITION_RULES.items():
        for idx, comp in enumerate((comp1, comp2), start=1):
            val = comp.get(elem, 0)
            if val > threshold:
                comp_warnings.append(
                    f"Эксперимент {idx}: элемент {elem} = {val:.1f}% (> {threshold}%) может влиять на неудачу."
                )

    # Сравнение состава: различия и совпадения
    comp_diffs = []
    for el in all_elements:
        v1, v2 = comp1.get(el, 0), comp2.get(el, 0)
        if v1 != v2:
            delta = v2 - v1
            direction = 'увеличился' if delta > 0 else 'уменьшился'
            comp_diffs.append(
                f"{el}: в 2-м эксперименте {direction} на {abs(delta):.1f} (из {v1:.1f} в {v2:.1f})."
            )
    # Совпадающие элементы
    comp_same = [el for el in all_elements if comp1.get(el, 0) == comp2.get(el, 0)]

    # Сравнение исполнителя и создателя
    human_notes = []
    if exp1.conducted_user and exp2.conducted_user and exp1.conducted_user.id != exp2.conducted_user.id:
        human_notes.append(
            f"Разные исполнители: {exp1.conducted_user.name} и {exp2.conducted_user.name}."
        )
    if exp1.creator != exp2.creator:
        human_notes.append(f"Разные создатели: {exp1.creator} и {exp2.creator}.")

    # Итоговый JSON
    return JSONResponse({
        "comp_data": comp_data,
        "total": {"exp1": exp1.id, "exp2": exp2.id},
        "human": human_notes,
        "composition_warnings": comp_warnings,
        "composition_differences": comp_diffs,
        "composition_same": comp_same,
    })
