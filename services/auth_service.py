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
    try:
        # Check for stored original URL first
        original_url = request.cookies.get("original_url")

        # If no stored URL, check referer as fallback
        if not original_url:
            referer_url = request.headers.get('referer')
            if referer_url:
                parsed_url = urlparse(referer_url)
                original_url = f"{parsed_url.path}?{parsed_url.query}" if parsed_url.query else parsed_url.path

        # Database query
        query = "SELECT * FROM web_users WHERE username = :username"
        user = await db.fetch_one(query=query, values={"username": form_data.username})

        if user and verify_password(form_data.password, user["password"]):
            token = create_access_token({"sub": form_data.username, "role": user["role"]})

            # Parse the original URL to extract path and query parameters
            parsed_original_url = urlparse(original_url)
            original_path = parsed_original_url.path
            original_query_params = parse_qs(parsed_original_url.query)

            # Determine redirect URL
            if original_path == "/tg_bot_add" and "username" in original_query_params:
                # Reconstruct the full URL with query parameters
                redirect_url = f"{original_path}?{'&'.join([f'{k}={v[0]}' for k, v in original_query_params.items()])}"
            else:
                redirect_url = "/welcome"

            response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
            response.set_cookie(key="token", value=token, httponly=True)
            response.delete_cookie("original_url")  # Clean up the stored URL
            return response

        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Invalid username or password"}
        )

    except Exception as e:
        print(f"Error logging in: {e}")
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "An error occurred"}
        )