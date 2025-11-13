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

# Configure session to be less restrictive for localhost development
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Strava API configuration
STRAVA_CLIENT_ID = os.getenv('STRAVA_CLIENT_ID')
STRAVA_CLIENT_SECRET = os.getenv('STRAVA_CLIENT_SECRET')
STRAVA_PORT = int(os.getenv('FLASK_PORT', '3000'))
STRAVA_REDIRECT_URI = f'http://localhost:{STRAVA_PORT}/callback'

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
    print("=" * 50)
    print("CALLBACK ROUTE HIT!")
    print(f"Request args: {request.args}")
    print(f"Full URL: {request.url}")
    print("=" * 50)

    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        print(f"OAuth error: {error}")
        return f"Authentication error: {error}", 400

    if not code:
        print("No code received")
        return redirect(url_for('index'))

    print(f"Exchanging code: {code[:10]}...")
    token_data = strava_api.exchange_code_for_token(code)
    print(f"Token response: {token_data}")

    if 'access_token' in token_data:
        session['access_token'] = token_data['access_token']
        session['athlete'] = token_data['athlete']
        print("Authentication successful!")
        return redirect(url_for('index'))

    print("Authentication failed - no access token")
    return f"Authentication failed: {token_data}", 400

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
                             message="No activities found in the specified date range.",
                             start_date=start_date_str,
                             end_date=end_date_str)
    
    # Process activities data
    analysis = process_activities(activities, session['access_token'])
    
    # Add date range to analysis results
    analysis['start_date'] = start_date_str
    analysis['end_date'] = end_date_str
    analysis['date_range_formatted'] = f"{start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}"
    
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

    # Show which activities are categorized as "Workout" before normalization
    workout_activities = df[df['type'] == 'Workout']
    if not workout_activities.empty:
        print("\n" + "="*50)
        print("Activities categorized as 'Workout':")
        for idx, activity in workout_activities.iterrows():
            activity_name = activity.get('name', 'Unnamed')
            activity_date = activity.get('start_date', 'Unknown date')
            activity_id = activity.get('id', 'No ID')
            print(f"  - {activity_name} (Date: {activity_date}, ID: {activity_id})")
        print("="*50 + "\n")

    # Normalize activity types - combine similar activities
    df['type'] = df['type'].replace({
        'Workout': 'WeightTraining',  # Combine Workout with WeightTraining
        'VirtualRun': 'Run',  # Combine VirtualRun with Run
        'VirtualRide': 'Ride'  # Combine VirtualRide with Ride
    })

    # Activity type distribution
    activity_counts = df['type'].value_counts()

    print("="*50)
    print("Activity counts:")
    print(activity_counts)
    print(f"Labels: {list(activity_counts.index)}")
    print(f"Values: {list(activity_counts.values)}")
    print("\nAll unique activity types:")
    print(df['type'].unique())
    print("="*50)

    # Create pie chart for activity types
    pie_chart = go.Figure(data=[go.Pie(
        labels=list(activity_counts.index),
        values=list(activity_counts.values),
        hole=0.3
    )])
    pie_chart.update_layout(title="Activity Types Distribution")
    pie_chart_json = json.dumps(pie_chart, cls=plotly.utils.PlotlyJSONEncoder)

    print(f"Pie chart JSON length: {len(pie_chart_json)}")

    # Calculate total duration
    total_duration_seconds = df['moving_time'].sum() if 'moving_time' in df.columns else 0
    total_duration_hours = total_duration_seconds / 3600
    print(f"Total duration: {total_duration_hours:.2f} hours ({total_duration_seconds} seconds)")

    # Calculate duration by activity type for pie chart
    duration_by_type = df.groupby('type')['moving_time'].sum() if 'moving_time' in df.columns else pd.Series()

    # Create duration pie chart
    duration_pie_chart = go.Figure(data=[go.Pie(
        labels=list(duration_by_type.index),
        values=list(duration_by_type.values / 3600),  # Convert to hours
        hole=0.3,
        texttemplate='%{label}<br>%{value:.1f}h (%{percent})',
        textposition='auto'
    )])
    duration_pie_chart.update_layout(title="Time Distribution by Activity Type")
    duration_pie_chart_json = json.dumps(duration_pie_chart, cls=plotly.utils.PlotlyJSONEncoder)

    # Calculate running stats and distance distribution
    running_activities = df[df['type'] == 'Run']

    running_distance = running_activities['distance'].sum() / 1609.34 if not running_activities.empty else 0

    # Create running distance distribution (group by mile ranges)
    run_distance_distribution = {}
    if not running_activities.empty:
        running_distances_miles = running_activities['distance'] / 1609.34

        # Define distance bins (in miles)
        bins = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, float('inf')]
        labels = ['0-1', '1-2', '2-3', '3-4', '4-5', '5-6', '6-7', '7-8', '8-9', '9-10', '10+']

        # Categorize runs into bins
        distance_categories = pd.cut(running_distances_miles, bins=bins, labels=labels, right=False)
        run_distance_distribution = distance_categories.value_counts().sort_index().to_dict()

        print("Run distance distribution:", run_distance_distribution)

    # Calculate total elevation gain
    total_elevation = df['total_elevation_gain'].sum() if 'total_elevation_gain' in df.columns else 0
    total_elevation_feet = total_elevation * 3.28084  # Convert meters to feet
    print(f"Total elevation: {total_elevation_feet:.2f} feet")

    # Heart rate zones analysis (simplified - would need detailed API calls for each activity)
    zone_analysis = analyze_heart_rate_zones(activities, access_token)

    return {
        'pie_chart': pie_chart_json,
        'duration_pie_chart': duration_pie_chart_json,
        'total_activities': len(activities),
        'running_miles': round(running_distance, 2),
        'total_elevation_feet': round(total_elevation_feet, 2),
        'total_duration_hours': round(total_duration_hours, 2),
        'activity_breakdown': activity_counts.to_dict(),
        'run_distance_distribution': run_distance_distribution,
        'zone_analysis': zone_analysis
    }

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
    app.run(debug=True, host='0.0.0.0', port=STRAVA_PORT)
