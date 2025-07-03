# Strava Stats Web Application

A Python Flask web application that connects to your Strava account and provides detailed analytics about your activities including activity type distribution, running/walking mileage, calories burned, and heart rate zone analysis.

## Features

- 🔐 Secure Strava OAuth authentication
- 📊 Interactive pie chart of activity types
- 🏃‍♂️ Running and walking mileage tracking
- 🔥 Calories burned analysis
- 💓 Heart rate zone distribution
- 📅 Custom date range selection
- 📱 Responsive web interface

## Setup Instructions

### 1. Create a Strava Application

1. Go to [Strava Developers](https://developers.strava.com/)
2. Click "Create & Manage Your App"
3. Fill in the application details:
   - **Application Name**: Strava Stats
   - **Category**: Data Importer
   - **Club**: Leave blank
   - **Website**: http://localhost:5000
   - **Authorization Callback Domain**: localhost
4. Note down your **Client ID** and **Client Secret**

### 2. Virtual Environment Setup (Already Done!)

The project is already set up with a Python virtual environment. All dependencies are installed and ready to use.

**To activate the virtual environment:**
```bash
cd strava-stats
source activate.sh
```

**Or manually:**
```bash
cd strava-stats
source venv/bin/activate
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

2. Edit `.env` and add your Strava credentials:
```
STRAVA_CLIENT_ID=your_actual_client_id
STRAVA_CLIENT_SECRET=your_actual_client_secret
FLASK_SECRET_KEY=your_random_secret_key_here
```

### 4. Run the Application

**With virtual environment activated:**
```bash
python app.py
```

The application will be available at `http://localhost:5000`

## Usage

1. **Connect to Strava**: Click the "Connect with Strava" button and authorize the application
2. **Select Date Range**: Choose start and end dates for your analysis
3. **View Results**: Get comprehensive analytics including:
   - Activity type distribution pie chart
   - Running and walking mileage summary
   - Calories burned (if available in your activities)
   - Heart rate zone breakdown
   - Key insights and recommendations

## API Rate Limits

The application respects Strava's API rate limits:
- 100 requests per 15 minutes
- 1,000 requests per day

For large date ranges with many activities, the app may take some time to fetch all data.

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

This project is for educational purposes. Please respect Strava's API terms of service and rate limits.
