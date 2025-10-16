#!/bin/bash

# Simple test runner for the petstore resilience demo
echo "🚀 Starting Petstore Resilience Demo..."
echo "==============================================="

# Check if we're in the correct directory
if [ ! -f "demo_resilience.py" ]; then
    echo "❌ Error: demo_resilience.py not found. Please run from the petstore_domain plugin directory."
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 not found. Please install Python 3.9+."
    exit 1
fi

echo "📋 Environment Check:"
echo "   Python version: $(python3 --version)"
echo "   Working directory: $(pwd)"
echo ""

# Set PYTHONPATH to include the current directory and parent directories
export PYTHONPATH="${PYTHONPATH}:$(pwd):$(pwd)/..:$(pwd)/../.."

echo "🏃 Running resilience demo..."
echo "Note: This demo will show simulated resilience patterns even if the full MMF framework is not available."
echo ""

# Run the demo
python3 demo_resilience.py

echo ""
echo "✅ Demo completed!"
echo "📖 For more information, see docs/RESILIENCE_INTEGRATION.md"
