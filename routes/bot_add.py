from datetime import datetime
from typing import Optional
import logging
import gspread
from database import TgUser, get_db, PaymentTypes, Operations, Categories, Articles, Wallets
from databases import Database
from fastapi import FastAPI, Form, Request, APIRouter, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pytz import timezone

app = FastAPI()
router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация gspread
try:
    gc = gspread.service_account(filename="credentials.json")
    sht2 = gc.open_by_url(
        'https://docs.google.com/spreadsheets/d/1NZaFb5ssWHbVcWH-3OUgLN32KcoxI86GW7qyNttZbsI/edit?gid=0#gid=0'
    )
    worksheet = sht2.get_worksheet(0)
except Exception as e:
    print(f"Ошибка при инициализации gspread: {str(e)}")

moscow_tz = timezone('Europe/Moscow')

def format_date(date):
    date_obj = datetime.strptime(date, "%Y-%m-%d").date()
    return date_obj.strftime("%d.%m.%Y")


@router.get("/tg_bot_add", response_class=HTMLResponse)
async def get_form(request: Request, username: str, db: Database = Depends(get_db)):
    users_data = await db.fetch_all(TgUser.__table__.select())
    payment_types = await db.fetch_all(PaymentTypes.__table__.select())
    operations = await db.fetch_all(Operations.__table__.select())
    categories = await db.fetch_all(Categories.__table__.select())
    articles = await db.fetch_all(Articles.__table__.select())
    wallets = await db.fetch_all(Wallets.__table__.select())

    # Преобразуем данные в нужный формат
    category_articles = {}
    for article in articles:
        category_name = article.category_name
        if category_name not in category_articles:
            category_articles[category_name] = []
        category_articles[category_name].append(article.title)

    operation_categories = {}
    for category in categories:
        operation_name = category.operation_name
        if operation_name not in operation_categories:
            operation_categories[operation_name] = []
        operation_categories[operation_name].append(category.name)

    return templates.TemplateResponse(
        "bot/form.html",
        {"request": request, "users": users_data, "username": username,
         "payment_types": payment_types, "operations": operations,
         "operation_categories": operation_categories,
         "category_articles": category_articles, "wallets": wallets}
    )


@router.post("/submit", response_class=HTMLResponse)
async def submit_form(
        request: Request,
        username: str = Form(...),
        date: str = Form(...),
        operation_type: str = Form(...),
        accounting_type: Optional[str] = Form(None),
        account_type: Optional[str] = Form(None),
        date_finish: Optional[str] = Form(None),
        amount: float = Form(...),
        payment_type: Optional[str] = Form(None),
        comment: str = Form(...),
        wallet_from: Optional[str] = Form(None),
        wallet_to: Optional[str] = Form(None),
        wallet: Optional[str] = Form(None),
):
    try:
        current_time = datetime.now(moscow_tz).strftime("%d.%m.%Y %H:%M:%S")
        username = username.replace("%20", " ")

        # Применяем форматирование столбца с датами до добавления данных
        worksheet.format('C:C', {
            "numberFormat": {
                "type": "DATE",
                "pattern": "dd.mm.yyyy"
            }
        })
        worksheet.format('G:G', {
            "numberFormat": {
                "type": "DATE",
                "pattern": "dd.mm.yyyy"
            }
        })
        worksheet.format('A:A', {
            "numberFormat": {
                "type": "DATE",
                "pattern": "dd.mm.yyyy HH:mm:ss"
            }
        })

        # Преобразуем строку даты в объект datetime
        formatted_operation_date = format_date(date)

        if operation_type == "Перемещение":
            # Для "Перемещения" дата окончания не требуется
            formatted_finish_date = ""
        else:
            formatted_finish_date = format_date(date_finish)
            if operation_type == "Расход":
                # Для "Расхода" меняем знак суммы на отрицательный
                amount = -amount

        new_row = [
            current_time,
            username,
            formatted_operation_date,
            # Передаем дату операции в формате, который Google Таблицы могут распознать как дату
            operation_type,
            accounting_type,
            account_type,
            formatted_finish_date,
            # Передаем дату назначения в формате, который Google Таблицы могут распознать как дату
            amount,
            payment_type,
            comment,
        ]

        if operation_type == "Перемещение":
            new_row.append(wallet_from)
            new_row[7] = -new_row[7]
            worksheet.append_row(new_row, value_input_option="USER_ENTERED")
            new_row[-1] = wallet_to
            new_row[7] = -new_row[7]
            worksheet.append_row(new_row, value_input_option="USER_ENTERED")
        else:
            new_row.append(wallet)
            worksheet.append_row(new_row, value_input_option="USER_ENTERED")

        return templates.TemplateResponse(
            "bot/success.html", {"request": request, "message": "Данные успешно добавлены!"}
        )
    except Exception as e:
        print(f"Ошибка при добавлении строки: {str(e)}")
        logger.error(f"Ошибка: {e}")
        return templates.TemplateResponse(
            "bot/error.html", {"request": request, "message": f"Произошла ошибка: {str(e)}"}
        )


app.include_router(router)
