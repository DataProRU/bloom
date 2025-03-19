# Используем Python образ
FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем зависимости для сборки некоторых библиотек
RUN apt-get update

# Обновляем pip
RUN pip install --upgrade pip

# Копируем файл с зависимостями и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# Копируем все файлы проекта
COPY . .

# Указываем команду по умолчанию для запуска приложения через uvicorn
CMD ["sh", "-c", "python bot.py & uvicorn main:app --host 0.0.0.0 --port 8000 --reload"]