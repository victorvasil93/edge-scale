.PHONY: proto build up down logs test clean

proto:
	bash scripts/generate_proto.sh

build:
	docker compose build

up:
	docker compose up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f

test:
	docker compose up -d --build
	@echo "Waiting for services to be ready..."
	sleep 5
	cd tests && pip install -q -r requirements.txt && python -m pytest -v .
	docker compose down -v

clean:
	docker compose down -v --rmi local
	rm -f edgescale_pb2.py edgescale_pb2_grpc.py edgescale_pb2.pyi edgescale_pb2_grpc.pyi
