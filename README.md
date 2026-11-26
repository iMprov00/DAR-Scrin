# ДАР-Скрин

Веб-сервис назначения и заполнения анкет для обследования работников. Описание продукта — в [ABOUT.md](ABOUT.md), правила разработки — в [AGENT.md](AGENT.md).

## Стек

- Python 3.12, Django 5.2.19 (LTS), PostgreSQL 16, psycopg 3.2.13, gunicorn 23.0.0
- Gunicorn за nginx (порт хоста **8080**)
- Docker Compose: сервисы `db`, `app`, `nginx`

## Быстрый запуск на тестовой Linux-ВМ

1. Скопируйте пример окружения и заполните значения **на ВМ** (файл `.env` не коммитить):

```bash
cp .env.example .env
```

Минимальный пример для теста (подставьте свои секреты; **не** копируйте реальные значения в git и отчёты):

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

При старте контейнера `app` entrypoint сам ждёт PostgreSQL, применяет миграции (`migrate --noinput`), собирает статику (`collectstatic`) и запускает Gunicorn. Отдельно эти шаги выполнять не нужно.

3. Загрузите явно помеченный демо-шаблон анкеты (синтетика, **не** бланк Минздрава):

```bash
docker compose exec app python manage.py load_demo_questionnaire
```

4. Создайте администратора и синтетические роли:

```bash
docker compose exec app python manage.py createsuperuser
```

Далее в Django Admin (`/admin/`): учётки с флагами `is_employee` / `is_therapist`, у сотрудника — профиль с датой рождения и подразделением. Только синтетические данные; реальные ПДн и медицину не переносить. Пароли храните только на ВМ.

5. Проверьте доступ через nginx (не через `runserver`):

- вход: `http://<хост>:8080/login/`
- локальный HTMX (без CDN): `http://<хост>:8080/static/vendor/htmx.min.js` — ожидается HTTP 200

6. PostgreSQL **не** публикуется на хост (в `docker-compose.yml` у `db` нет `ports`). Снаружи открыт только nginx `:8080`.

### Важно: сохранность данных

В обычных операциях **не** выполняйте `docker compose down -v` — флаг `-v` уничтожает тома `postgres_data` и `static_volume`. Для остановки: `docker compose stop` или `docker compose down` (без `-v`). Перезапуск: `docker compose restart` или `down` + `up -d` без `-v`.

Полный runbook, резерв и откат: [docs/deployment.md](docs/deployment.md).
