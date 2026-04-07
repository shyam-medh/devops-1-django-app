# Django Notes App

A full-stack notes application built with Django REST Framework and React, packaged with Docker Compose, proxied by Nginx, and backed by MySQL.

## Project Hierarchy

```text
.
|-- backend/           Django project, API app, Python dependencies, backend Dockerfile
|-- frontend/          React application source
|-- infra/nginx/       Nginx image and reverse-proxy configuration
|-- docker-compose.yml Multi-container local environment
|-- Jenkinsfile        Jenkins pipeline for build, test, and Docker deployment on the Jenkins agent
|-- .env.example       Sample environment variables
|-- README.md          Setup and run instructions
```

## Stack

- Django 4 + Django REST Framework
- React 18
- MySQL 8
- Gunicorn
- Nginx
- Docker Compose

## Architecture

`Browser -> Nginx -> Django -> MySQL`

Services started by Compose:

- `nginx`: public entrypoint on `http://localhost:8080`
- `django`: Django app on `http://localhost:8000`
- `db`: MySQL database inside the Docker network

## Prerequisites

For the recommended Docker workflow:

- Docker Desktop
- Docker Compose

For optional local development without Docker:

- Python 3.9+
- Node.js 18+
- npm

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/shyam-medh/devops-1-django-app.git
cd devops-1-django-app
```

### 2. Create the environment file

Docker Compose has defaults, but using a local `.env` file is clearer for new contributors.

```bash
cp .env.example .env
```

Example values:

```env
DB_NAME=test_db
DB_USER=root
DB_PASSWORD=root
DB_PORT=3306
DB_HOST=db
DEBUG=False
DJANGO_SECRET_KEY=change-me
```

### 3. Pull and start the project

```bash
docker compose pull
docker compose up -d
```

What this does:

- pulls the published backend and nginx images from Docker Hub
- starts MySQL, Django, and Nginx
- runs Django migrations automatically
- collects static files automatically

### 4. Open the app

- Main app: `http://localhost:8080`
- Django directly: `http://localhost:8000`
- Django admin: `http://localhost:8080/admin/`

### 5. Stop the project

```bash
docker compose down
```

## Useful Docker Commands

```bash
docker compose ps
docker compose logs -f
docker compose exec django sh
docker compose exec django python manage.py createsuperuser
docker compose run --rm django python manage.py check
```

Refresh to the latest published images:

```bash
docker compose pull
docker compose up -d
```

## Push Images To Docker Hub

This project builds two publishable images:

- `django`: the Django app image with the built React frontend included
- `nginx`: the reverse-proxy image

Set your Docker Hub namespace and image tag in the root `.env` file:

```env
DOCKERHUB_USERNAME=your-dockerhub-username
IMAGE_TAG=latest
```

To publish a new image version after code or Dockerfile changes, sign in, build each image, and push:

```bash
docker login
docker build -f backend/Dockerfile -t <DOCKERHUB_USERNAME>/django-notes-backend:<IMAGE_TAG> .
docker build -f infra/nginx/Dockerfile -t <DOCKERHUB_USERNAME>/django-notes-nginx:<IMAGE_TAG> infra/nginx
docker push <DOCKERHUB_USERNAME>/django-notes-backend:<IMAGE_TAG>
docker push <DOCKERHUB_USERNAME>/django-notes-nginx:<IMAGE_TAG>
```

The pushed image names will be:

```text
docker.io/<DOCKERHUB_USERNAME>/django-notes-backend:<IMAGE_TAG>
docker.io/<DOCKERHUB_USERNAME>/django-notes-nginx:<IMAGE_TAG>
```

Example:

```bash
docker build -f backend/Dockerfile -t shyammedh/django-notes-backend:v1 .
docker build -f infra/nginx/Dockerfile -t shyammedh/django-notes-nginx:v1 infra/nginx
docker push shyammedh/django-notes-backend:v1
docker push shyammedh/django-notes-nginx:v1
```

```text
shyammedh/django-notes-backend:v1
shyammedh/django-notes-nginx:v1
```

## Jenkins Pipeline

This repository already includes a Jenkins pipeline in `Jenkinsfile`.

### Jenkins prerequisites

The current pipeline runs on the Jenkins agent label:

```text
dard
```

The Jenkins node or agent with this label should have:

- Git
- Python 3.9+
- Node.js 18+
- npm
- Docker
- Docker Compose (`docker-compose`)
- System packages required for `mysqlclient` on Linux:
  `pkg-config`, `build-essential`, `default-libmysqlclient-dev`

Useful note:

- If the root `.env` file is missing, Jenkins copies `.env.example` to `.env` before deployment.
- Make sure `.env.example` contains the values you want Jenkins to use.

### How to run this project from Jenkins

1. Open Jenkins.
2. Create a new item.
3. Choose `Pipeline` as the job type.
4. In the job configuration, select `Pipeline script from SCM`.
5. Choose `Git` as the SCM.
6. Add your repository URL:

```text
https://github.com/shyam-medh/devops-1-django-app.git
```

7. Select the branch you want Jenkins to build.
8. Set `Script Path` to:

```text
Jenkinsfile
```

9. Save the job.
10. Click `Build Now`.

If you are using a Jenkins node setup with labels, make sure the job can run on the agent labeled `dard`, because the pipeline contains:

```groovy
agent { label 'dard' }
```

### What the Jenkins pipeline does

The pipeline runs these stages:

1. `Build Frontend`
2. `Install Backend Dependencies`
3. `Test Backend`
4. `Deploy Containers`

In practice, Jenkins will:

- install frontend dependencies in `frontend/`
- build the React app
- create a Python virtual environment
- install backend dependencies from `backend/requirements.txt`
- run Django `check` and `test`
- create `.env` from `.env.example` if needed
- use the root `.env` file for database and Django settings during deployment
- pull published Docker Hub images for `django` and `nginx`
- redeploy containers with:

```bash
docker-compose down || true
docker-compose pull
docker-compose up -d
```

### Jenkins build output

The pipeline archives the built frontend files from:

```text
frontend/build/
```

You can download them from the Jenkins job after a successful build.

## Local Development Without Docker

### Backend

```bash
python -m venv .venv
```

Activate the virtual environment:

```bash
# Windows PowerShell
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

Then install and run the backend:

```bash
pip install -r backend/requirements.txt
python backend/manage.py migrate
python backend/manage.py runserver
```

Notes:

- If `DB_NAME` is not set, Django falls back to SQLite.
- Static files are collected into `backend/staticfiles/`.

### Frontend

In a second terminal:

```bash
cd frontend
npm install
npm start
```

The React dev server proxies API requests to `http://127.0.0.1:8000`.

If you want Django to serve the built frontend instead of the React dev server:

```bash
cd frontend
npm install
npm run build
```

## Environment Variables

Root `.env` supports these values:

- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_PORT`
- `DB_HOST`
- `DEBUG`
- `DJANGO_SECRET_KEY`

## Troubleshooting

- If `localhost:8080` is busy, stop the conflicting process or change the published port in `docker-compose.yml`.
- If the frontend looks outdated, publish fresh images and then run `docker compose pull` followed by `docker compose up -d`.
- If containers start but the app is unavailable, check `docker compose logs -f`.
- If you want a completely fresh database volume, run `docker compose down -v` and then start again.
- If Jenkins fails with `npm: not found`, install Node.js and npm on the `dard` agent.
- If Jenkins fails while installing `mysqlclient`, install `pkg-config`, `build-essential`, and `default-libmysqlclient-dev` on the agent.
- If deployment fails after Django starts, inspect:
  `docker-compose ps`, `docker-compose logs django`, `docker-compose logs nginx`, and `docker-compose logs db`

## Notes

- `frontend/build/` is generated output and should not be committed.
- MySQL is available only inside the Docker network.
- Nginx is exposed on port `8080` to avoid conflicts with services already using port `80`.
