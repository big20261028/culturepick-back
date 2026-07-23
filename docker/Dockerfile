FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 시스템 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system culturepick && adduser --system --ingroup culturepick culturepick

# Python 의존성
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/local.txt 
# RUN pip install --no-cache-dir -r requirements/production.txt 

COPY . .

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown -R culturepick:culturepick /app

USER culturepick

ENTRYPOINT ["/entrypoint.sh"]
