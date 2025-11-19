#!/bin/bash

# DefectDojo Frontend Setup Script

set -e

echo "🚀 Setting up DefectDojo Modern Frontend..."
echo ""

# Check Node.js version
required_node_version="18"
current_node_version=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)

if [ "$current_node_version" -lt "$required_node_version" ]; then
    echo "❌ Error: Node.js $required_node_version or higher is required"
    echo "   Current version: $(node -v)"
    echo "   Please upgrade Node.js: https://nodejs.org/"
    exit 1
fi

echo "✅ Node.js version OK: $(node -v)"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
npm install

echo ""
echo "✅ Setup complete!"
echo ""
echo "Available commands:"
echo "  npm run dev        - Start development server"
echo "  npm run build      - Build for production"
echo "  npm run lint       - Lint JavaScript"
echo "  npm run format     - Format code with Prettier"
echo ""
echo "Development server will be available at: http://localhost:3000"
echo "Django backend should be running at: http://localhost:8080"
echo ""
