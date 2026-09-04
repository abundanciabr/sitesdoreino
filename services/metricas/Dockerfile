FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python manage.py collectstatic --noinput || true
EXPOSE 8000
# migrate no boot (Expand-and-Contract garante compatibilidade com código anterior)
CMD ["sh", "-c", "python manage.py migrate --noinput && uvicorn config.asgi:application --host 0.0.0.0 --port 8000"]
