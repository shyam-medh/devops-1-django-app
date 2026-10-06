kubectl set image deployment/django-backend django-backend=nginx:nonexistent -n django
Write-Host "Broke deployment django-backend in django namespace (set image to nginx:nonexistent)!"
