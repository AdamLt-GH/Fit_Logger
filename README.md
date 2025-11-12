# Core Workflow: Setup and Run

This guide covers the essential steps to run the Fitness Web Logger App, including backend, frontend, Redis setup, and running test cases.

Note: New dependencies `redis`, `bleach`, `pytest` have been added. Make sure to update your environment and install them before running the app or tests.

---

## 1. Backend Setup (Django)

### 1.1 Create and activate a virtual environment
python3 -m venv env
source env/bin/activate   # Linux / macOS
# OR on Windows:
# .\env\Scripts\activate

### 1.2 Install dependencies
pip install -r requirements.txt
Make sure to rerun this whenever requirements.txt is updated (e.g., after adding redis or bleach).

### 1.3 Start Redis
Redis is required for caching and for running test cases. It must be running before running tests.

macOS (brew)
brew services start redis

Linux
sudo service redis-server start

Windows (if installed manually)
redis-server

### 1.4 Run database migrations
python manage.py makemigrations
python manage.py migrate


### 1.5 Set up Weather API (Optional)
To enable weather functionality, you need to:
1. Get a free API key from [WeatherAPI.com](https://www.weatherapi.com/my/)
2. Create a `.env` file in the project root with:
   ```
   WEATHERAPI_API_KEY=your-api-key-here
   ```
3. Or set the environment variable directly

### 1.6 Start Django development server
python manage.py runserver

---

## 2. Frontend Setup (React + Vite)

### 2.1 Navigate to frontend folder
cd frontend

### 2.2 Install dependencies
npm install

### 2.3 Start the Vite development server
npm run dev

Backend and frontend servers can run concurrently in separate terminals.

---

## 3. Running Test Cases (Pytest)

### 3.1 Ensure Redis is running
Redis must be running before running test cases.

macOS
brew services start redis

Linux
sudo service redis-server start

Windows
redis-server

### 3.2 Run the test suite
pytest -v

This will run all backend test cases, including serializers, models, and views. The -v flag stands for verbose, showing the name and status of each test.

---

## Notes
- IMPORTANT: Overwrite existing migrations with my new migrations
- Any updates to requirements.txt (like redis or bleach) must be installed before running servers or tests.
- Redis must always be started before running test cases to avoid failures in caching or task-related tests.
- Backend and frontend servers can run concurrently in separate terminals.
- Make sure the virtual environment is active whenever running Django or Python commands.
