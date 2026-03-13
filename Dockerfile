FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY rift_github_runner/ rift_github_runner/

RUN pip install --no-cache-dir .

RUN mkdir -p /app/data

EXPOSE 8080

CMD ["gunicorn", "rift_github_runner.main:get_app()", \
     "--bind", "0.0.0.0:8080", \
     "--workers", "1", \
     "--threads", "4", \
     "--access-logfile", "-"]
