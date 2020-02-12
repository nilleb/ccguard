# Stage 1
FROM python:3.7 as build

COPY requirements.txt .

RUN pip3 wheel --no-cache-dir --no-deps --wheel-dir /wheels -r requirements.txt
