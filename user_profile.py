from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from database.db_depends import get_db  # Предполагается, что у тебя уже есть get_db
from models import User
from auth import get_current_user  # Зависимость для получения текущего пользователя

router = APIRouter(prefix='/user_profile', tags=['User Profile'])
templates = Jinja2Templates(directory="templates")


@router.get("/")
async def user_profile(request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/experiments", status_code=302)

    return templates.TemplateResponse("user.html", {
        "request": request,
        "user": current_user
    })
