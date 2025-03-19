from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordRequestForm
import databases
from services.auth_service import login_user, register_user
from dependencies import get_authenticated_user, get_current_user, get_token_from_cookie
from database import get_db

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/register", response_class=HTMLResponse)
async def get_register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register")
async def post_register(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        role: str = Form(),
        db: databases.Database = Depends(get_db),
):
    await register_user(request, username, password, role, db, templates)
    return RedirectResponse(url="/users", status_code=303)


@router.get("/login", response_class=HTMLResponse)
async def get_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login", response_class=HTMLResponse)
async def login(
        request: Request,
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: databases.Database = Depends(get_db),
):
    return await login_user(request, form_data, db, templates)


@router.get("/welcome", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def welcome(request: Request):
    token = get_token_from_cookie(request)
    if isinstance(token, RedirectResponse):
        return token

    payload = get_current_user(token)
    if isinstance(payload, RedirectResponse):
        return payload

    # Извлекаем информацию о пользователе
    username = payload.get("sub")
    role = payload.get("role")

    # Возвращаем HTML-шаблон с данными пользователя
    return templates.TemplateResponse(
        "welcome.html", {"request": request, "username": username, "role": role}
    )


@router.get("/confirm", response_class=HTMLResponse)
async def confirm(request: Request, user: dict = Depends(get_authenticated_user), ):
    if isinstance(user, RedirectResponse):
        return user  # Если пользователь не аутентифицирован

    return templates.TemplateResponse(
        "confirm.html", {"request": request}
    )


@router.get("/access", response_class=HTMLResponse)
async def access(request: Request):
    token = get_token_from_cookie(request)
    if isinstance(token, RedirectResponse):
        return token
    payload = get_current_user(token)
    if isinstance(payload, RedirectResponse):
        return payload
    username = payload.get("sub")
    role = payload.get("role")
    return templates.TemplateResponse(
        "access.html", {"request": request, "username": username, "role": role}
    )
