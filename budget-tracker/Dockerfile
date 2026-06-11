FROM node:24-alpine AS frontend-build

WORKDIR /build/frontend
COPY app-src/frontend/package.json app-src/frontend/package-lock.json* ./
RUN npm ci
COPY app-src/frontend/ ./
ENV VITE_API_BASE_URL=api
RUN npm run build

FROM python:3.13-slim

WORKDIR /app

COPY app-src/backend/pyproject.toml ./
COPY app-src/backend/app ./app
RUN pip install --no-cache-dir -e .

COPY --from=frontend-build /build/frontend/dist ./frontend
COPY run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 8099
CMD ["/run.sh"]
