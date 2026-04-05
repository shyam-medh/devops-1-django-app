FROM node:18-alpine AS frontend-builder

WORKDIR /frontend

COPY mynotes/package*.json ./
RUN npm ci

COPY mynotes/ ./
RUN npm run build

FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend-builder /frontend/build ./mynotes/build

EXPOSE 8000
CMD ["python3", "manage.py", "runserver", "0.0.0.0:8000"]
