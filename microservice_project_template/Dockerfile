FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install uv
RUN pip install uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./
COPY README.md ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy source code
COPY src ./src
COPY proto ./proto

# Generate protobuf files
RUN uv run python -m grpc_tools.protoc \
    --proto_path=proto \
    --python_out=src/microservice_template/proto \
    --grpc_python_out=src/microservice_template/proto \
    proto/greeter.proto

# Fix the import in the generated gRPC file to use relative imports
RUN sed -i 's/^import greeter_pb2 as greeter__pb2$/from . import greeter_pb2 as greeter__pb2/' src/microservice_template/proto/greeter_pb2_grpc.py

EXPOSE 50051 9000 8080

# Use uv to run the application
ENTRYPOINT ["uv", "run", "python", "-m", "microservice_template.main"]
CMD ["serve"]
