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
    error = request.args.get('error')

    if error:
        return f"Authentication error: {error}", 400

    if not code:
        return redirect(url_for('index'))

    token_data = strava_api.exchange_code_for_token(code)

    if 'access_token' in token_data:
        session['access_token'] = token_data['access_token']
        session['athlete'] = token_data['athlete']
        return redirect(url_for('index'))

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

    # Normalize activity types - combine similar activities
    df['type'] = df['type'].replace({
        'Workout': 'WeightTraining',  # Combine Workout with WeightTraining
        'VirtualRun': 'Run',  # Combine VirtualRun with Run
        'VirtualRide': 'Ride'  # Combine VirtualRide with Ride
    })

    # Activity type distribution
    activity_counts = df['type'].value_counts()

    # Create pie chart for activity types
    pie_chart = go.Figure(data=[go.Pie(
        labels=list(activity_counts.index),
        values=list(activity_counts.values),
        hole=0.3,
        texttemplate='%{label}<br>%{value} (%{percent})',
        textposition='inside',
        insidetextorientation='horizontal'
    )])
    pie_chart.update_layout(title="Activity Types Distribution")
    pie_chart_json = json.dumps(pie_chart, cls=plotly.utils.PlotlyJSONEncoder)

    # Calculate total duration
    total_duration_seconds = df['moving_time'].sum() if 'moving_time' in df.columns else 0
    total_duration_hours = int(total_duration_seconds // 3600)
    total_duration_minutes = int((total_duration_seconds % 3600) // 60)
    total_duration_formatted = f"{total_duration_hours}h {total_duration_minutes}m"

    # Calculate duration by activity type for pie chart
    duration_by_type = df.groupby('type')['moving_time'].sum() if 'moving_time' in df.columns else pd.Series()

    # Create duration pie chart with formatted time labels
    duration_labels = []
    duration_values = []
    duration_text = []

    for activity_type, seconds in duration_by_type.items():
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        time_str = f"{hours}h {minutes}m"

        duration_labels.append(activity_type)
        duration_values.append(seconds / 3600)  # Keep as hours for proper percentage calculation
        duration_text.append(time_str)

    duration_pie_chart = go.Figure(data=[go.Pie(
        labels=duration_labels,
        values=duration_values,
        hole=0.3,
        text=duration_text,
        texttemplate='%{label}<br>%{text} (%{percent})',
        textposition='inside',
        insidetextorientation='horizontal'
    )])
    duration_pie_chart.update_layout(title="Time Distribution by Activity Type")
    duration_pie_chart_json = json.dumps(duration_pie_chart, cls=plotly.utils.PlotlyJSONEncoder)

    # Calculate running stats and distance distribution
    running_activities = df[df['type'] == 'Run']

    running_distance = running_activities['distance'].sum() / 1609.34 if not running_activities.empty else 0

    # Create running distance distribution (group by mile ranges)
    run_distance_distribution = {}
    runs_10k_plus = 0
    total_runs = 0
    avg_pace_formatted = "0:00"
    if not running_activities.empty:
        running_distances_miles = running_activities['distance'] / 1609.34
        total_runs = len(running_activities)

        # Calculate average pace (minutes per mile)
        # moving_time is in seconds, distance is in meters
        avg_pace_formatted = "0:00"
        if 'moving_time' in running_activities.columns and running_distance > 0:
            total_time_seconds = running_activities['moving_time'].sum()
            avg_pace_seconds_per_mile = total_time_seconds / running_distance
            pace_minutes = int(avg_pace_seconds_per_mile // 60)
            pace_seconds = int(avg_pace_seconds_per_mile % 60)
            avg_pace_formatted = f"{pace_minutes}:{pace_seconds:02d}"

        # Define distance bins (in miles)
        bins = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, float('inf')]
        labels = ['0-1', '1-2', '2-3', '3-4', '4-5', '5-6', '6-7', '7-8', '8-9', '9-10', '10+']

        # Categorize runs into bins
        distance_categories = pd.cut(running_distances_miles, bins=bins, labels=labels, right=False)
        run_distance_distribution = distance_categories.value_counts().sort_index().to_dict()

        # Count runs 10K or longer (10K = 6.2 miles)
        runs_10k_plus = len(running_distances_miles[running_distances_miles >= 6.2])

    # Calculate total elevation gain
    total_elevation = df['total_elevation_gain'].sum() if 'total_elevation_gain' in df.columns else 0
    total_elevation_feet = total_elevation * 3.28084  # Convert meters to feet

    # ==============================
    # Mileage trend (daily/weekly/monthly)
    # ==============================
    mileage_trend_daily_json = None
    mileage_trend_weekly_json = None
    mileage_trend_monthly_json = None

    # ==============================
    # Pace trend (daily/weekly/monthly)
    # ==============================
    pace_trend_daily_json = None
    pace_trend_weekly_json = None
    pace_trend_monthly_json = None

    try:
        if not running_activities.empty:
            # Ensure start_date is datetime
            if 'start_date' in running_activities.columns:
                ra = running_activities.copy()
                ra['start_date'] = pd.to_datetime(ra['start_date'])
                # Distance in miles
                ra['distance_mi'] = ra.get('distance', 0) / 1609.34
                ra = ra.set_index('start_date').sort_index()

                # Daily aggregate (non-cumulative) as line graph
                # Build an explicit daily date index and reindex to avoid any implicit behavior
                daily_index = pd.date_range(ra.index.min().normalize(), ra.index.max().normalize(), freq='D')
                daily = (ra['distance_mi']
                         .groupby(pd.Grouper(freq='D'))
                         .sum()
                         .reindex(daily_index, fill_value=0))
                # Use ISO strings for dates to avoid any serialization quirks
                x_daily = [d.strftime('%Y-%m-%d') for d in daily.index]
                y_daily = [float(v) for v in daily.values]
                daily_fig = go.Figure([
                    go.Scatter(
                        x=x_daily,
                        y=y_daily,
                        mode='lines+markers',
                        line=dict(color="#4e79a7"),
                        marker=dict(size=6),
                        hovertemplate='%{x|%Y-%m-%d}<br>%{y:.2f} mi<extra></extra>'
                    )
                ])
                daily_fig.update_layout(
                    title="Daily Running Mileage",
                    xaxis_title="Day",
                    yaxis_title="Miles",
                    yaxis=dict(rangemode='tozero'),
                    # Ensure the daily chart actually shows daily ticks, so it doesn't look like weekly
                    xaxis=dict(
                        dtick="D1",
                        tickformat="%b %d"
                    )
                )
                mileage_trend_daily_json = json.dumps(daily_fig, cls=plotly.utils.PlotlyJSONEncoder)

                # Weekly aggregate (Mon-Sun by default with 'W-MON') as line graph
                weekly = (ra['distance_mi']
                          .groupby(pd.Grouper(freq='W-MON'))
                          .sum())
                # Filter out zero values and create labels
                weekly = weekly[weekly > 0] if len(weekly) > 0 else weekly
                # Create week labels with start date (e.g., "Nov 4")
                x_weekly = [d.strftime('%b %d') for d in weekly.index]
                y_weekly = [float(v) for v in weekly.values]
                # Create hover data with week number and full date range
                week_numbers = [d.isocalendar()[1] for d in weekly.index]  # ISO week number
                week_end_dates = [(d + timedelta(days=6)).strftime('%b %d, %Y') for d in weekly.index]
                hover_text = [f"Week {wk} of {d.year}<br>{d.strftime('%b %d')} - {end}<br>{miles:.2f} mi"
                             for wk, d, end, miles in zip(week_numbers, weekly.index, week_end_dates, y_weekly)]
                weekly_fig = go.Figure([
                    go.Scatter(
                        x=x_weekly,
                        y=y_weekly,
                        mode='lines+markers',
                        line=dict(color="#59a14f"),
                        marker=dict(size=8),
                        text=hover_text,
                        hovertemplate='%{text}<extra></extra>'
                    )
                ])
                weekly_fig.update_layout(
                    title="Weekly Running Mileage",
                    xaxis_title="Week Start Date",
                    yaxis_title="Miles",
                    yaxis=dict(rangemode='tozero'),
                    xaxis=dict(type='category')
                )
                mileage_trend_weekly_json = json.dumps(weekly_fig, cls=plotly.utils.PlotlyJSONEncoder)

                # Monthly aggregate as line graph
                monthly = (ra['distance_mi']
                           .groupby(pd.Grouper(freq='MS'))
                           .sum())
                # Filter out zero values
                monthly = monthly[monthly > 0] if len(monthly) > 0 else monthly
                # Create month labels like "Jan 2024", "Feb 2024", etc.
                x_monthly = [d.strftime('%b %Y') for d in monthly.index]
                y_monthly = [float(v) for v in monthly.values]
                monthly_fig = go.Figure([
                    go.Scatter(
                        x=x_monthly,
                        y=y_monthly,
                        mode='lines+markers',
                        line=dict(color="#f28e2c"),
                        marker=dict(size=8),
                        hovertemplate='%{x}<br>%{y:.2f} mi<extra></extra>'
                    )
                ])
                monthly_fig.update_layout(
                    title="Monthly Running Mileage",
                    xaxis_title="Month",
                    yaxis_title="Miles",
                    yaxis=dict(rangemode='tozero'),
                    xaxis=dict(type='category')
                )
                mileage_trend_monthly_json = json.dumps(monthly_fig, cls=plotly.utils.PlotlyJSONEncoder)

                # ==============================
                # Pace trend calculations
                # ==============================
                # Calculate pace for each run (seconds per mile)
                # Avoid division by zero by replacing zero distances with NaN
                ra['pace_sec_per_mi'] = ra['moving_time'] / (ra['distance_mi'].replace(0, float('nan')))
                ra['pace_sec_per_mi'] = ra['pace_sec_per_mi'].fillna(0)

                # Convert pace to MM:SS format for display
                def pace_to_mmss(pace_seconds):
                    mins = int(pace_seconds // 60)
                    secs = int(pace_seconds % 60)
                    return f"{mins}:{secs:02d}"

                # Daily average pace - create complete dataset with all days
                # Group by date and calculate mean pace, normalizing the index
                daily_pace_with_runs = ra['pace_sec_per_mi'].groupby(ra.index.normalize()).mean()

                # Now create complete lists for ALL days in the range
                x_daily_pace = []
                y_daily_pace = []
                hover_text_daily_pace = []

                for date in daily_index:
                    x_daily_pace.append(date)

                    if date in daily_pace_with_runs.index:
                        pace = daily_pace_with_runs[date]
                        y_daily_pace.append(float(pace))
                        hover_text_daily_pace.append(f"{date.strftime('%b %d')}<br>Pace: {pace_to_mmss(pace)}")
                    else:
                        y_daily_pace.append(0.0)  # Explicitly 0.0 for non-running days
                        hover_text_daily_pace.append(f"{date.strftime('%b %d')}<br>No run")

                daily_pace_fig = go.Figure([
                    go.Scatter(
                        x=x_daily_pace,
                        y=y_daily_pace,
                        mode='lines+markers',
                        line=dict(color="#e15759", width=2),
                        marker=dict(size=5, symbol='circle'),
                        text=hover_text_daily_pace,
                        hovertemplate='%{text}<extra></extra>'
                    )
                ])

                daily_pace_fig.update_layout(
                    title="Daily Average Pace",
                    xaxis_title="Day",
                    yaxis_title="Pace (min/mile)",
                    yaxis=dict(
                        rangemode='tozero',
                        tickmode='array',
                        tickvals=[0] + [i * 60 for i in range(6, 15)],
                        ticktext=['0:00'] + [f"{i}:00" for i in range(6, 15)]
                    ),
                    xaxis=dict(
                        type='date',
                        tickformat='%b %d',
                        tickangle=-45,
                        dtick=86400000,  # 1 day in milliseconds - show every day
                        range=[daily_index[0], daily_index[-1]]  # Ensure full range is shown
                    ),
                    hovermode='x unified'
                )
                pace_trend_daily_json = json.dumps(daily_pace_fig, cls=plotly.utils.PlotlyJSONEncoder)

                # Weekly average pace
                weekly_pace = (ra['pace_sec_per_mi']
                              .groupby(pd.Grouper(freq='W-MON'))
                              .mean())
                weekly_pace = weekly_pace[weekly_pace > 0] if len(weekly_pace) > 0 else weekly_pace

                x_weekly_pace = [d.strftime('%b %d') for d in weekly_pace.index]
                y_weekly_pace = [float(v) for v in weekly_pace.values]
                week_numbers_pace = [d.isocalendar()[1] for d in weekly_pace.index]
                week_end_dates_pace = [(d + timedelta(days=6)).strftime('%b %d, %Y') for d in weekly_pace.index]
                hover_text_pace = [f"Week {wk} of {d.year}<br>{d.strftime('%b %d')} - {end}<br>Pace: {pace_to_mmss(pace)}"
                                  for wk, d, end, pace in zip(week_numbers_pace, weekly_pace.index, week_end_dates_pace, y_weekly_pace)]

                weekly_pace_fig = go.Figure([
                    go.Scatter(
                        x=x_weekly_pace,
                        y=y_weekly_pace,
                        mode='lines+markers',
                        line=dict(color="#e15759"),
                        marker=dict(size=8),
                        text=hover_text_pace,
                        hovertemplate='%{text}<extra></extra>'
                    )
                ])
                weekly_pace_fig.update_layout(
                    title="Weekly Average Pace",
                    xaxis_title="Week Start Date",
                    yaxis_title="Pace (min/mile)",
                    yaxis=dict(
                        autorange='reversed',  # Lower pace (faster) at top
                        tickmode='array',
                        tickvals=[i * 60 for i in range(6, 15)],  # 6:00 to 14:00 min/mile
                        ticktext=[f"{i}:00" for i in range(6, 15)]
                    ),
                    xaxis=dict(type='category')
                )
                pace_trend_weekly_json = json.dumps(weekly_pace_fig, cls=plotly.utils.PlotlyJSONEncoder)

                # Monthly average pace
                monthly_pace = (ra['pace_sec_per_mi']
                               .groupby(pd.Grouper(freq='MS'))
                               .mean())
                monthly_pace = monthly_pace[monthly_pace > 0] if len(monthly_pace) > 0 else monthly_pace

                x_monthly_pace = [d.strftime('%b %Y') for d in monthly_pace.index]
                y_monthly_pace = [float(v) for v in monthly_pace.values]
                hover_text_monthly_pace = [f"{month}<br>Pace: {pace_to_mmss(pace)}"
                                          for month, pace in zip(x_monthly_pace, y_monthly_pace)]

                monthly_pace_fig = go.Figure([
                    go.Scatter(
                        x=x_monthly_pace,
                        y=y_monthly_pace,
                        mode='lines+markers',
                        line=dict(color="#e15759"),
                        marker=dict(size=8),
                        text=hover_text_monthly_pace,
                        hovertemplate='%{text}<extra></extra>'
                    )
                ])
                monthly_pace_fig.update_layout(
                    title="Monthly Average Pace",
                    xaxis_title="Month",
                    yaxis_title="Pace (min/mile)",
                    yaxis=dict(
                        autorange='reversed',  # Lower pace (faster) at top
                        tickmode='array',
                        tickvals=[i * 60 for i in range(6, 15)],
                        ticktext=[f"{i}:00" for i in range(6, 15)]
                    ),
                    xaxis=dict(type='category')
                )
                pace_trend_monthly_json = json.dumps(monthly_pace_fig, cls=plotly.utils.PlotlyJSONEncoder)

    except Exception as e:
        # Silently handle errors in trend generation
        pass

    return {
        'pie_chart': pie_chart_json,
        'duration_pie_chart': duration_pie_chart_json,
        'total_activities': len(activities),
        'running_miles': round(running_distance, 2),
        'total_elevation_feet': round(total_elevation_feet, 2),
        'total_duration_formatted': total_duration_formatted,
        'activity_breakdown': activity_counts.to_dict(),
        'run_distance_distribution': run_distance_distribution,
        'runs_10k_plus': runs_10k_plus,
        'total_runs': total_runs,
        'avg_pace_formatted': avg_pace_formatted,
        'mileage_trend_daily': mileage_trend_daily_json,
        'mileage_trend_weekly': mileage_trend_weekly_json,
        'mileage_trend_monthly': mileage_trend_monthly_json,
        'pace_trend_daily': pace_trend_daily_json,
        'pace_trend_weekly': pace_trend_weekly_json,
        'pace_trend_monthly': pace_trend_monthly_json
    }

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=STRAVA_PORT)
