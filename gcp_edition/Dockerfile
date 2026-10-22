FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt gcp_edition/requirements-gcp.txt /srv/
RUN pip install --no-cache-dir -r requirements.txt -r requirements-gcp.txt
COPY app /srv/app
COPY gcp_edition /srv/gcp_edition
ENV PYTHONUNBUFFERED=1 PORT=8080
USER 65532:65532
CMD ["sh", "-c", "exec uvicorn gcp_edition.api:app --host 0.0.0.0 --port ${PORT:-8080}"]
