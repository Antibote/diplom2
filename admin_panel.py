from fastapi import Request, Form
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from passlib.context import CryptContext
from fastapi.responses import RedirectResponse, HTMLResponse
from database.db_depends import get_db
from models import User
from auth import get_current_user

from fastapi.templating import Jinja2Templates

async def require_admin(user: User = Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admins only")
    return user


templates = Jinja2Templates(directory="templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
router = APIRouter(prefix='/admin-panel',
                   tags=['Admin-panel'],
                   dependencies=[Depends(require_admin)])


@router.get("/")
async def admin_panel(
    request: Request,
    current_user: User = Depends(require_admin)
):
    return templates.TemplateResponse("admin_panel.html", {
        "request": request,
        "user": current_user
    })


@router.get("/create-user", response_class=HTMLResponse)
async def show_create_user_form(request: Request, db: AsyncSession = Depends(get_db)):
    return templates.TemplateResponse(
        "create_user.html",
        {"request": request}
    )


@router.post("/create-user", status_code=201)
async def create_user(
        request: Request,
        name: str = Form(...),  # Используем Form() для данных формы
        post: str = Form(...),
        password: str = Form(...),
        is_admin: bool = Form(False),
        is_director: bool = Form(False),
        is_slave: bool = Form(True),
        db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.name == name))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Username already exists")

    hashed_password = pwd_context.hash(password)
    new_user = User(
        name=name,
        post=post,
        hashed_password=hashed_password,
        is_admin=is_admin,
        is_director=is_director,
        is_slave=is_slave,
        is_active=True
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return RedirectResponse(url="/admin-panel", status_code=303)


@router.get("/delete-user")
async def manage_users(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    result = await db.execute(select(User))
    users = result.scalars().all()
    active_users = [u for u in users if u.is_active]
    inactive_users = [u for u in users if not u.is_active]

    return templates.TemplateResponse("manage_users.html", {
        "request": request,
        "active_users": active_users,
        "inactive_users": inactive_users,
        "user": current_user
    })


@router.post("/toggle-user-status")
async def toggle_user_status(
    user_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = not user.is_active
    await db.commit()

    return RedirectResponse(url="/admin-panel/delete-user", status_code=303)