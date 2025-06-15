import uvicorn
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from exp import router as ro_exp
from auth import router as ro_au, verify_auth
from admin_panel import router as admin_panel
from user_profile import router as user_profile
from analytics import router as analytics
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR

templates = Jinja2Templates(directory="templates")
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == HTTP_401_UNAUTHORIZED:
        return templates.TemplateResponse("errors/401.html", {"request": request}, status_code=401)
    if exc.status_code == HTTP_404_NOT_FOUND:
        return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)
    return templates.TemplateResponse("errors/500.html", {"request": request}, status_code=exc.status_code)

@app.exception_handler(Exception)
async def custom_internal_error_handler(request: Request, exc: Exception):
    return templates.TemplateResponse("errors/500.html", {"request": request}, status_code=500)


@app.get("/", tags=["Главное Меню"])
async def welcome(request: Request, error: str = None):
    error_message = "Неверный логин или пароль, попробуйте снова" if error == "invalid_credentials" else None
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error_message": error_message})

app.include_router(ro_exp, dependencies=[Depends(verify_auth)])
app.include_router(ro_au)
app.include_router(user_profile, dependencies=[Depends(verify_auth)])
app.include_router(admin_panel, dependencies=[Depends(verify_auth)])
app.include_router(analytics, dependencies=[Depends(verify_auth)])

if __name__ == '__main__':
    uvicorn.run("main:app", reload=True, port=5220)
