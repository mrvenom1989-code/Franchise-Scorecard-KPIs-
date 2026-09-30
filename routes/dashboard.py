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
    locations = user.get('locations', [])

    return render_template(
        'dashboard.html',
        user=user,
        periods=periods,
        locations=locations
    )
