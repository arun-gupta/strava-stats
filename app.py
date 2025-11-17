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

@app.route('/', methods=['GET', 'POST'])
def index():
    """Home page - shows analysis with default or submitted dates"""
    if 'access_token' not in session:
        return render_template('login.html', auth_url=strava_api.get_auth_url())

    # Get dates from POST form or use defaults (last 30 days)
    if request.method == 'POST':
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
    else:
        # Default to last 30 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

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

    return render_template('results.html', analysis=analysis, start_date=start_date_str, end_date=end_date_str)

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

    # Determine common date range for all streak calculations
    common_date_range_start = None
    common_date_range_end = None
    if 'start_date' in df.columns:
        df['start_date_temp'] = pd.to_datetime(df['start_date'])
        common_date_range_start = df['start_date_temp'].min().normalize()
        common_date_range_end = df['start_date_temp'].max().normalize()
        df.drop('start_date_temp', axis=1, inplace=True)

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

        # Calculate personal records
        # Best mile split (fastest pace for any run)
        best_mile_split_formatted = None
        if 'moving_time' in running_activities.columns:
            running_activities_copy = running_activities.copy()
            running_activities_copy['pace_sec_per_mi'] = running_activities_copy['moving_time'] / (running_activities_copy['distance'] / 1609.34)
            # Filter out invalid paces (too slow or NaN)
            valid_paces = running_activities_copy['pace_sec_per_mi'].dropna()
            valid_paces = valid_paces[valid_paces > 0]
            if len(valid_paces) > 0:
                best_mile_split_seconds = valid_paces.min()
                pace_minutes = int(best_mile_split_seconds // 60)
                pace_seconds = int(best_mile_split_seconds % 60)
                best_mile_split_formatted = f"{pace_minutes}:{pace_seconds:02d}"

        # Fastest 10K
        fastest_10k_formatted = None
        runs_10k = running_activities[(running_activities['distance'] / 1609.34) >= 6.2]
        if not runs_10k.empty and 'moving_time' in runs_10k.columns:
            fastest_10k_seconds = runs_10k['moving_time'].min()

            # Format fastest 10K
            hours = int(fastest_10k_seconds // 3600)
            minutes = int((fastest_10k_seconds % 3600) // 60)
            seconds = int(fastest_10k_seconds % 60)
            if hours > 0:
                fastest_10k_formatted = f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                fastest_10k_formatted = f"{minutes}:{seconds:02d}"

        # Longest run (by distance)
        longest_run_distance = None
        if not running_activities.empty:
            longest_run_distance_miles = (running_activities['distance'].max()) / 1609.34
            longest_run_distance = f"{longest_run_distance_miles:.2f} mi"

        # Most elevation in a single run
        most_elevation_run = None
        if not running_activities.empty and 'total_elevation_gain' in running_activities.columns:
            max_elevation_idx = running_activities['total_elevation_gain'].idxmax()
            max_elevation_meters = running_activities.loc[max_elevation_idx, 'total_elevation_gain']
            max_elevation_feet = max_elevation_meters * 3.28084
            run_distance_miles = running_activities.loc[max_elevation_idx, 'distance'] / 1609.34
            most_elevation_run = f"{max_elevation_feet:.0f} ft ({run_distance_miles:.2f} mi)"

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
                # Use common date range if available, otherwise fall back to running activities range
                if common_date_range_start and common_date_range_end:
                    daily_index = pd.date_range(common_date_range_start, common_date_range_end, freq='D')
                else:
                    daily_index = pd.date_range(ra.index.min().normalize(), ra.index.max().normalize(), freq='D')
                daily = (ra['distance_mi']
                         .groupby(pd.Grouper(freq='D'))
                         .sum()
                         .reindex(daily_index, fill_value=0))
                # Use ISO strings for dates to avoid any serialization quirks
                x_daily = [d.strftime('%Y-%m-%d') for d in daily.index]
                y_daily = [float(v) for v in daily.values]

                # ==============================
                # Running streaks and gap days
                # ==============================
                # Boolean series for run/no-run per day
                run_days = daily > 0

                # Current streak: consecutive run days ending on the last day in range
                current_streak_days = 0
                for ran in reversed(run_days.tolist()):
                    if ran:
                        current_streak_days += 1
                    else:
                        break

                # Days since last run and last run date
                last_run_date = None
                days_since_last_run = None
                if run_days.any():
                    last_true_idx = None
                    # find last index where run_days is True
                    for i in range(len(run_days) - 1, -1, -1):
                        if run_days.iloc[i]:
                            last_true_idx = i
                            break
                    if last_true_idx is not None:
                        last_run_date = daily.index[last_true_idx]
                        days_since_last_run = (daily.index[-1] - last_run_date).days

                # Collect gap day spans (consecutive zero-mile stretches)
                gap_spans = []
                in_gap = False
                gap_start = None
                for i, (date, ran) in enumerate(zip(daily.index, run_days.tolist())):
                    if not ran and not in_gap:
                        in_gap = True
                        gap_start = date
                    elif ran and in_gap:
                        # gap ended at previous day
                        gap_end = daily.index[i - 1]
                        length = (gap_end - gap_start).days + 1
                        gap_spans.append({
                            'start': gap_start.strftime('%Y-%m-%d'),
                            'end': gap_end.strftime('%Y-%m-%d'),
                            'length': int(length)
                        })
                        in_gap = False
                        gap_start = None
                # If range ends in a gap, close it
                if in_gap and gap_start is not None:
                    gap_end = daily.index[-1]
                    length = (gap_end - gap_start).days + 1
                    gap_spans.append({
                        'start': gap_start.strftime('%Y-%m-%d'),
                        'end': gap_end.strftime('%Y-%m-%d'),
                        'length': int(length)
                    })

                total_gap_days = int(sum(span['length'] for span in gap_spans))
                longest_gap_days = int(max((span['length'] for span in gap_spans), default=0))

                # Longest run streak (consecutive run days anywhere in the range)
                longest_run_streak = 0
                current_seq = 0
                for ran in run_days.tolist():
                    if ran:
                        current_seq += 1
                        if current_seq > longest_run_streak:
                            longest_run_streak = current_seq
                    else:
                        current_seq = 0

                # Build arrays for frontend timeline/heat visualization
                streak_daily_dates = x_daily
                streak_daily_miles = y_daily
                streak_daily_run_flags = [1 if m > 0 else 0 for m in y_daily]

                # Calculate total running days and missed days in window
                running_total_days_in_window = len(daily_index)
                running_active_days = int(run_days.sum())
                running_missed_days = running_total_days_in_window - running_active_days

                # Milestones and next target based on current streak
                milestones = [7, 14, 30, 60, 100]
                next_milestone = None
                days_to_next_milestone = None
                estimated_next_milestone_date = None
                if milestones:
                    for m in milestones:
                        if current_streak_days < m:
                            next_milestone = int(m)
                            days_to_next_milestone = int(m - current_streak_days)
                            try:
                                estimated_next_milestone_date = (daily.index[-1] + timedelta(days=days_to_next_milestone)).strftime('%Y-%m-%d')
                            except Exception:
                                estimated_next_milestone_date = None
                            break
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
                # Calculate appropriate tick interval for mileage chart
                num_days_mileage = len(daily_index)
                if num_days_mileage <= 30:
                    mileage_dtick = 86400000  # Show every day for <= 30 days
                elif num_days_mileage <= 90:
                    mileage_dtick = 86400000 * 7  # Show every week for <= 90 days
                else:
                    mileage_dtick = 86400000 * 14  # Show every 2 weeks for > 90 days

                daily_fig.update_layout(
                    title="Daily Running Mileage",
                    xaxis_title="Day",
                    yaxis_title="Miles",
                    yaxis=dict(rangemode='tozero'),
                    xaxis=dict(
                        type='date',
                        tickformat='%b %d',
                        tickangle=-45,
                        dtick=mileage_dtick
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

                # Calculate appropriate tick interval based on date range
                num_days = len(daily_index)
                if num_days <= 30:
                    dtick = 86400000  # Show every day for <= 30 days
                elif num_days <= 90:
                    dtick = 86400000 * 7  # Show every week for <= 90 days
                else:
                    dtick = 86400000 * 14  # Show every 2 weeks for > 90 days

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
                        dtick=dtick,
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

    # ==============================
    # Workout Streak (all activities)
    # ==============================
    workout_current_streak_days = 0
    workout_longest_streak = 0
    workout_days_since_last = None
    workout_last_activity_date = None
    workout_total_gap_days = 0
    workout_longest_gap_days = 0
    workout_gap_spans = []
    workout_daily_dates = []
    workout_daily_activity_counts = []
    workout_daily_flags = []
    workout_active_days = 0
    workout_missed_days = 0
    workout_total_days_in_window = 0

    try:
        if not df.empty and 'start_date' in df.columns:
            # Work with all activities
            all_activities = df.copy()
            all_activities['start_date'] = pd.to_datetime(all_activities['start_date'])
            all_activities = all_activities.set_index('start_date').sort_index()

            # Create daily index for full range
            # Use common date range if available, otherwise fall back to all activities range
            if common_date_range_start and common_date_range_end:
                workout_daily_index = pd.date_range(common_date_range_start, common_date_range_end, freq='D')
            else:
                workout_daily_index = pd.date_range(
                    all_activities.index.min().normalize(),
                    all_activities.index.max().normalize(),
                    freq='D'
                )

            # Calculate total hours per day (moving_time is in seconds)
            daily_workout_hours = all_activities.groupby(all_activities.index.normalize())['moving_time'].sum() / 3600
            daily_workout_hours = daily_workout_hours.reindex(workout_daily_index, fill_value=0)

            # Boolean series for workout/no-workout per day
            workout_days = daily_workout_hours > 0

            # Current streak: consecutive workout days ending on the last day
            for had_workout in reversed(workout_days.tolist()):
                if had_workout:
                    workout_current_streak_days += 1
                else:
                    break

            # Last activity date and days since
            if workout_days.any():
                last_workout_idx = None
                for i in range(len(workout_days) - 1, -1, -1):
                    if workout_days.iloc[i]:
                        last_workout_idx = i
                        break
                if last_workout_idx is not None:
                    workout_last_activity_date = workout_daily_index[last_workout_idx]
                    workout_days_since_last = (workout_daily_index[-1] - workout_last_activity_date).days

            # Collect gap spans (consecutive no-workout days)
            in_gap = False
            gap_start = None
            for i, (date, had_workout) in enumerate(zip(workout_daily_index, workout_days.tolist())):
                if not had_workout and not in_gap:
                    in_gap = True
                    gap_start = date
                elif had_workout and in_gap:
                    gap_end = workout_daily_index[i - 1]
                    length = (gap_end - gap_start).days + 1
                    workout_gap_spans.append({
                        'start': gap_start.strftime('%Y-%m-%d'),
                        'end': gap_end.strftime('%Y-%m-%d'),
                        'length': int(length)
                    })
                    in_gap = False
                    gap_start = None

            # Close gap if range ends in one
            if in_gap and gap_start is not None:
                gap_end = workout_daily_index[-1]
                length = (gap_end - gap_start).days + 1
                workout_gap_spans.append({
                    'start': gap_start.strftime('%Y-%m-%d'),
                    'end': gap_end.strftime('%Y-%m-%d'),
                    'length': int(length)
                })

            workout_total_gap_days = int(sum(span['length'] for span in workout_gap_spans))
            workout_longest_gap_days = int(max((span['length'] for span in workout_gap_spans), default=0))

            # Longest workout streak (consecutive workout days anywhere in range)
            current_seq = 0
            for had_workout in workout_days.tolist():
                if had_workout:
                    current_seq += 1
                    if current_seq > workout_longest_streak:
                        workout_longest_streak = current_seq
                else:
                    current_seq = 0

            # Build arrays for frontend visualization
            workout_daily_dates = [d.strftime('%Y-%m-%d') for d in workout_daily_index]
            workout_daily_hours = [float(h) for h in daily_workout_hours.values]
            workout_daily_flags = [1 if h > 0 else 0 for h in daily_workout_hours.values]

            # Calculate total workout days and missed days in window
            workout_total_days_in_window = len(workout_daily_index)
            workout_active_days = int(workout_days.sum())
            workout_missed_days = workout_total_days_in_window - workout_active_days

            # Milestones for workout streaks
            workout_milestones = [7, 14, 30, 60, 100]
            workout_next_milestone = None
            workout_days_to_next_milestone = None
            workout_eta_next_milestone = None
            for m in workout_milestones:
                if workout_current_streak_days < m:
                    workout_next_milestone = int(m)
                    workout_days_to_next_milestone = int(m - workout_current_streak_days)
                    try:
                        workout_eta_next_milestone = (workout_daily_index[-1] + timedelta(days=workout_days_to_next_milestone)).strftime('%Y-%m-%d')
                    except Exception:
                        workout_eta_next_milestone = None
                    break
    except Exception:
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
        'best_mile_split': best_mile_split_formatted if 'best_mile_split_formatted' in locals() else None,
        'fastest_10k': fastest_10k_formatted if 'fastest_10k_formatted' in locals() else None,
        'longest_run': longest_run_distance if 'longest_run_distance' in locals() else None,
        'most_elevation_run': most_elevation_run if 'most_elevation_run' in locals() else None,
        'mileage_trend_daily': mileage_trend_daily_json,
        'mileage_trend_weekly': mileage_trend_weekly_json,
        'mileage_trend_monthly': mileage_trend_monthly_json,
        'pace_trend_daily': pace_trend_daily_json,
        'pace_trend_weekly': pace_trend_weekly_json,
        'pace_trend_monthly': pace_trend_monthly_json,
        # Running streaks + gap analysis (may be None if no running data)
        'current_streak_days': int(current_streak_days) if 'current_streak_days' in locals() else 0,
        'last_run_date': last_run_date.strftime('%Y-%m-%d') if 'last_run_date' in locals() and last_run_date is not None else None,
        'days_since_last_run': int(days_since_last_run) if 'days_since_last_run' in locals() and days_since_last_run is not None else None,
        'total_gap_days': int(total_gap_days) if 'total_gap_days' in locals() else 0,
        'longest_gap_days': int(longest_gap_days) if 'longest_gap_days' in locals() else 0,
        'gap_spans': gap_spans if 'gap_spans' in locals() else [],
        # Enhanced streak visualization data
        'longest_run_streak': int(longest_run_streak) if 'longest_run_streak' in locals() else 0,
        'streak_daily_dates': streak_daily_dates if 'streak_daily_dates' in locals() else [],
        'streak_daily_miles': streak_daily_miles if 'streak_daily_miles' in locals() else [],
        'streak_daily_run_flags': streak_daily_run_flags if 'streak_daily_run_flags' in locals() else [],
        'next_streak_milestone': next_milestone if 'next_milestone' in locals() else None,
        'days_to_next_milestone': days_to_next_milestone if 'days_to_next_milestone' in locals() else None,
        'eta_next_milestone_date': estimated_next_milestone_date if 'estimated_next_milestone_date' in locals() else None,
        'running_active_days': running_active_days if 'running_active_days' in locals() else 0,
        'running_missed_days': running_missed_days if 'running_missed_days' in locals() else 0,
        'running_total_days_in_window': running_total_days_in_window if 'running_total_days_in_window' in locals() else 0,
        # Workout streaks (all activities)
        'workout_current_streak_days': workout_current_streak_days,
        'workout_longest_streak': workout_longest_streak,
        'workout_last_activity_date': workout_last_activity_date.strftime('%Y-%m-%d') if workout_last_activity_date is not None else None,
        'workout_days_since_last': workout_days_since_last,
        'workout_total_gap_days': workout_total_gap_days,
        'workout_longest_gap_days': workout_longest_gap_days,
        'workout_gap_spans': workout_gap_spans,
        'workout_daily_dates': workout_daily_dates,
        'workout_daily_hours': workout_daily_hours if 'workout_daily_hours' in locals() else [],
        'workout_daily_flags': workout_daily_flags,
        'workout_next_milestone': workout_next_milestone if 'workout_next_milestone' in locals() else None,
        'workout_days_to_next_milestone': workout_days_to_next_milestone if 'workout_days_to_next_milestone' in locals() else None,
        'workout_eta_next_milestone': workout_eta_next_milestone if 'workout_eta_next_milestone' in locals() else None,
        'workout_active_days': workout_active_days,
        'workout_missed_days': workout_missed_days,
        'workout_total_days_in_window': workout_total_days_in_window
    }

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=STRAVA_PORT)
