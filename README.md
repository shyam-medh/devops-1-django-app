# Notes App Django

Notes App Django is a full-stack notes application built with Django and React, containerized with Docker Compose, and served through Nginx. The project is structured for local development and practical DevOps learning, with MySQL used as the primary database and Gunicorn serving the Django application.

## Repository

```bash
git clone https://github.com/shyam-medh/devops-1-django-app.git
cd devops-1-django-app
```

## Project Overview

This repository brings together a complete web application stack:

- `Django` for the backend application and API
- `React` for the frontend user interface
- `MySQL` for persistent relational data storage
- `Gunicorn` as the Python application server
- `Nginx` as the reverse proxy
- `Docker Compose` to orchestrate the full environment

The application is intended to be simple to run, easy to rebuild, and suitable for showcasing a containerized deployment workflow.

## Architecture

The stack is composed of three services:

- `db`: MySQL 8 with a persistent Docker volume
- `django`: Django application container that runs migrations, collects static files, and starts Gunicorn
- `nginx`: Reverse proxy that exposes the application to the browser

Application flow:

`Browser -> Nginx -> Django -> MySQL`

## Prerequisites

Make sure the following tools are installed before running the project:

- Docker Desktop
- Docker Compose
- Node.js
- npm

## Environment Variables

The backend can read database configuration from the root `.env` file, but Docker Compose now provides sensible defaults when `.env` is missing.

Example:

```env
DB_NAME=test_db
DB_USER=root
DB_PASSWORD=root
DB_PORT=3306
DB_HOST=db
```

Optional Django configuration can also be provided:

```env
DEBUG=True
DJANGO_SECRET_KEY=your-secret-key
```

## Getting Started

If you are cloning this repository for the first time, follow these steps in order.

### 1. Clone the repository

```bash
git clone https://github.com/shyam-medh/devops-1-django-app.git
cd devops-1-django-app
```

### 2. Verify or create the environment file

This step is optional for Docker-based deployments because Compose will use defaults when `.env` is missing. If you want to override them, create the root `.env` file from `.env.example`, then verify it contains the database settings below:

```env
DB_NAME=test_db
DB_USER=root
DB_PASSWORD=root
DB_PORT=3306
DB_HOST=db
```

### 3. Install frontend dependencies

This step is only needed if you want to build or run the React app directly outside Docker:

```bash
cd mynotes
npm install
```

### 4. Build the frontend

```bash
npm run build
cd ..
```

This generates the `mynotes/build` folder used by Django to serve the frontend when you are not relying on the Docker image build.

### 5. Build and start the application

```bash
docker compose up --build -d
```

This command will:

- build the Docker images
- build the React frontend inside the Django image
- start the MySQL, Django, and Nginx containers
- run Django migrations automatically
- collect static files automatically

### 6. Access the application

- Main application: `http://localhost:8080`
- Django directly: `http://localhost:8000`
- Django admin: `http://localhost:8080/admin/`

### 7. Stop the application

```bash
docker compose down
```

## Docker Compose Operations

### Start existing containers

Use this when the images are already built and you only want to start the stack:

```bash
docker compose up -d
```

### Start and rebuild containers

Use this after making code or Docker-related changes:

```bash
docker compose up --build -d
```

### Stop the running containers

Use this to stop and remove the running services:

```bash
docker compose down
```

### Stop containers and remove orphan services

Useful if the compose setup has changed and old containers still exist:

```bash
docker compose down --remove-orphans
```

### Restart the stack

```bash
docker compose down
docker compose up --build -d
```

## Useful Commands

View running containers:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs -f
```

Run Django system checks:

```bash
docker compose run --rm django python manage.py check
```

Open a shell inside the Django container:

```bash
docker compose exec django sh
```

## Project Structure

```text
.
|-- api/                Django app for notes APIs
|-- mynotes/            React source and built frontend assets
|-- nginx/              Nginx Dockerfile and configuration
|-- notesapp/           Django project settings and URLs
|-- docker-compose.yml  Multi-container application setup
|-- Dockerfile          Django application image
|-- requirements.txt    Python dependencies
|-- .env                Environment configuration
```

## Notes

- MySQL is available only within the Docker network and is not published to the host machine.
- Nginx is exposed on port `8080` to avoid conflicts with services that may already use port `80`.
- Static files are collected automatically when the Django container starts.
- The Django project can fall back to SQLite when MySQL environment variables are not provided.

## Repository Cleanup

The project has been cleaned to remove local-only and generated artifacts that should not be committed. Items such as Python cache folders, local database files, collected static files, local MySQL data, mock frontend JSON files, and unused Docker-related files were removed from the repository.

The following paths are intentionally ignored by Git:

- `__pycache__/`
- `db.sqlite3`
- `staticfiles/`
- `mysql-data/`
- `mynotes/node_modules/`
- `mynotes/build/`

Important:

- The React application is served by Django from the built frontend output.
- Docker builds the frontend during image creation, so `mynotes/build` does not need to be committed.
- If you run Django outside Docker and `mynotes/build` is missing, rebuild the frontend first.

Frontend build command:

```bash
cd mynotes
npm install
npm run build
```

## Tech Stack

- Django
- Django REST Framework
- React
- MySQL 8
- Gunicorn
- Nginx
- Docker Compose

## Repository Link

`https://github.com/shyam-medh/devops-1-django-app.git`
