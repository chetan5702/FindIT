FROM python:3.12.8-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system findit && adduser --system --ingroup findit findit

COPY requirements.txt requirements-dev.txt ./
ARG INSTALL_DEV=false
RUN if [ "$INSTALL_DEV" = "true" ]; then \
      pip install --no-cache-dir -r requirements-dev.txt; \
    else \
      pip install --no-cache-dir -r requirements.txt; \
    fi

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY docker-entrypoint.sh /usr/local/bin/findit-entrypoint
RUN sed -i 's/\r$//' /usr/local/bin/findit-entrypoint && chmod +x /usr/local/bin/findit-entrypoint && mkdir -p /data/media /data/mail && chown -R findit:findit /app /data

USER findit
EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/findit-entrypoint"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

