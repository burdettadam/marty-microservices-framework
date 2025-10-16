#!/bin/bash
# MMF Demo Launcher
# Quick access to all MMF demonstrations

set -e

echo "🚀 Marty Microservices Framework - Demo Launcher"
echo "=================================================="
echo

# Check if we're in the right directory
if [ ! -f "quick_start_demo.py" ]; then
    echo "❌ Please run this script from the examples/demos directory"
    exit 1
fi

# Function to show available demos
show_demos() {
    echo "📋 Available Demonstrations:"
    echo
    echo "  1. 🚀 Quick Start (5 min)         - python quick_start_demo.py"
    echo "  2. 🎯 Feature Demos (15-45 min)   - python runner/petstore_demo_runner.py --list"
    echo "  3. 🏪 Petstore Domain (2-3 hours) - cd petstore_domain/"
    echo
    echo "💡 Examples:"
    echo "   ./demo_launcher.sh quick          # Run quick start"
    echo "   ./demo_launcher.sh feature core   # Run core framework demo"
    echo "   ./demo_launcher.sh petstore       # Enter petstore domain"
    echo "   ./demo_launcher.sh list           # Show detailed demo list"
    echo
}

# Main command handling
case "${1:-help}" in
    "quick"|"start")
        echo "🚀 Starting Quick Demo..."
        python3 quick_start_demo.py ${2:+--verbose}
        ;;

    "feature")
        if [ -z "$2" ]; then
            echo "📋 Available feature demos:"
            python3 mmf_demos.py --list
        else
            echo "🎯 Running feature demo: $2"
            python3 mmf_demos.py --demo "$2"
        fi
        ;;

    "petstore")
        echo "🏪 Entering Petstore Domain..."
        echo "💡 Available commands in petstore_domain/:"
        echo "   python experience_polish_demo.py --scenario quick"
        echo "   python dev/experience_polish_demo.py --scenario ml-demo"
        echo "   bash working_demo.sh"
        echo
        cd petstore_domain
        exec $SHELL
        ;;

    "list")
        python3 mmf_demos.py --list
        echo
        echo "🏪 Petstore Domain Commands:"
        echo "   cd petstore_domain"
        echo "   python experience_polish_demo.py --scenario quick"
        echo "   python dev/experience_polish_demo.py --scenario ml-demo"
        ;;

    "all")
        echo "🎯 Running ALL demos (this will take 45-60 minutes)..."
        if [ "$2" = "--confirm" ]; then
            python3 mmf_demos.py --demo all
        else
            echo "⚠️  This will run all demos and take significant time."
            echo "💡 Use: ./demo_launcher.sh all --confirm"
        fi
        ;;

    "help"|*)
        show_demos
        ;;
esac
