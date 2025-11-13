# Strava Stats Web Application

A Python Flask web application that connects to your Strava account and provides detailed analytics about your activities including activity type distribution, time distribution, running distance analysis, elevation tracking, and pace trends.

## Features

- 🔐 Secure Strava OAuth authentication
- 📊 Interactive tabbed charts with 5 views:
  - **Activity Count Distribution**: Pie chart showing activity types with counts and percentages
  - **Time Distribution**: Pie chart showing time spent on each activity type (formatted as hours and minutes)
  - **Run Distance Distribution**: Bar chart with 1-mile bins + running summary card showing:
    - Total Runs
    - 10K+ Runs (6.2 miles or longer)
    - Average Pace (in MM:SS format per mile)
    - Total Miles
  - **Mileage Trend**: Toggle between Daily, Weekly, Monthly running mileage with proper time-series display
  - **Pace Trend**: Toggle between Daily, Weekly, Monthly average pace with continuous line showing rest days at zero
- 📈 Advanced visualizations:
  - Weekly charts show week numbers and start dates on X-axis
  - Monthly charts show month names on X-axis
  - Pace displayed in traditional MM:SS format throughout
- 🏃‍♂️ Running metrics tracking with detailed statistics
- ⛰️ Total elevation gain tracking (in feet)
- ⏱️ Total activity time tracking (formatted as hours and minutes)
- 🎯 Most common activity identification
- 📅 Custom date range selection
- 📱 Responsive web interface with Bootstrap styling

## Output

### Input Page
![Input Page](images/input-page.png)

### Dashboard
![Dashboard](images/dashboard.png)

### Time Distribution
![Time Distribution](images/time-distribution.png)

### Run Distribution
![Run Distribution](images/run-distribution.png)

### Mileage Trend
![Mileage Trend](images/mileage-trend.png)

### Pace Trend
![Pace Trend](images/pace-trend.png)

## Quick Start

Get up and running in 3 steps:

1. **Clone the repository**
   ```bash
   git clone https://github.com/arun-gupta/strava-stats.git
   cd strava-stats
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your Strava credentials
   # Generate FLASK_SECRET_KEY: python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

3. **Run the quickstart script**
   ```bash
   ./quickstart.sh
   ```

That's it! The application will be available at `http://localhost:3000`

The quickstart script automatically:
- Creates virtual environment
- Installs all dependencies
- Validates configuration
- Starts the application

## Manual Setup Instructions

### 1. Create a Strava Application

1. Go to [Strava Developers](https://developers.strava.com/)
2. Click "Create & Manage Your App"
3. Fill in the application details:
   - **Application Name**: Strava Stats
   - **Category**: Data Importer
   - **Club**: Leave blank
   - **Website**: http://localhost:3000
   - **Authorization Callback Domain**: localhost
4. Note down your **Client ID** and **Client Secret**

### 2. Virtual Environment Setup

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

### 3. Configure Environment Variables

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

### 4. Run the Application

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

## Usage

1. **Connect to Strava**: Click the "Connect with Strava" button and authorize the application
2. **Select Date Range**: Choose start and end dates for your analysis
3. **View Results**: Get comprehensive analytics including:
   - **Summary Stats Bar**: Most common activity, running miles, total time (HH:MM format), and elevation gain
   - **Activity Count Distribution**: Pie chart showing activity types with counts and percentages
   - **Time Distribution**: Pie chart showing time spent per activity type in hours and minutes format
   - **Run Distance Distribution**:
     - Bar chart with 1-mile distance bins
     - Running summary card with total runs, 10K+ runs count, total miles, and average pace
   - **Mileage Trend**: Interactive charts showing daily/weekly/monthly running mileage
     - Weekly view shows week numbers and start dates
     - Monthly view shows month names (e.g., "Jan 2024")
   - **Pace Trend**: Interactive charts showing daily/weekly/monthly average pace
     - Pace displayed in MM:SS format (e.g., "9:30" per mile)
     - Daily view shows continuous line dropping to 0 on rest days
     - Hover tooltips show week numbers and date ranges for weekly/monthly views

## API Rate Limits

The application respects Strava's API rate limits:
- 100 requests per 15 minutes
- 1,000 requests per day

For large date ranges with many activities, the app may take some time to fetch all data.

## Known Limitations

- **Activity Type Categorization**: Due to Strava API behavior, some activities may be categorized as "Workout" instead of their specific type (e.g., "WeightTraining"). The application automatically combines "Workout" activities with "WeightTraining" for consistency.

## Troubleshooting

### Common Issues

1. **Authentication Error**: Ensure your Strava app's callback domain is set to `localhost`
2. **No Activities Found**: Check that you have activities in the selected date range
3. **Missing Heart Rate Data**: Zone analysis is estimated if detailed HR data isn't available

### Environment Variables

Make sure all required environment variables are set in your `.env` file:
- `STRAVA_CLIENT_ID`: Your Strava app's client ID
- `STRAVA_CLIENT_SECRET`: Your Strava app's client secret  
- `FLASK_SECRET_KEY`: A random secret key for Flask sessions

## Development

To extend the application:

1. **Add New Metrics**: Modify the `process_activities()` function in `app.py`
2. **Enhance UI**: Update templates in the `templates/` directory
3. **Add Charts**: Use Plotly.js to create additional visualizations

## Security Notes

- Never commit your `.env` file to version control
- Use a strong, random secret key for production deployments
- Consider using environment-specific configuration for production

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

Please respect Strava's API terms of service and rate limits when using this application.
