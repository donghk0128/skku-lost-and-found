FROM python:3.12.15-slim-bookworm

WORKDIR /app

COPY requirements.lock .
RUN python -m pip install --no-cache-dir -r requirements.lock

COPY . .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]