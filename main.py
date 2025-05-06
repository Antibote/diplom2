import uvicorn
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from exp import router as ro_exp
from auth import router as ro_au, verify_auth
from admin_panel import router as admin_panel
from user_profile import router as user_profile
from fastapi.templating import Jinja2Templates


templates = Jinja2Templates(directory="templates")

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", tags=["Главное Меню"])
async def welcome(request: Request, error: str = None):
    error_message = "Неверный логин или пароль, попробуйте снова" if error == "invalid_credentials" else None
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error_message": error_message}
    )

app.include_router(ro_exp, dependencies=[Depends(verify_auth)])
app.include_router(ro_au)

app.include_router(user_profile, dependencies=[Depends(verify_auth)])
app.include_router(admin_panel, dependencies=[Depends(verify_auth)])

if __name__ == '__main__':
    uvicorn.run("main:app", reload=True, port=5220)
