import logging

from database import Categories, Operations, get_db
from dependencies import get_token_from_cookie, get_current_user
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

router = APIRouter()
templates = Jinja2Templates(directory="templates/directory/")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@router.get("/categories/")
async def get_categories(request: Request, db: AsyncSession = Depends(get_db)):
    logger.info("checking")
    token = get_token_from_cookie(request)
    if isinstance(token, RedirectResponse):
        return token

    payload = get_current_user(token)
    if isinstance(payload, RedirectResponse):
        return payload

    role = payload.get("role")
    if role != "admin":
        return templates.TemplateResponse("not_access.html", {"request": request})

    try:
        categories = await db.fetch_all(Categories.__table__.select())
        operations = await db.fetch_all(Operations.__table__.select())
    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return templates.TemplateResponse("categories.html", {"request": request, "categories": categories, "operations": operations})


@router.delete("/categories/{id}/")
async def delete_category(
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

    try:
        stmt = select(Categories).where(Categories.id == id)
        result = await db.execute(stmt)
        category = result.scalar_one_or_none()

        if category:
            await db.delete(category)
            await db.commit()
            return JSONResponse({"detail": "Category deleted successfully"})
        return JSONResponse({"detail": "Category not found"}, status_code=404)
    except Exception as e:
        logger.error(f"Error deleting category: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/categories/{id}/edit/")
async def update_category(
        request: Request,
        id: int,
        name: str = Form(...),
        operation_name: str = Form(...),
        db: AsyncSession = Depends(get_db),
):
    token = get_token_from_cookie(request)
    if isinstance(token, RedirectResponse):
        return token

    payload = get_current_user(token)
    if isinstance(payload, RedirectResponse):
        return payload

    user_role = payload.get("role")
    if user_role != "admin":
        return templates.TemplateResponse("not_access.html", {"request": request})

    try:
        # Check if the category exists
        category = await db.fetch_one(Categories.__table__.select().where(Categories.id == id))
        if not category:
            return templates.TemplateResponse("not_found.html", {"request": request})

        # Update the category
        query = (
            update(Categories.__table__)
            .where(Categories.id == id)
            .values(name=name, operation_name=operation_name)
        )
        await db.execute(query)
    except Exception as e:
        logger.error(f"Error updating category: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return RedirectResponse(url="/categories/", status_code=303)


@router.post("/categories/add/")
async def add_category(
        request: Request,
        name: str = Form(...),
        operation_name: str = Form(...),
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
        category = Categories(name=name, operation_name=operation_name)  # Do not set the id manually
        query = Categories.__table__.insert().values(name=name, operation_name=operation_name)
        await db.execute(query)
        logger.info(f"Category added successfully: {category}")
    except Exception as e:
        logger.error(f"Error adding category: {e}")
        await db.rollback()  # Rollback the transaction in case of an error
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return RedirectResponse(url="/categories/", status_code=303)


@router.post("/categories/{id}/delete/")
async def delete_category_post(
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

    try:
        query = Categories.__table__.delete().where(Categories.id == id)
        await db.execute(query)
    except Exception as e:
        logger.error(f"Error deleting category: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return RedirectResponse(url="/categories/", status_code=303)
