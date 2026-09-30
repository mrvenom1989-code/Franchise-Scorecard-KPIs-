import os
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY, supabase

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def roles_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user' not in session:
                return redirect(url_for('auth.login'))
            user_role = session['user'].get('role')
            if user_role not in allowed_roles and 'super_admin' not in allowed_roles:
                flash("Unauthorized access for your user role.", "danger")
                return redirect(url_for('dashboard.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        try:
            # Client dedicated to verifying credentials
            local_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            auth_resp = local_client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            user_id = auth_resp.user.id

            # Fetch profile using service role
            p_resp = supabase.table('user_profiles').select('*').eq('id', user_id).execute()
            if not p_resp.data:
                flash("No active profile found for this account. Contact your administrator.", "danger")
                return render_template('login.html', email=email)

            profile = p_resp.data[0]
            if not profile.get('is_active', True):
                flash("Your account has been deactivated. Please contact support.", "danger")
                return render_template('login.html', email=email)

            role = profile.get('role', 'store_manager')

            # Fetch permitted locations
            permitted_locations = []
            if role == 'super_admin':
                # Super Admin has access to all active locations
                loc_resp = supabase.table('locations').select('id, store_number, name, short_name, region, store_type').eq('is_active', True).order('store_number').execute()
                permitted_locations = loc_resp.data or []
            else:
                # Scoped to user_location_access
                acc_resp = supabase.table('user_location_access').select('location_id, locations(*)').eq('user_id', user_id).execute()
                for row in (acc_resp.data or []):
                    if row.get('locations'):
                        permitted_locations.append(row['locations'])

            # Sort by store number
            permitted_locations.sort(key=lambda x: x.get('store_number', 0))

            session['user'] = {
                'id': user_id,
                'email': email,
                'full_name': profile.get('full_name', email.split('@')[0]),
                'role': role,
                'organization_name': profile.get('organization_name', 'Mobile Klinik'),
                'location_ids': [loc['id'] for loc in permitted_locations],
                'locations': permitted_locations
            }

            next_url = request.args.get('next')
            return redirect(next_url or url_for('dashboard.index'))

        except Exception as e:
            msg = str(e).replace("AuthApiError:", "").strip()
            if "Invalid login credentials" in msg:
                flash("Invalid email or password. Please try again.", "danger")
            else:
                flash(f"Authentication error: {msg}", "danger")
            return render_template('login.html', email=email)

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
