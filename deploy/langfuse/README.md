# Langfuse self-host (Docker)

Файл `docker-compose.yml` в этой папке — **копия официального** из репозитория [langfuse/langfuse](https://github.com/langfuse/langfuse) (ветка `main`). При обновлении Langfuse имеет смысл снова скачать свежую версию с GitHub.

Стек: **Langfuse 3.x** (`langfuse-web`, `langfuse-worker`), PostgreSQL, Redis, ClickHouse, MinIO — как в upstream.

## Быстрый старт (VPS или локально)

1. Перейти в эту папку:

   ```bash
   cd deploy/langfuse
   ```

2. Создать **`.env`** рядом с `docker-compose.yml`. Docker Compose подставит переменные из `.env` в compose-файл.

   Обязательно замените значения, помеченные в `docker-compose.yml` комментариями **`# CHANGEME`**, в том числе:

   - `NEXTAUTH_SECRET`, `SALT`, `ENCRYPTION_KEY` (для `ENCRYPTION_KEY`: `openssl rand -hex 32`)
   - пароли: Postgres, ClickHouse, Redis (`REDIS_AUTH`), MinIO (`MINIO_ROOT_PASSWORD` и связанные `LANGFUSE_S3_*_SECRET_ACCESS_KEY`)
   - при необходимости — `DATABASE_URL` согласованный с `POSTGRES_*`

   Минимальный пример заголовков (подставьте свои секреты):

   ```env
   NEXTAUTH_URL=http://localhost:3000
   NEXTAUTH_SECRET=
   SALT=
   ENCRYPTION_KEY=
   DATABASE_URL=postgresql://postgres:ВАШ_ПАРОЛЬ@postgres:5432/postgres
   POSTGRES_PASSWORD=
   CLICKHOUSE_PASSWORD=
   REDIS_AUTH=
   MINIO_ROOT_PASSWORD=
   MINIO_ROOT_USER=minio
   ```

3. Запуск:

   ```bash
   docker compose pull
   docker compose up -d
   docker compose ps
   ```

4. Веб-интерфейс: порт **3000** у сервиса **`langfuse-web`**. На VPS без открытия порта наружу удобно: SSH-туннель с ПК:

   ```bash
   ssh -L 3000:127.0.0.1:3000 user@ВАШ_VPS
   ```

   Затем в браузере: `http://localhost:3000`

5. В UI создайте проект и скопируйте **API Keys** (public / secret).

## Связка с ботом (Docker)

Имя сервиса в этом compose — **`langfuse-web`**, не `langfuse`.

В `.env` **бота** на той же Docker-сети, что и Langfuse:

```env
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://langfuse-web:3000
```

Если бот и Langfuse в **разных** `docker compose`, подключите их к **общей внешней сети** Docker (см. `LangFuse_observability.md` в корне репозитория).

## Полезные ссылки

- [Документация self-host Langfuse](https://langfuse.com/docs/deployment/self-host)
- [Исходный docker-compose.yml](https://github.com/langfuse/langfuse/blob/main/docker-compose.yml)
