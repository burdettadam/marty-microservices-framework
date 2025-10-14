#!/bin/bash
# MMF Demo Startup Script
# Starts all required services for the demonstration

echo "🚀 Starting MMF Demo Services"
echo "=============================="

# Function to check if a port is in use
check_port() {
    port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
        echo "⚠️  Port $port is already in use"
        return 1
    else
        return 0
    fi
}

# Function to start a service in the background
start_service() {
    service_name=$1
    service_file=$2
    port=$3
    log_name=$(echo "$service_name" | tr ' ' '_' | tr '[:upper:]' '[:lower:]')

    echo "Starting $service_name on port $port..."

    if check_port $port; then
        # Start the service in background
        uv run $service_file > ${log_name}.log 2>&1 &
        service_pid=$!
        echo "✅ $service_name started (PID: $service_pid, Port: $port)"
        echo $service_pid > ${log_name}.pid

        # Give the service a moment to start
        sleep 2

        # Check if service is actually running
        if kill -0 $service_pid 2>/dev/null; then
            echo "   Status: Running"
        else
            echo "   ❌ Failed to start $service_name"
            return 1
        fi
    else
        echo "   ⚠️  Skipping $service_name - port $port already in use"
    fi
}

# Check if uv is available
if ! command -v uv &> /dev/null; then
    echo "❌ Error: 'uv' command not found"
    echo "Please install uv first: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "📦 Checking dependencies..."
uv sync

echo ""
echo "🔄 Starting services..."

# Start all services
start_service "Order Service" "mmf_order_service.py" 8001
start_service "Payment Service" "mmf_payment_service.py" 8002
start_service "Inventory Service" "mmf_inventory_service.py" 8003

echo ""
echo "🔍 Service Status Check:"
echo "========================"

# Check service health
for service in "Order Service" "Payment Service" "Inventory Service"; do
    log_name=$(echo "$service" | tr ' ' '_' | tr '[:upper:]' '[:lower:]')
    if [ -f "${log_name}.pid" ]; then
        pid=$(cat "${log_name}.pid")
        if kill -0 $pid 2>/dev/null; then
            echo "✅ $service: Running (PID: $pid)"
        else
            echo "❌ $service: Not running"
        fi
    else
        echo "❌ $service: PID file not found"
    fi
done

echo ""
echo "🌐 Service Endpoints:"
echo "===================="
echo "📦 Order Service:     http://localhost:8001"
echo "   - Health:          http://localhost:8001/health"
echo "   - Metrics:         http://localhost:8001/metrics"
echo "   - Create Order:    POST http://localhost:8001/orders/create"
echo ""
echo "💳 Payment Service:   http://localhost:8002"
echo "   - Health:          http://localhost:8002/health"
echo "   - Metrics:         http://localhost:8002/metrics"
echo "   - Process Payment: POST http://localhost:8002/payments/process"
echo ""
echo "📦 Inventory Service: http://localhost:8003"
echo "   - Health:          http://localhost:8003/health"
echo "   - Metrics:         http://localhost:8003/metrics"
echo "   - Check Stock:     GET http://localhost:8003/inventory/check/{product_id}"
echo ""

echo "📊 Observability (if Kind cluster is running):"
echo "=============================================="
echo "📈 Prometheus:  http://localhost:9090"
echo "📊 Grafana:     http://localhost:3000"
echo ""

echo "🧪 Running the Demo:"
echo "==================="
echo "To run the comprehensive demo, execute:"
echo "   uv run mmf_demo_runner.py"
echo ""
echo "To stop all services, run:"
echo "   ./stop_demo.sh"
echo ""

echo "✅ MMF Demo environment is ready!"
echo "Logs are available in:"
for service in "Order Service" "Payment Service" "Inventory Service"; do
    log_name=$(echo "$service" | tr ' ' '_' | tr '[:upper:]' '[:lower:]')
    echo "   - ${log_name}.log"
done
