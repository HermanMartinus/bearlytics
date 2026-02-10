FROM python:3-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
  curl && \
  rm -rf /var/lib/apt/lists/* && \
  groupadd -g 1000 bear && \
  useradd -u 1000 -g 1000 -m -s /bin/bash bear && \
  mkdir -p /app/data && \
  chown -R bear:bear /app

WORKDIR /app

COPY --chown=bear:bear . .

RUN pip install --no-cache-dir -r requirements.txt && \
  chmod +x docker/entrypoint.sh docker/run.sh

EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=30s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8000/script.js || exit 1
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["/app/docker/run.sh"]
