FROM python:3.12-slim AS base

WORKDIR /app

COPY services/ingestion/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proto/ proto/
COPY common/ common/
COPY services/ingestion/main.py .

RUN python -m grpc_tools.protoc \
    -Iproto \
    --python_out=. \
    --grpc_python_out=. \
    proto/edgescale.proto

EXPOSE 50051
CMD ["python", "main.py"]
