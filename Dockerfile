FROM python:3.11-slim

WORKDIR /app

# Requirements o'rnatamiz
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Qolgan barcha loyiha fayllarini nusxalaymiz
COPY . .

# Botni ishga tushiramiz
CMD ["python", "bot.py"]
