add-app name:
  cd src && python manage.py startapp {{name}}

run:
  cd src && python manage.py runserver

makemigrations:
  cd src && python manage.py makemigrations

migrate:
  cd src && python manage.py migrate

check:
  cd src && python manage.py check

shell:
  cd src && python manage.py shell

format:
  uv run ruff format

