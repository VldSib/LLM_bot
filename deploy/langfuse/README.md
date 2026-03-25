# Langfuse self-host (Docker)

Файл `docker-compose.yml` в этой папке — **копия официального** из репозитория [langfuse/langfuse](https://github.com/langfuse/langfuse) (ветка `main`). При обновлении Langfuse имеет смысл снова скачать свежую версию с GitHub.

Стек: **Langfuse 3.x** (`langfuse-web`, `langfuse-worker`), PostgreSQL, Redis, ClickHouse, MinIO — как в upstream.

## Установка с нуля

1. **На сервере** установлены **Docker** и **Docker Compose** (plugin `docker compose`). Проверка: `docker --version`, `docker compose version`.

2. **Старый Langfuse** (если был): в каталоге со старым `docker-compose.yml` выполните `docker compose down -v` (полное удаление данных) или `docker compose down` (только контейнеры). Убедитесь, что порт **3000** свободен: `ss -tlnp | grep 3000`.

3. **Файлы** этого репозитория: склонируйте [LLM_bot](https://github.com/VldSib/LLM_bot) или скопируйте папку `deploy/langfuse/` на VPS. Рабочий каталог для Langfuse: `deploy/langfuse` (внутри клона).

4. **Общая сеть с ботом** (один раз на хосте):

   ```bash
   docker network create llm_shared
   ```

   Если сеть уже есть, команда выдаст ошибку — это нормально.

5. **`.env`** в `deploy/langfuse/` рядом с `docker-compose.yml`. Скопируйте пример из раздела ниже и заполните секреты. Обязательно согласуйте пароли: `POSTGRES_PASSWORD` в `DATABASE_URL`, `CLICKHOUSE_PASSWORD`, `REDIS_AUTH`, `MINIO_ROOT_PASSWORD` и все `LANGFUSE_S3_*_SECRET_ACCESS_KEY` / ключи MinIO в env Langfuse.

   Полезные команды:

   ```bash
   openssl rand -hex 32   # для NEXTAUTH_SECRET, SALT, ENCRYPTION_KEY
   ```

6. **Запуск стека** из `deploy/langfuse/`:

   ```bash
   cd deploy/langfuse
   docker compose pull
   docker compose up -d
   docker compose ps
   ```

   Дождитесь `healthy` у зависимостей (postgres, redis и т.д.). Логи при проблемах: `docker compose logs -f langfuse-web`.

7. **Веб-интерфейс**: сервис **`langfuse-web`**, порт **3000**. Локально: `http://127.0.0.1:3000`. С VPS без открытия порта наружу — SSH-туннель с ПК: `ssh -L 3000:127.0.0.1:3000 user@ВАШ_VPS`, затем в браузере `http://localhost:3000`.

8. **Первый вход**: создайте организацию/пользователя в UI (если не заданы `LANGFUSE_INIT_*` в `.env`).

9. **API Keys**: в Langfuse **Settings → API Keys** создайте ключи и скопируйте **Public** и **Secret**.

10. **Бот LLM_bot** в той же сети `llm_shared`: в **корне** репозитория в `.env` укажите:

    ```env
    LANGFUSE_ENABLED=true
    LANGFUSE_PUBLIC_KEY=pk-lf-...
    LANGFUSE_SECRET_KEY=sk-lf-...
    LANGFUSE_HOST=http://langfuse-web:3000
    ```

    Поднимите бота:

    ```bash
    cd /путь/к/LLM_bot
    docker compose up -d --build
    ```

11. **Проверка связи** из контейнера бота (должен быть HTTP 200):

    ```bash
    docker exec llm-bot python3 -c "import urllib.request; print(urllib.request.urlopen('http://langfuse-web:3000/api/public/health', timeout=5).status)"
    ```

12. **Фаервол**: при необходимости откройте порт 3000 только для нужных IP; внутренняя связка бот ↔ Langfuse идёт по Docker-сети и не требует публикации 3000 в интернет.

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

3. **Сеть `llm_shared`** (нужна для связки с ботом; в `docker-compose.yml` она объявлена как `external`):

   Один раз на хосте:

   ```bash
   docker network create llm_shared
   ```

   Затем из этой папки:

   ```bash
   docker compose pull
   docker compose up -d
   docker compose ps
   ```

   Сервис `langfuse-web` подключён к `llm_shared` и к внутренней сети compose. Бот в корне репозитория LLM_bot подключается к той же сети — в `.env` бота: `LANGFUSE_HOST=http://langfuse-web:3000`.

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

Оба compose-файла (корень LLM_bot и эта папка) используют сеть **`llm_shared`** (`external: true`). На VPS после правок выполните `docker compose up -d` у Langfuse и у бота, чтобы контейнеры переподключились к сети.

## Полезные ссылки

- [Документация self-host Langfuse](https://langfuse.com/docs/deployment/self-host)
- [Исходный docker-compose.yml](https://github.com/langfuse/langfuse/blob/main/docker-compose.yml)
