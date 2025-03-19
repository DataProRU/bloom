from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import init_db, database
from routes import users, auth_routes, bot_add, tg_users, main_directory
from routes.directory import payment_types, operations, categories, articles, wallets

app = FastAPI()

app.mount("/templates", StaticFiles(directory="templates"), name="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(auth_routes.router)
app.include_router(users.router)
app.include_router(bot_add.router)
app.include_router(tg_users.router)

app.include_router(payment_types.router)
app.include_router(operations.router)
app.include_router(categories.router)
app.include_router(articles.router)
app.include_router(wallets.router)

app.include_router(main_directory.router)


@app.on_event("startup")
async def startup():
    # При старте приложения создаем таблицы
    await init_db()


@app.on_event("shutdown")
async def shutdown():
    # Отключаемся от базы данных при завершении работы
    await database.disconnect()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
