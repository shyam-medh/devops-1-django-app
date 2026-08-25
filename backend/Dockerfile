# Stage 1: builder
# Installs system dependencies and compiles Python packages.
# Build tools are NOT carried into the final image, keeping it small.
FROM python:3.9-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       default-libmysqlclient-dev \
       pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt


# Stage 2: final runtime image
# Only contains the app code and runtime libs — no compilers or build tools.
FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libmariadb3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

COPY . .

# Collect static files at build time so they're always present
RUN SECRET_KEY=build-time-placeholder \
    DB_HOST=localhost DB_NAME=x DB_USER=x DB_PASSWORD=x \
    python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "notesapp.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
