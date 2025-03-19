import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Укажите ваш токен от BotFather
BOT_TOKEN = "7382155025:AAHDSIkwnZRKMq2waIBYAw1Z7QkhWjCnJOQ"
DATABASE_URL = "sqlite:///./eq_rental.db"

# URL мини-приложения
WEB_APP_URL = "https://garage-garageshop.amvera.io/tg_bot_add"

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Инициализация SQLAlchemy
Base = declarative_base()
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()


class TgUser(Base):
    __tablename__ = "tg_users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tg_username = Column(String, unique=True, nullable=False)
    username = Column(String, unique=True, nullable=False)


# Функция для получения имени пользователя по нику в Telegram
async def get_user_by_tg_username(tg_username: str) -> str:
    user = session.query(TgUser).filter_by(tg_username=tg_username).first()
    print(f"User from DB: {user}")  # Логирование для проверки
    return user.username if user else None


@dp.message(Command("start"))
async def start_command_handler(message: types.Message):
    # Получаем ник пользователя
    user_nick = message.from_user.username

    # Получаем имя пользователя из базы данных
    user_name = await get_user_by_tg_username(user_nick)
    if user_name:
        user_nick = user_name
    else:
        user_nick = "гость"

    # Создаем инлайн-клавиатуру с кнопкой для мини-приложения, если пользователь не гость
    if user_nick != "гость":
        web_app_url_with_params = f"{WEB_APP_URL}?username={user_nick}"
        print(f"Web App URL: {web_app_url_with_params}")  # Логирование для проверки
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Открыть мини-приложение",
                        web_app=WebAppInfo(url=web_app_url_with_params)
                    )
                ]
            ]
        )
    else:
        keyboard = None

    # Отправляем приветственное сообщение с кнопкой, если пользователь не гость
    await message.answer(
        f"Привет, {user_nick}! 👋\nДобро пожаловать в бота!",
        reply_markup=keyboard
    )


async def main():
    # Запуск бота
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
