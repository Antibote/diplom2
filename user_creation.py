from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from passlib.context import CryptContext
from datetime import datetime
from database.db_depends import get_db
from models import User

router = APIRouter(tags=["User Management"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/users/", status_code=201)
async def create_user(
        name: str,
        post: str,
        password: str,
        is_admin: bool = False,
        is_director: bool = False,
        is_slave: bool = True,
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

    return {
        "id": new_user.id,
        "name": new_user.name,
        "post": new_user.post,
        "is_admin": new_user.is_admin,
        "is_director": new_user.is_director,
        "created_at": datetime.utcnow()
    }