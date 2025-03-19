import logging

from database import Articles, Operations, Categories, get_db
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


@router.get("/articles/")
async def get_articles(request: Request, db: AsyncSession = Depends(get_db)):
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
        articles = await db.fetch_all(Articles.__table__.select())
        categories = await db.fetch_all(Categories.__table__.select())
        operations = await db.fetch_all(Operations.__table__.select())

        # Преобразуем данные в нужный формат
        operation_categories = {}
        for category in categories:
            operation_name = category.operation_name
            if operation_name not in operation_categories:
                operation_categories[operation_name] = []
            operation_categories[operation_name].append(category.name)
    except Exception as e:
        logger.error(f"Error fetching articles or categories: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return templates.TemplateResponse("articles.html",
                                      {"request": request,
                                       "articles": articles,
                                       "operations": operations,
                                       "operation_categories": operation_categories})


@router.delete("/articles/{id}/")
async def delete_article(
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
        stmt = select(Articles).where(Articles.id == id)
        result = await db.execute(stmt)
        article = result.scalar_one_or_none()

        if article:
            await db.delete(article)
            await db.commit()
            return JSONResponse({"detail": "Article deleted successfully"})
        return JSONResponse({"detail": "Article not found"}, status_code=404)
    except Exception as e:
        logger.error(f"Error deleting article: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/articles/{id}/edit/")
async def update_article(
        request: Request,
        id: int,
        title: str = Form(...),
        category_name: str = Form(...),
        category_operation: str = Form(...),
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
        article = await db.fetch_one(Articles.__table__.select().where(Articles.id == id))
        if not article:
            return templates.TemplateResponse("not_found.html", {"request": request})

        # Update the article
        query = (
            update(Articles.__table__)
            .where(Articles.id == id)
            .values(title=title,
                    category_name=category_name,
                    category_operation=category_operation)
        )
        await db.execute(query)
    except Exception as e:
        logger.error(f"Error updating article: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return RedirectResponse(url="/articles/", status_code=303)


@router.post("/articles/add/")
async def add_article(
        request: Request,
        title: str = Form(...),
        category_name: str = Form(...),
        category_operation: str = Form(...),
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
        article = Articles(title=title,
                           category_name=category_name,
                           category_operation=category_operation)

        query = Articles.__table__.insert().values(title=title,
                                                   category_name=category_name,
                                                   category_operation=category_operation
                                                   )
        await db.execute(query)
        logger.info(f"Article added successfully: {article}")
    except Exception as e:
        logger.error(f"Error adding article: {e}")
        await db.rollback()  # Rollback the transaction in case of an error
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return RedirectResponse(url="/articles/", status_code=303)


@router.post("/articles/{id}/delete/")
async def delete_article_post(
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
        query = Articles.__table__.delete().where(Articles.id == id)
        await db.execute(query)
    except Exception as e:
        logger.error(f"Error deleting article: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return RedirectResponse(url="/articles/", status_code=303)
