# Manual Setup Instructions

If you prefer to set up the application manually instead of using the quickstart script, follow these detailed steps.

## 1. Create a Strava Application

1. Go to [Strava Developers](https://developers.strava.com/)
2. Click "Create & Manage Your App"
3. Fill in the application details:
   - **Application Name**: Strava Stats
   - **Category**: Data Importer
   - **Club**: Leave blank
   - **Website**: http://localhost:3000
   - **Authorization Callback Domain**: localhost
4. Note down your **Client ID** and **Client Secret**

## 2. Virtual Environment Setup

**Create the virtual environment:**
```bash
cd strava-stats
python3 -m venv venv
```

**Activate the virtual environment:**
```bash
source activate.sh
```

**Or manually:**
```bash
source venv/bin/activate
```

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**To deactivate when done:**
```bash
deactivate
```

## 3. Configure Environment Variables

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Generate a Flask secret key:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

3. Edit `.env` and add your Strava credentials and the generated secret key:
```
STRAVA_CLIENT_ID=your_actual_client_id
STRAVA_CLIENT_SECRET=your_actual_client_secret
FLASK_SECRET_KEY=your_generated_secret_key_here
```

## 4. Run the Application

**Option 1: Quick Start (Recommended)**
```bash
./quickstart.sh
```
This script handles everything: creates venv, installs dependencies, and starts the app.

**Option 2: Run script (if already set up)**
```bash
./run.sh
```
Stops any existing Flask processes and starts a new one.

**Option 3: Manual**
```bash
source venv/bin/activate
python app.py
```

The application will be available at `http://localhost:3000`

## Environment Variables Reference

Make sure all required environment variables are set in your `.env` file:
- `STRAVA_CLIENT_ID`: Your Strava app's client ID
- `STRAVA_CLIENT_SECRET`: Your Strava app's client secret
- `FLASK_SECRET_KEY`: A random secret key for Flask sessions
