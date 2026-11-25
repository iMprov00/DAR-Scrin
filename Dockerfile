FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# gunicorn/psycopg — с зеркала; Django 5.2 LTS — с официального тега GitHub
# (часть зеркал PyPI на тестовой ВМ не отдаёт линейку 5.2).
RUN pip install --no-cache-dir \
      "setuptools>=83" \
      "psycopg[binary]==3.2.13" \
      "gunicorn==23.0.0" \
      "asgiref>=3.8.1" \
      "sqlparse>=0.3.1" \
    && pip install --no-cache-dir --no-build-isolation \
      "https://github.com/django/django/archive/refs/tags/5.2.19.tar.gz"

COPY . .

RUN chmod +x /app/scripts/entrypoint.sh \
    && mkdir -p /app/staticfiles

EXPOSE 8000

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
