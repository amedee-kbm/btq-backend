add-app name:
  cd src && python manage.py startapp {{name}}

run:
  cd src && uv run python manage.py runserver

makemigrations:
  cd src && uv run python manage.py makemigrations

migrate:
  cd src && uv run python manage.py migrate

check:
  cd src && uv run python manage.py check

shell:
  cd src && uv run python manage.py shell

format:
  uv run ruff format

