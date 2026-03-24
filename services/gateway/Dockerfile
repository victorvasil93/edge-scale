FROM python:3.12-slim AS base

WORKDIR /app

COPY services/gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proto/ proto/
COPY common/ common/
COPY services/gateway/main.py .
COPY services/gateway/config.py .

RUN python -m grpc_tools.protoc \
    -Iproto \
    --python_out=. \
    --grpc_python_out=. \
    proto/edgescale.proto

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
