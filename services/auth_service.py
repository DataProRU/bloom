from fastapi import Request, HTTPException, status, Response
from fastapi.responses import RedirectResponse
from services.auth import verify_password, get_password_hash, create_access_token
from schemas import UserCreate
import databases
from urllib.parse import urlparse
import json

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
    try:
        # Получаем original_url
        original_url = request.cookies.get("original_url")
        if not original_url:
            referer = request.headers.get('referer')
            original_url = urlparse(referer).path if referer else "/welcome"

        # Проверка пользователя
        query = "SELECT * FROM web_users WHERE username = :username"
        user = await db.fetch_one(query=query, values={"username": form_data.username})

        if user and verify_password(form_data.password, user["password"]):
            token = create_access_token({"sub": form_data.username, "role": user["role"]})
            
            # Создаем response с обновленными cookies
            response = RedirectResponse(
                url=original_url,
                status_code=status.HTTP_303_SEE_OTHER
            )
            
            # Устанавливаем cookies
            response.set_cookie(
                key="token",
                value=token,
                httponly=True,
                secure=True,
                samesite="lax"
            )
            
            # Сохраняем original_url для PWA
            response.set_cookie(
                key="pwa_original_url",
                value=original_url,
                max_age=3600,
                secure=True,
                samesite="lax"
            )
            
            return response

        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "error": "Invalid credentials"}
        )

    except Exception as e:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": f"Login error: {str(e)}"}
        )
