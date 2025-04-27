import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from exp import router as ro_exp
from auth import router as ro_au
from user_creation import router as ro_uc
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", tags=["Главное Меню"])
async def welcome(request:Request):
    return templates.TemplateResponse("login.html", {"request":request})


app.include_router(ro_exp)
app.include_router(ro_au)
app.include_router(ro_uc)

if __name__ == '__main__':
    uvicorn.run(app, reload=True)