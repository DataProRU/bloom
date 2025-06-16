import logging

from database import Operations, get_db
from dependencies import get_token_from_cookie, get_current_user
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
templates = Jinja2Templates(directory="templates/directory/")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@router.get("/operations/")
async def get_operations(request: Request, db: AsyncSession = Depends(get_db)):
    token = get_token_from_cookie(request)
    if isinstance(token, RedirectResponse):
        return token

    payload = get_current_user(token)
    if isinstance(payload, RedirectResponse):
        return payload

    role = payload.get("role")
    if role != "admin":
        return templates.TemplateResponse("not_access.html", {"request": request})

    operations = await db.fetch_all(Operations.__table__.select())
    return templates.TemplateResponse("operations.html", {"request": request, "operations": operations})


@router.delete("/operations/{id}/")
async def delete_operations(
        id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
):
    token = get_token_from_cookie(request)
    if isinstance(token, RedirectResponse):
        return token

    payload = get_current_user(token)
    if isinstance(payload, RedirectResponse):
        return payload

    role = payload.get("role")
    if role != "admin":
        return JSONResponse({"detail": "Access denied"}, status_code=403)

    # Удаляем пользователя
    query = Operations.__table__.delete().where(Operations.id == id)
    result = await db.execute(query)

    if result:
        return JSONResponse({"detail": "Operation deleted successfully"})
    return JSONResponse({"detail": "Operation not found"}, status_code=404)


@router.post("/operations/{id}/edit/")
async def update_operations(
        request: Request,
        id: int,
        name: str = Form(...),
        db: AsyncSession = Depends(get_db),
):
    token = get_token_from_cookie(request)
    if isinstance(token, RedirectResponse):
        return token

    payload = get_current_user(token)
    if isinstance(payload, RedirectResponse):
        return payload

    logger.info("checking")

    role = payload.get("role")
    if role != "admin":
        return templates.TemplateResponse("not_access.html", {"request": request})

    try:
        # Проверяем, существует способ оплаты
        operation = await db.fetch_one(Operations.__table__.select().where(Operations.id == id))
        if not operation:
            return templates.TemplateResponse("not_found.html", {"request": request})

        # Обновляем способ оплаты
        query = (
            update(Operations.__table__)
            .where(Operations.id == id)
            .values(name=name)
        )
        await db.execute(query)
    except Exception as e:
        logger.error(f"Error updating operations: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return RedirectResponse(url="/operations/", status_code=303)


@router.post("/operations/add/")
async def add_operation(
        request: Request,
        name: str = Form(...),
        db: AsyncSession = Depends(get_db),
):
    token = get_token_from_cookie(request)
    if isinstance(token, RedirectResponse):
        return token

    payload = get_current_user(token)
    if isinstance(payload, RedirectResponse):
        return payload

    if payload.get("role") != "admin":
        return templates.TemplateResponse("not_access.html", {"request": request})

    try:
        operations = Operations(name=name)  # Do not set the id manually
        query = Operations.__table__.insert().values(name=name)
        await db.execute(query)
        logger.info(f"Oeration added successfully: {operations}")
    except Exception as e:
        logger.error(f"Error adding operation: {e}")
        await db.rollback()  # Rollback the transaction in case of an error
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return RedirectResponse(url="/operations/", status_code=303)


@router.post("/operations/{id}/delete/")
async def delete_operation_post(
        id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
):
    token = get_token_from_cookie(request)
    if isinstance(token, RedirectResponse):
        return token

    payload = get_current_user(token)
    if isinstance(payload, RedirectResponse):
        return payload

    if payload.get("role") != "admin":
        return templates.TemplateResponse("not_access.html", {"request": request})

    # Удаляем пользователя
    query = Operations.__table__.delete().where(Operations.id == id)
    await db.execute(query)

    return RedirectResponse(url="/operations/", status_code=303)
