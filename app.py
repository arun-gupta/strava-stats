from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import requests
import os
from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objs as go
import plotly.utils
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-change-this')

# Strava API configuration
STRAVA_CLIENT_ID = os.getenv('STRAVA_CLIENT_ID')
STRAVA_CLIENT_SECRET = os.getenv('STRAVA_CLIENT_SECRET')
STRAVA_REDIRECT_URI = 'http://localhost:5000/callback'

class StravaAPI:
    def __init__(self):
        self.base_url = 'https://www.strava.com/api/v3'
    
    def get_auth_url(self):
        """Generate Strava OAuth authorization URL"""
        return (f"https://www.strava.com/oauth/authorize?"
                f"client_id={STRAVA_CLIENT_ID}&"
                f"redirect_uri={STRAVA_REDIRECT_URI}&"
                f"response_type=code&"
                f"scope=read,activity:read")
    
    def exchange_code_for_token(self, code):
        """Exchange authorization code for access token"""
        token_url = 'https://www.strava.com/oauth/token'
        data = {
            'client_id': STRAVA_CLIENT_ID,
            'client_secret': STRAVA_CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code'
        }
        
        response = requests.post(token_url, data=data)
        return response.json()
    
    def get_activities(self, access_token, start_date, end_date, per_page=200):
        """Fetch activities from Strava API"""
        headers = {'Authorization': f'Bearer {access_token}'}
        
        # Convert dates to Unix timestamps
        start_timestamp = int(start_date.timestamp())
        end_timestamp = int(end_date.timestamp())
        
        activities = []
        page = 1
        
        while True:
            params = {
                'after': start_timestamp,
                'before': end_timestamp,
                'per_page': per_page,
                'page': page
            }
            
            response = requests.get(f'{self.base_url}/athlete/activities', 
                                  headers=headers, params=params)
            
            if response.status_code != 200:
                break
                
            page_activities = response.json()
            if not page_activities:
                break
                
            activities.extend(page_activities)
            page += 1
            
            # Strava API rate limit protection
            if len(page_activities) < per_page:
                break
        
        return activities
    
    def get_activity_zones(self, access_token, activity_id):
        """Get heart rate zones for a specific activity"""
        headers = {'Authorization': f'Bearer {access_token}'}
        
        response = requests.get(f'{self.base_url}/activities/{activity_id}/zones',
                              headers=headers)
        
        if response.status_code == 200:
            return response.json()
        return None

strava_api = StravaAPI()

@app.route('/')
def index():
    """Home page"""
    if 'access_token' not in session:
        return render_template('login.html', auth_url=strava_api.get_auth_url())
    return render_template('dashboard.html')

@app.route('/callback')
def callback():
    """Handle Strava OAuth callback"""
    code = request.args.get('code')
    if not code:
        return redirect(url_for('index'))
    
    token_data = strava_api.exchange_code_for_token(code)
    
    if 'access_token' in token_data:
        session['access_token'] = token_data['access_token']
        session['athlete'] = token_data['athlete']
        return redirect(url_for('index'))
    
    return "Authentication failed", 400

@app.route('/logout')
def logout():
    """Logout and clear session"""
    session.clear()
    return redirect(url_for('index'))

@app.route('/analyze', methods=['POST'])
def analyze():
    """Analyze activities for given date range"""
    if 'access_token' not in session:
        return redirect(url_for('index'))
    
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        # Add time to end date to include the full day
        end_date = end_date.replace(hour=23, minute=59, second=59)
        
    except ValueError:
        return "Invalid date format", 400
    
    # Fetch activities
    activities = strava_api.get_activities(session['access_token'], start_date, end_date)
    
    if not activities:
        return render_template('results.html', 
                             message="No activities found in the specified date range.")
    
    # Process activities data
    analysis = process_activities(activities, session['access_token'])
    
    return render_template('results.html', analysis=analysis)

def process_activities(activities, access_token):
    """Process activities data and generate analytics"""
    if not activities:
        return None
        
    df = pd.DataFrame(activities)
    
    # Debug: Print available columns to understand Strava data structure
    print("Available columns in Strava data:", df.columns.tolist())
    if len(activities) > 0:
        print("Sample activity data keys:", list(activities[0].keys()))
    
    # Activity type distribution
    activity_counts = df['type'].value_counts()
    
    # Create pie chart for activity types
    pie_chart = go.Figure(data=[go.Pie(
        labels=activity_counts.index,
        values=activity_counts.values,
        hole=0.3
    )])
    pie_chart.update_layout(title="Activity Types Distribution")
    pie_chart_json = json.dumps(pie_chart, cls=plotly.utils.PlotlyJSONEncoder)
    
    # Calculate running and walking stats
    running_activities = df[df['type'].isin(['Run', 'VirtualRun'])]
    walking_activities = df[df['type'] == 'Walk']
    
    running_distance = running_activities['distance'].sum() / 1609.34 if not running_activities.empty else 0
    walking_distance = walking_activities['distance'].sum() / 1609.34 if not walking_activities.empty else 0
    
    # Calculate total calories - handle different possible field names and missing data
    total_calories = 0
    calories_found = False
    
    # Check for different possible calorie field names in Strava API
    possible_calorie_fields = ['calories', 'kilojoules', 'total_calories']
    
    for field in possible_calorie_fields:
        if field in df.columns:
            print(f"Found calorie field: {field}")
            # Remove NaN values and sum
            field_sum = df[field].fillna(0).sum()
            print(f"Sum for {field}: {field_sum}")
            if field_sum > 0:
                if field == 'kilojoules':
                    # Convert kilojoules to calories (1 kJ ≈ 0.239 calories)
                    total_calories += field_sum * 0.239
                else:
                    total_calories += field_sum
                calories_found = True
    
    # If no calorie data found, estimate based on activity type and duration
    if not calories_found or total_calories == 0:
        print("No calorie data found, estimating...")
        total_calories = estimate_calories_from_activities(df)
        print(f"Estimated calories: {total_calories}")
    
    # Heart rate zones analysis (simplified - would need detailed API calls for each activity)
    zone_analysis = analyze_heart_rate_zones(activities, access_token)
    
    return {
        'pie_chart': pie_chart_json,
        'total_activities': len(activities),
        'running_miles': round(running_distance, 2),
        'walking_miles': round(walking_distance, 2),
        'total_calories': int(round(total_calories)) if total_calories > 0 else None,
        'calories_estimated': not calories_found,
        'activity_breakdown': activity_counts.to_dict(),
        'zone_analysis': zone_analysis
    }

def estimate_calories_from_activities(df):
    """Estimate calories burned based on activity type and duration"""
    # Rough calorie estimates per minute by activity type
    calorie_rates = {
        'Run': 12,
        'VirtualRun': 12,
        'Ride': 8,
        'VirtualRide': 8,
        'Walk': 4,
        'Hike': 6,
        'Swim': 10,
        'Workout': 8,
        'WeightTraining': 6,
        'Yoga': 3,
        'CrossTraining': 10
    }
    
    total_estimated_calories = 0
    
    for _, activity in df.iterrows():
        activity_type = activity.get('type', 'Workout')
        moving_time = activity.get('moving_time', 0)  # in seconds
        
        if moving_time > 0:
            minutes = moving_time / 60
            rate = calorie_rates.get(activity_type, 8)  # default 8 cal/min
            total_estimated_calories += minutes * rate
    
    return total_estimated_calories

def analyze_heart_rate_zones(activities, access_token):
    """Analyze heart rate zones across activities"""
    # This is a simplified version - in practice, you'd need to make API calls
    # for each activity to get detailed zone data
    zone_data = {
        'Zone 1 (Recovery)': 0,
        'Zone 2 (Aerobic)': 0,
        'Zone 3 (Tempo)': 0,
        'Zone 4 (Threshold)': 0,
        'Zone 5 (Anaerobic)': 0
    }
    
    # Sample zone distribution (you would calculate this from actual zone data)
    total_time = sum(activity.get('moving_time', 0) for activity in activities)
    
    if total_time > 0:
        # Simplified zone distribution - replace with actual API calls
        zone_data = {
            'Zone 1 (Recovery)': 25,
            'Zone 2 (Aerobic)': 35,
            'Zone 3 (Tempo)': 20,
            'Zone 4 (Threshold)': 15,
            'Zone 5 (Anaerobic)': 5
        }
    
    return zone_data

if __name__ == '__main__':
    app.run(debug=True, port=5000)
