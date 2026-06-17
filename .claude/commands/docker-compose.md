# Docker Compose 설정 스킬

이 스킬은 Neeews 프로젝트(FastAPI + MySQL + 정적 프론트엔드)에 맞는 Docker Compose 환경을 구성합니다.

## 실행 순서

아래 단계를 순서대로 모두 실행하세요. 파일이 이미 존재하면 덮어쓰기 전에 사용자에게 확인하세요.


### 1단계 — back-end/Dockerfile 생성

`back-end/Dockerfile`을 생성하세요:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY ../requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

> requirements.txt는 프로젝트 루트에 있으므로, 빌드 컨텍스트를 루트로 설정합니다(3단계에서 처리).

---

### 2단계 — docker-compose.yml 생성

프로젝트 루트에 `docker-compose.yml`을 생성하세요:

```yaml
services:
  db:
    image: mysql:8.0
    container_name: neeews-db
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-u", "root", "-p${MYSQL_ROOT_PASSWORD}"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: .
      dockerfile: back-end/Dockerfile
    container_name: neeews-backend
    restart: unless-stopped
    working_dir: /app/back-end
    env_file:
      - .env
    environment:
      DATABASE_URL: mysql+aiomysql://${MYSQL_USER}:${MYSQL_PASSWORD}@db:3306/${MYSQL_DATABASE}
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./back-end:/app/back-end

  frontend:
    image: nginx:alpine
    container_name: neeews-frontend
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ./front-end:/usr/share/nginx/html:ro
    depends_on:
      - backend

volumes:
  mysql_data:
```

---

### 3단계 — back-end/Dockerfile 수정 (빌드 컨텍스트가 루트이므로)

`back-end/Dockerfile`의 COPY 경로를 수정하세요:

```dockerfile
FROM python:3.12-slim

WORKDIR /app/back-end

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY back-end/ /app/back-end/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 주의사항

- `DATABASE_URL`은 `docker-compose.yml`에서 `environment`로 주입되므로 `.env`에 별도로 설정하지 않아도 됩니다.
- MySQL 컨테이너가 완전히 준비된 후 백엔드가 시작되도록 `healthcheck`와 `depends_on`이 설정되어 있습니다.
- `volumes: ./back-end:/app/back-end`는 개발 중 코드 변경 시 재빌드 없이 반영됩니다 (단, 의존성 변경 시에는 `--build` 필요).
