import os
from enum import unique

from databases import Database
from fastapi import APIRouter
from fastapi.templating import Jinja2Templates
from sqlalchemy import Column, Integer, String, ForeignKey, MetaData, create_engine, Boolean, Numeric
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Строка подключения к базе данных
DATABASE_URL = os.getenv("DATABASE_URL")
database = Database(DATABASE_URL)
metadata = MetaData()

# Создаем базовый класс для моделей
Base = declarative_base(metadata=metadata)


# Определение модели WebUser с использованием SQLAlchemy
class WebUser(Base):
    __tablename__ = "web_users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False, server_default="user")

    wallets = relationship("Wallets", back_populates="web_user")


class TgUser(Base):
    __tablename__ = "tg_users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tg_username = Column(String, unique=True, nullable=False)
    username = Column(String, unique=True, nullable=False)
    buttons = Column(Boolean, nullable=False, default=False)


class Wallets(Base):
    __tablename__ = "wallets"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    username = Column(Integer, ForeignKey("web_users.username"))
    balance = Column(Numeric(10, 2), default=0, nullable=False)

    web_user = relationship("WebUser", back_populates="wallets")


class Operations(Base):
    __tablename__ = "operations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)

    categories = relationship("Categories", back_populates="operations")


class Categories(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=False, nullable=False)
    # operation_id = Column(Integer, ForeignKey("operations.id"))
    operation_name = Column(String, ForeignKey("operations.name"))

    operations = relationship("Operations", back_populates="categories")
    articles = relationship("Articles", back_populates="categories")


class Articles(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, unique=False, nullable=False)
    # category_id = Column(Integer, ForeignKey("categories.id"))
    category_name = Column(String, ForeignKey("categories.name"))
    category_operation = Column(String, unique=False, nullable=False)

    categories = relationship("Categories", back_populates="articles")



class PaymentTypes(Base):
    __tablename__ = "payment_types"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)


class FinancialOperations(Base):
    __tablename__ = "financial_operations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String, nullable=False)
    username = Column(String, nullable=False)
    operation_date = Column(String, nullable=False)
    operation_type = Column(String, nullable=False)
    accounting_type = Column(String, nullable=False)
    account_type = Column(String, nullable=False)
    finish_date = Column(String)
    amount = Column(String, nullable=False)
    payment_type = Column(String, nullable=False)
    comment = Column(String)
    wallet = Column(String)
    wallet_from = Column(String)
    wallet_to = Column(String)


# Создаем асинхронный engine для работы с базой данных SQLAlchemy
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Асинхронная функция для создания таблиц
async def init_db():
    # Создаем таблицы в базе данных
    Base.metadata.create_all(bind=engine)


async def get_db():
    # Возвращаем объект базы данных для использования в зависимостях
    if not database.is_connected:
        await database.connect()
    try:
        yield database
    finally:
        await database.disconnect()
