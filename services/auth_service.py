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
        # Получаем URL, с которого пользователь пришел
        previous_url = request.cookies.get("referer")

        # Запрос к базе данных
        query = "SELECT * FROM web_users WHERE username = :username"
        user = await db.fetch_one(query=query, values={"username": form_data.username})

        # Проверка логина и пароля
        if user and verify_password(form_data.password, user["password"]):
            # Генерация токена
            token = create_access_token({"sub": form_data.username, "role": user["role"]})

            # Определяем, куда редиректить
            if previous_url and previous_url.startswith("/tg_bot_add"):
                redirect_url = previous_url  # Возвращаем на предыдущую страницу
            else:
                redirect_url = "/welcome"  # Если другая страница, то на welcome

            # Создаем редирект и ставим куки
            response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
            response.set_cookie(key="token", value=token, httponly=True)
            return response

        # Ошибка авторизации
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Invalid username or password"}
        )

    except Exception as e:
        print(f"Error logging in: {e}")
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "An error occurred"}
        )
