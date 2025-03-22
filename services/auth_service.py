from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
from services.auth import verify_password, get_password_hash, create_access_token
from schemas import UserCreate
import databases


async def register_user(
        request: Request,
        username: str,
        password: str,
        role: str,
        db: databases.Database,
        templates,
):
    user = UserCreate(username=username, password=password, role=role)
    try:
        query = "INSERT INTO web_users (username, password, role) VALUES (:username, :password, :role)"
        values = {
            "username": user.username,
            "password": get_password_hash(user.password),
            "role": user.role,
        }
        await db.execute(query=query, values=values)
        return RedirectResponse("/users", status_code=303)
    except Exception as e:
        return templates.TemplateResponse(
            "register.html", {"request": request, "error": str(e)}
        )


async def login_user(request: Request, form_data, db: databases.Database, templates):
    try:
        # Выполнение запроса к базе данных
        query = "SELECT * FROM web_users WHERE username = :username"
        user = await db.fetch_one(query=query, values={"username": form_data.username})

        # Проверка, найден ли пользователь и совпадает ли пароль
        if user and verify_password(form_data.password, user["password"]):
            # Генерация токена и установка куки
            token = create_access_token(
                {"sub": form_data.username, "role": user["role"]}
            )
            response = RedirectResponse(
                url="/tg_bot_add?username=" + user.username, status_code=status.HTTP_303_SEE_OTHER
            )
            response.set_cookie(key="token", value=token, httponly=True)
            return response

        # Ошибка авторизации
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Invalid username or password"}
        )

    except Exception as e:
        # Логирование ошибки для отладки (по желанию)
        print(f"Error logging in: {e}")
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "An error occurred"}
        )
