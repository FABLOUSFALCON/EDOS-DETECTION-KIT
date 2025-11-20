# 🚀 EDoS Security Dashboard - Setup Guide

## Quick Start (5 minutes)

### Prerequisites

- **Python 3.12+**
- **Node.js 18+**
- **Git**

### 1. Clone Repository

```bash
git clone https://github.com/FABLOUSFALCON/EDOS-DETECTION-KIT.git
cd EDOS-DETECTION-KIT
```

### 2. Backend Setup

```bash
cd backend

# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
# or pip install uv

# Install dependencies
uv sync

# Start backend server
python main.py
```

Backend will run on **http://localhost:8000**

### 3. Frontend Setup

```bash
cd .. # Go back to root
npm install
npm run dev
```

Frontend will run on **http://localhost:3000**

## 🗄️ Database Options

### Option A: Use Shared Supabase (Recommended)

- ✅ **Already configured** - just run the backend
- ✅ **No setup needed** - uses shared database
- ✅ **Real-time features** - WebSocket support

### Option B: Local SQLite Development

If you want to use local SQLite instead:

1. **Create `.env` file in backend folder:**

```bash
cd backend
echo "DATABASE_URL=sqlite:///./edos_security.db" > .env
```

2. **Run backend:**

```bash
python main.py
```

SQLite database file (`edos_security.db`) will be created automatically.

## 🛠️ What Happens Automatically

### Backend Startup:

1. ✅ **Database connection** - connects to Supabase or creates SQLite
2. ✅ **Table creation** - creates all required tables
3. ✅ **API endpoints** - all REST APIs available
4. ✅ **WebSocket server** - real-time alerts ready
5. ✅ **CORS setup** - frontend can connect

### Database:

- **SQLite**: Creates `edos_security.db` file locally
- **PostgreSQL**: Connects to Supabase (shared database)
- **Tables**: Auto-created on first run
- **Sample data**: Can generate test alerts

## 🚨 Troubleshooting

### Common Issues:

**"ModuleNotFoundError":**

```bash
cd backend
uv sync  # Reinstall dependencies
```

**"Database connection error":**

```bash
# Check if using SQLite
echo "DATABASE_URL=sqlite:///./edos_security.db" > .env
python main.py
```

**"Port already in use":**

```bash
# Kill existing process
pkill -f "python main.py"
# Or use different port
python main.py --port 8001
```

**Frontend can't connect:**

- ✅ Backend running on port 8000?
- ✅ Frontend running on port 3000?
- ✅ Check browser console for errors

## 🔧 Development Commands

### Backend:

```bash
cd backend

# Start server
python main.py

# Install new package
uv add package-name

# Run tests (when available)
uv run pytest
```

### Frontend:

```bash
# Development server
npm run dev

# Build for production
npm run build

# Install new package
npm install package-name
```

## 📊 Features Available

### ✅ Working Features:

- 🔐 **Authentication system** (Supabase JWT)
- 📊 **Dashboard analytics**
- 🚨 **Security alerts** (real-time via WebSocket)
- 🌐 **Network monitoring** (3D globe visualization)
- 📋 **System logs**
- ⚙️ **Settings management**

### 🏗️ In Development:

- 🤖 **ML threat detection**
- 📈 **Advanced metrics**
- 📱 **Mobile responsiveness**

## 🎯 Next Steps

1. **Start both backend and frontend**
2. **Open http://localhost:3000**
3. **Check authentication flow**
4. **Test real-time alerts**
5. **Explore dashboard features**

---

Need help? Check the logs in terminal or create an issue! 🚀
