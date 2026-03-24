FROM python:3.12-slim AS base

WORKDIR /app

COPY services/worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proto/ proto/
COPY common/ common/
COPY services/worker/main.py .
COPY services/worker/config.py .
COPY services/worker/text_worker.py .
COPY services/worker/file_worker.py .

RUN python -m grpc_tools.protoc \
    -Iproto \
    --python_out=. \
    --grpc_python_out=. \
    proto/edgescale.proto

CMD ["python", "main.py"]
