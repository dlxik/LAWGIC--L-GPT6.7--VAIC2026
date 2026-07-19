# Deploy image cho Render (build tu GOC repo — dong goi ca backend + frontend + prompts + data).
# Khac backend/Dockerfile (chi dong goi backend/, dung cho docker-compose co mount volume).
FROM python:3.12-slim

WORKDIR /app

# Cai dependency truoc de tan dung layer cache
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy toan bo repo — main.py serve /frontend/static va doc /prompts, /data luc chay
COPY . /app
ENV PYTHONPATH=/app

# Render cap $PORT luc chay; mac dinh 8000 khi chay local (docker run)
EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
