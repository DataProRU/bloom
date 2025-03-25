from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
from services.auth import verify_password, get_password_hash, create_access_token
from schemas import UserCreate
import databases
from urllib.parse import urlparse

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


from urllib.parse import urlparse, parse_qs

async def login_user(
    request: Request,
    form_data,
    db: databases.Database,
    templates,
):
    """
    Обрабатывает аутентификацию пользователя с поддержкой:
    - Стандартного входа
    - PWA (сохранение исходного URL для iOS)
    - Обработки защищенных маршрутов (/tg_bot_add)
    """
    try:
        # 1. Получаем исходный URL из (в порядке приоритета):
        #    - Куки original_url
        #    - Referer заголовок
        #    - По умолчанию "/welcome"
        original_url = (
            request.cookies.get("original_url") or
            request.headers.get('referer') or
            "/welcome"
        )

        # Очищаем URL от потенциально опасных значений
        if "/login" in original_url:
            original_url = "/welcome"

        # 2. Проверяем учетные данные
        user = await db.fetch_one(
            "SELECT * FROM web_users WHERE username = :username",
            {"username": form_data.username}
        )

        if not user or not verify_password(form_data.password, user["password"]):
            return templates.TemplateResponse(
                "login.html",
                {
                    "request": request,
                    "error": "Неверный логин или пароль",
                    "original_url": original_url,  # Для PWA
                },
                status_code=status.HTTP_401_UNAUTHORIZED
            )

        # 3. Создаем JWT токен
        token = create_access_token(
            data={"sub": user["username"], "role": user["role"]}
        )

        # 4. Определяем URL для редиректа
        if "/tg_bot_add" in original_url:
            # Парсим параметры из оригинального URL
            parsed_url = urlparse(original_url)
            query_params = parse_qs(parsed_url.query)
            
            # Собираем новый URL с параметрами
            redirect_url = parsed_url.path
            if query_params:
                redirect_url += "?" + "&".join(
                    f"{k}={v[0]}" for k, v in query_params.items()
                )
        else:
            redirect_url = "/welcome"

        # 5. Формируем ответ
        response = RedirectResponse(
            url=redirect_url,
            status_code=status.HTTP_303_SEE_OTHER
        )

        # Устанавливаем токен в куки
        response.set_cookie(
            key="token",
            value=token,
            httponly=True,
            secure=True,  # Для HTTPS
            samesite="Lax"
        )

        # Удаляем временную куку (если была)
        response.delete_cookie("original_url")

        # 6. Добавляем PWA-совместимые заголовки
        response.headers["Cache-Control"] = "no-store, max-age=0"
        
        return response

    except Exception as e:
        # Логирование ошибки (на практике используйте logging)
        print(f"Ошибка входа: {str(e)}")
        
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Внутренняя ошибка сервера",
                "original_url": request.url.path,
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )