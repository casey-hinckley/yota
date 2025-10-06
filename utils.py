import pandas as pd
import re
from models import db, Athlete, SwimTime

def load_swim_data():
    """Load and parse swim data from CSV"""
    try:
        df = pd.read_csv('cleaned_swim_data.csv')
        return df
    except Exception as e:
        print(f"Error loading swim data: {e}")
        return pd.DataFrame()

def load_time_standards():
    """Load and parse time standards from CSV"""
    try:
        df = pd.read_csv('all_meet_standards.csv')
        return df
    except Exception as e:
        print(f"Error loading time standards: {e}")
        return pd.DataFrame()

def load_attendance_data():
    """Load and parse attendance data from CSV"""
    try:
        df = pd.read_csv('Swimmer_Attendance_Percentages.csv')
        return df
    except Exception as e:
        print(f"Error loading attendance data: {e}")
        return pd.DataFrame()

def extract_athlete_age(athlete_name):
    """Extract age from athlete name like 'Name (Gender Age)'"""
    # Look for pattern like "(Girl 13)" or "(Boy 15)" - age comes after gender
    match = re.search(r'\((Girl|Boy)\s+(\d+)\)', athlete_name)
    if match:
        return int(match.group(2))  # Group 2 is the age number
    return None

def get_athlete_gender(athlete_name):
    """Extract gender from athlete name"""
    if 'Girl' in athlete_name:
        return 'Female'
    elif 'Boy' in athlete_name:
        return 'Male'
    return None

def parse_time(time_str):
    """Convert time string to seconds for comparison"""
    if pd.isna(time_str) or time_str == '':
        return None
    
    # Remove course indicator (Y, L, M) and convert to seconds
    time_str = str(time_str).strip()
    course_indicator = time_str[-1] if time_str[-1] in ['Y', 'L', 'M'] else ''
    time_str = time_str[:-1] if course_indicator else time_str
    
    # Parse time format (MM:SS.ss or SS.ss)
    if ':' in time_str:
        parts = time_str.split(':')
        if len(parts) == 2:
            minutes, seconds = parts
            return float(minutes) * 60 + float(seconds)
        elif len(parts) == 3:
            hours, minutes, seconds = parts
            return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
    else:
        return float(time_str)

def get_course_from_time(time_str):
    """Extract course from time string"""
    if pd.isna(time_str) or time_str == '':
        return None
    time_str = str(time_str).strip()
    course_indicator = time_str[-1] if time_str[-1] in ['Y', 'L', 'M'] else ''
    course_map = {'Y': 'SCY', 'L': 'LCM', 'M': 'SCM'}
    return course_map.get(course_indicator)

def get_eligible_age_groups(athlete_age):
    """Get age groups the athlete is eligible for based on their exact age"""
    if athlete_age is None:
        return []
    
    eligible = []
    
    # Age-specific groups
    if athlete_age <= 10:
        eligible.append('10-Under')
    if 11 <= athlete_age <= 12:
        eligible.append('11-12')
    if 13 <= athlete_age <= 14:
        eligible.append('13-14')
    if athlete_age >= 15:
        eligible.append('15&O')
        eligible.append('15-Over')
        eligible.append('15-18')
    
    # Cumulative age groups (swimmer can compete in these if they meet the age requirement)
    if athlete_age <= 12:
        eligible.append('12&U')
    if athlete_age <= 14:
        eligible.append('14-Under')
    if athlete_age <= 18:
        eligible.append('18 and Under')
        eligible.append('18&U')
    
    # Open is always eligible
    eligible.append('Open')
    
    # Remove duplicates and return
    return list(set(eligible))

def get_time_standards_for_event(event, course, gender, athlete_age):
    """Get all time standards for a specific event, course, and gender"""
    standards_df = load_time_standards()
    if standards_df.empty:
        return pd.DataFrame()
    
    # Filter by event, course, and gender
    filtered = standards_df[
        (standards_df['Event'] == event) &
        (standards_df['Course'] == course) &
        (standards_df['Gender'] == gender)
    ].copy()
    
    if filtered.empty:
        return pd.DataFrame()
    
    # Parse times and filter by eligible age groups
    filtered['time_seconds'] = filtered['Time'].apply(parse_time)
    eligible_age_groups = get_eligible_age_groups(athlete_age)
    
    # Filter out "Age Group" entries and only include eligible age groups
    filtered = filtered[
        (filtered['Age Group'] != 'Age Group') & 
        (filtered['Age Group'].isin(eligible_age_groups))
    ]
    
    # For YMCA Nationals, we want to show both meets but only the cuts for the selected course
    # The filtering by course will naturally show the right cuts from each meet
    
    # For each meet, keep only the slowest (most challenging) cut the athlete is eligible for
    filtered = filtered.sort_values(['Meet', 'time_seconds'], ascending=[True, False])
    filtered = filtered.drop_duplicates(subset=['Meet'], keep='first')
    
    # Sort by time (fastest first) for final ordering
    filtered = filtered.sort_values('time_seconds')
    
    return filtered

def determine_cuts_achieved(athlete_best_time, standards_df):
    """Determine which cuts the athlete has achieved"""
    if standards_df.empty or athlete_best_time is None:
        return []
    
    achieved_cuts = []
    for _, standard in standards_df.iterrows():
        if athlete_best_time <= standard['time_seconds']:
            achieved_cuts.append({
                'meet': str(standard['Meet']),
                'age_group': str(standard['Age Group']),
                'time': str(standard['Time']),
                'time_seconds': float(standard['time_seconds']) if pd.notna(standard['time_seconds']) else None
            })
    
    return achieved_cuts

def get_next_cut(athlete_best_time, standards_df):
    """Get the next cut the athlete needs to achieve - the closest one they haven't achieved yet"""
    if standards_df.empty or athlete_best_time is None:
        return None
    
    # Find all cuts they haven't achieved yet (faster than their best time)
    unachieved_cuts = standards_df[standards_df['time_seconds'] < athlete_best_time].copy()
    
    if unachieved_cuts.empty:
        # If they have all cuts, show distance past the fastest
        fastest_cut = standards_df.iloc[0]
        return {
            'meet': str(fastest_cut['Meet']),
            'age_group': str(fastest_cut['Age Group']),
            'time': str(fastest_cut['Time']),
            'time_seconds': float(fastest_cut['time_seconds']) if pd.notna(fastest_cut['time_seconds']) else None,
            'distance_seconds': float(athlete_best_time - fastest_cut['time_seconds']) if pd.notna(fastest_cut['time_seconds']) else None,
            'distance_percentage': float(((athlete_best_time - fastest_cut['time_seconds']) / fastest_cut['time_seconds']) * 100) if pd.notna(fastest_cut['time_seconds']) else None,
            'beyond_fastest': True,
            'achieved': True
        }
    
    # Find the closest unachieved cut (smallest difference from their best time)
    unachieved_cuts['distance'] = athlete_best_time - unachieved_cuts['time_seconds']
    closest_cut = unachieved_cuts.loc[unachieved_cuts['distance'].idxmin()]
    
    return {
        'meet': str(closest_cut['Meet']),
        'age_group': str(closest_cut['Age Group']),
        'time': str(closest_cut['Time']),
        'time_seconds': float(closest_cut['time_seconds']) if pd.notna(closest_cut['time_seconds']) else None,
        'distance_seconds': float(closest_cut['distance']) if pd.notna(closest_cut['distance']) else None,
        'distance_percentage': float((closest_cut['distance'] / athlete_best_time) * 100) if pd.notna(closest_cut['distance']) else None,
        'achieved': False
    }

def get_athletes_from_data():
    """Get unique athletes from swim data"""
    # Get athletes from database instead of CSV
    athletes = db.session.query(Athlete.name).all()
    athletes = [athlete[0] for athlete in athletes]  # Extract from tuple
    return sorted(athletes)

def get_events_from_data():
    """Get unique events from swim data organized by stroke"""
    # Get events from database instead of CSV
    events = db.session.query(SwimTime.event).distinct().all()
    events = [event[0] for event in events]  # Extract from tuple
    
    if not events:
        return {}
    
    # Define stroke groups
    stroke_groups = {
        'Freestyle': ['50 Free', '100 Free', '200 Free', '400 Free', '500 Free', '800 Free', '1000 Free', '1500 Free', '1650 Free'],
        'Backstroke': ['50 Back', '100 Back', '200 Back'],
        'Breaststroke': ['50 Breast', '100 Breast', '200 Breast'],
        'Butterfly': ['50 Fly', '100 Fly', '200 Fly'],
        'Individual Medley': ['100 IM', '200 IM', '400 IM']
    }
    
    # Organize events by stroke
    organized_events = {}
    for stroke, stroke_events in stroke_groups.items():
        organized_events[stroke] = [event for event in events if event in stroke_events]
    
    # Add any events that don't fit the predefined groups
    all_grouped_events = []
    for stroke_events in organized_events.values():
        all_grouped_events.extend(stroke_events)
    
    ungrouped_events = [event for event in events if event not in all_grouped_events]
    if ungrouped_events:
        organized_events['Other'] = ungrouped_events
    
    return organized_events

def get_courses_from_data():
    """Get unique courses from swim data"""
    # Get courses from database instead of CSV
    courses = db.session.query(SwimTime.course).distinct().all()
    courses = [course[0] for course in courses if course[0]]  # Extract from tuple and filter None
    
    if not courses:
        return []
    
    course_names = {'SCY': 'SCY (Short Course Yards)', 'LCM': 'LCM (Long Course Meters)', 'SCM': 'SCM (Short Course Meters)'}
    return [{'code': course, 'name': course_names.get(course, course)} for course in sorted(courses)]

def get_meets_from_standards():
    """Get unique meets from time standards"""
    standards_df = load_time_standards()
    if standards_df.empty:
        return []
    
    # Get all unique meets
    meets = standards_df['Meet'].unique().tolist()
    
    # For YMCA Nationals, we want to show them as course-specific options
    # but the actual filtering will be done in get_time_standards_for_event
    processed_meets = []
    for meet in meets:
        if 'YMCA Nationals (SC Meet)' in meet:
            processed_meets.append('YMCA Nationals (SC Meet)')
        elif 'YMCA Nationals (LC Meet)' in meet:
            processed_meets.append('YMCA Nationals (LC Meet)')
        else:
            processed_meets.append(meet)
    
    # Remove duplicates and sort
    processed_meets = sorted(list(set(processed_meets)))
    return processed_meets

def calculate_time_improvement_analysis(event, course, athlete_name):
    """Calculate time improvement vs attendance correlation for an event"""
    swim_df = load_swim_data()
    attendance_df = load_attendance_data()
    
    if swim_df.empty or attendance_df.empty:
        return None
    
    # Filter for the specific event and course
    course_name = {'Y': 'SCY', 'L': 'LCM', 'M': 'SCM'}[course]
    event_data = swim_df[
        (swim_df['Event'] == event) &
        (swim_df['Best Time'].str.endswith(course, na=False))
    ].copy()
    
    if event_data.empty:
        return None
    
    # Parse times
    event_data['time_seconds'] = event_data['Best Time'].apply(parse_time)
    event_data['date_parsed'] = pd.to_datetime(event_data['Date'], format='%m/%d/%Y')
    
    # Calculate time improvements for each swimmer
    improvements = []
    
    for swimmer in event_data['Name'].unique():
        swimmer_data = event_data[event_data['Name'] == swimmer].copy()
        swimmer_data = swimmer_data.sort_values('date_parsed')
        
        if len(swimmer_data) < 2:
            continue  # Need at least 2 swims to calculate improvement
        
        # Calculate improvement from first to last swim
        first_time = swimmer_data.iloc[0]['time_seconds']
        last_time = swimmer_data.iloc[-1]['time_seconds']
        
        if first_time is None or last_time is None:
            continue
        
        # Improvement is positive if they got faster (lower time)
        improvement_seconds = first_time - last_time
        improvement_percentage = (improvement_seconds / first_time) * 100
        
        # Get attendance for this swimmer
        # Clean name for matching (remove age/gender info)
        clean_name = re.sub(r'\s*\([^)]*\)', '', swimmer)
        attendance_match = attendance_df[attendance_df['Name'] == clean_name]
        
        if not attendance_match.empty:
            attendance_percentage = attendance_match.iloc[0]['AttendancePercentage']
            
            improvements.append({
                'swimmer': swimmer,
                'clean_name': clean_name,
                'attendance': attendance_percentage,
                'improvement_seconds': improvement_seconds,
                'improvement_percentage': improvement_percentage,
                'first_time': first_time,
                'last_time': last_time,
                'swims_count': len(swimmer_data)
            })
    
    if len(improvements) < 2:
        return None  # Need at least 2 swimmers with attendance data
    
    # Calculate correlation and prediction
    improvements_df = pd.DataFrame(improvements)
    
    # Simple linear regression: improvement_percentage = a * attendance + b
    attendance_values = improvements_df['attendance'].values
    improvement_values = improvements_df['improvement_percentage'].values
    
    # Calculate correlation
    correlation = improvements_df['attendance'].corr(improvements_df['improvement_percentage'])
    
    # Simple linear regression
    n = len(attendance_values)
    if n > 1:
        sum_x = sum(attendance_values)
        sum_y = sum(improvement_values)
        sum_xy = sum(attendance_values * improvement_values)
        sum_x2 = sum(attendance_values ** 2)
        
        # Calculate slope and intercept
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
        intercept = (sum_y - slope * sum_x) / n
    else:
        slope = 0
        intercept = 0
    
    # Get current athlete's attendance
    clean_athlete_name = re.sub(r'\s*\([^)]*\)', '', athlete_name)
    athlete_attendance_match = attendance_df[attendance_df['Name'] == clean_athlete_name]
    
    if athlete_attendance_match.empty:
        return None
    
    athlete_attendance = athlete_attendance_match.iloc[0]['AttendancePercentage']
    
    # Predict improvement for current athlete
    predicted_improvement_percentage = slope * athlete_attendance + intercept
    
    # Get athlete's current best time
    athlete_data = event_data[event_data['Name'] == athlete_name].copy()
    if athlete_data.empty:
        return None
    
    athlete_data = athlete_data.sort_values('date_parsed')
    current_best_time = athlete_data.iloc[-1]['time_seconds']
    
    if current_best_time is None:
        return None
    
    # Calculate predicted time
    predicted_time = current_best_time * (1 - predicted_improvement_percentage / 100)
    
    return {
        'correlation': correlation,
        'slope': slope,
        'intercept': intercept,
        'athlete_attendance': athlete_attendance,
        'predicted_improvement_percentage': predicted_improvement_percentage,
        'current_best_time': current_best_time,
        'predicted_time': predicted_time,
        'predicted_time_seconds': predicted_time,
        'sample_size': len(improvements),
        'improvements_data': improvements
    }
