# ДАР-Скрин

Веб-сервис назначения и заполнения анкет для обследования работников. Описание продукта — в [ABOUT.md](ABOUT.md), правила разработки — в [AGENT.md](AGENT.md).

## Стек (этап 1)

- Python 3.12, Django 5.2.19 (LTS), PostgreSQL 16, psycopg 3.2.13, gunicorn 23.0.0
- Gunicorn за nginx
- Docker Compose

## Быстрый запуск на тестовой Linux-ВМ

1. Скопируйте пример окружения и заполните значения **на ВМ** (файл `.env` не коммитить):

```bash
cp .env.example .env
```

Минимальный пример для теста (подставьте свои секреты):

```bash
DJANGO_SECRET_KEY=<длинный_случайный_секрет>
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,<имя_или_IP_ВМ>
CSRF_TRUSTED_ORIGINS=http://localhost:8080,http://127.0.0.1:8080,http://<имя_или_IP_ВМ>:8080
POSTGRES_DB=dar_scrin
POSTGRES_USER=dar_scrin
POSTGRES_PASSWORD=<пароль_бд>
POSTGRES_HOST=db
POSTGRES_PORT=5432
```

2. Поднимите стек **без удаления томов**:

```bash
docker compose up -d --build
```

3. При необходимости создайте администратора:

```bash
docker compose exec app python manage.py createsuperuser
```

4. Откройте сервис в браузере: `http://<хост>:8080/` (снаружи отвечает nginx на порту **8080**, внутри проксирует на Gunicorn).  
   `django runserver` для внешнего доступа на ВМ **не** использовать.

5. PostgreSQL снаружи не публикуется (только сеть Compose).

### Важно: сохранность данных

В обычных операциях **не** выполняйте `docker compose down -v` — флаг `-v` уничтожает тома с данными. Для остановки достаточно `docker compose down` или `docker compose stop`.

Подробнее: [docs/deployment.md](docs/deployment.md). Резервное копирование — зона ответственности сервера (дамп/том PostgreSQL, конфигурация, секреты).
