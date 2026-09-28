# Combined image: admin_bot + user_bot + webhook, supervised by run_all.py.
#
# The per-bot Dockerfiles (admin_bot/Dockerfile, user_bot/Dockerfile) still
# exist and still work -- they're what the `separate` compose profile builds
# when you want to restart one bot without touching the others. This image is
# the single-service alternative.
FROM python:3.11-slim

# postgresql-client supplies pg_dump, used by admin_bot's daily backup job.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
COPY shared/ ./shared/
RUN pip install --no-cache-dir -r requirements.txt

COPY admin_bot/ ./admin_bot/
COPY user_bot/ ./user_bot/
COPY run_all.py ./

CMD ["python", "run_all.py"]
