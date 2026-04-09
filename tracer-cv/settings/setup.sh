#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# TRASSIR Dashboard — Setup for Vercel
# Запуск: bash setup.sh
# ═══════════════════════════════════════════════════════════════

set -e

echo "📦 Создаю проект trassir-dashboard..."

mkdir -p trassir-dashboard/src
cd trassir-dashboard

# ─── package.json ───────────────────────────────────────────
cat > package.json << 'EOF'
{
  "name": "trassir-dashboard",
  "private": true,
  "version": "1.0.0",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "recharts": "^2.12.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.0",
    "vite": "^5.0.0"
  }
}
EOF

# ─── vite.config.js ────────────────────────────────────────
cat > vite.config.js << 'EOF'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
export default defineConfig({ plugins: [react()] })
EOF

# ─── index.html ─────────────────────────────────────────────
cat > index.html << 'EOF'
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>TRASSIR Инфоцентр</title>
  <style>body{margin:0;padding:0}</style>
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/main.jsx"></script>
</body>
</html>
EOF

# ─── src/main.jsx ───────────────────────────────────────────
cat > src/main.jsx << 'EOF'
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
ReactDOM.createRoot(document.getElementById('root')).render(<App />)
EOF

echo "✅ Структура создана!"
echo ""
echo "Теперь:"
echo "  1. Скопируй infocenter_dashboard_v7.jsx → trassir-dashboard/src/App.jsx"
echo "  2. cd trassir-dashboard"
echo "  3. npm install"
echo "  4. npm run dev        — проверить локально"
echo "  5. npx vercel          — задеплоить"