from flask import Blueprint, render_template, session, redirect, url_for
from routes.auth import login_required
from config import supabase

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    user = session['user']
    
    # Fetch available scorecard periods (ordered by end_date desc)
    periods = []
    try:
        p_resp = supabase.table('scorecard_periods').select('*').order('end_date', desc=True).execute()
        periods = p_resp.data or []
    except Exception as e:
        print(f"[ERROR] Fetching periods: {e}")

    # Locations available to this user
    locations = []
    try:
        if user.get('role') == 'super_admin':
            loc_resp = supabase.table('locations').select('id, store_number, name, short_name, region, store_type').eq('is_active', True).order('store_number').execute()
            locations = loc_resp.data or []
        else:
            acc_resp = supabase.table('user_location_access').select('locations(id, store_number, name, short_name, region, store_type)').eq('user_id', user['id']).execute()
            locations = [row['locations'] for row in (acc_resp.data or []) if row.get('locations')]
            locations.sort(key=lambda x: x.get('store_number', 0))
    except Exception as e:
        print(f"[ERROR] Fetching locations: {e}")

    return render_template(
        'dashboard.html',
        user=user,
        periods=periods,
        locations=locations
    )
