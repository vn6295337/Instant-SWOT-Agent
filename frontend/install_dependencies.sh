#!/bin/bash

echo "🚀 Starting frontend dependency installation..."
echo "This may take several minutes depending on your network speed."

echo "📦 Installing core dependencies..."
npm install --no-audit --no-fund

if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed successfully!"
    
    echo "🧪 Running syntax check..."
    npx tsc --noEmit
    
    if [ $? -eq 0 ]; then
        echo "✅ TypeScript compilation successful!"
        
        echo "🚀 Starting development server..."
        npm run dev
    else
        echo "❌ TypeScript compilation failed. Please check for errors."
        exit 1
    fi
else
    echo "❌ Dependency installation failed. Please try again."
    exit 1
fi