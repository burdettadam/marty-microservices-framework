#!/bin/bash
# MMF Demo Shutdown Script
# Stops all demo services

echo "🛑 Stopping MMF Demo Services"
echo "============================="

# Function to stop a service
stop_service() {
    service_name=$1
    log_name=$(echo "$service_name" | tr ' ' '_' | tr '[:upper:]' '[:lower:]')

    if [ -f "${log_name}.pid" ]; then
        pid=$(cat "${log_name}.pid")
        echo "Stopping $service_name (PID: $pid)..."

        if kill -0 $pid 2>/dev/null; then
            kill $pid
            sleep 2

            # Force kill if still running
            if kill -0 $pid 2>/dev/null; then
                echo "   Force killing $service_name..."
                kill -9 $pid
            fi

            echo "✅ $service_name stopped"
        else
            echo "   ⚠️  $service_name was not running"
        fi

        rm "${log_name}.pid"
        rm -f "${log_name}.log"
    else
        echo "   ⚠️  No PID file found for $service_name"
    fi
}

# Stop all services
stop_service "Order Service"
stop_service "Payment Service"
stop_service "Inventory Service"

echo ""
echo "🧹 Cleaning up temporary files..."
rm -f *.pid
rm -f *.log
rm -f mmf_demo_report_*.json

echo ""
echo "✅ All MMF demo services stopped and cleaned up!"
