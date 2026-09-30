import os
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from routes.auth import login_required, roles_required
from config import supabase
from create_user import create_or_update_user
from ingest_scorecard import main as run_ingest

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/users')
@login_required
@roles_required('super_admin', 'admin')
def user_management():
    current_user = session['user']
    role = current_user['role']
    user_id = current_user['id']

    # 1. Fetch accessible locations for store assignment
    if role == 'super_admin':
        loc_resp = supabase.table('locations').select('id, store_number, name, region').order('store_number').execute()
        assignable_locations = loc_resp.data or []
        
        # Super admin sees all users
        u_resp = supabase.table('user_profiles').select('*, user_location_access(locations(store_number, name))').order('created_at', desc=True).execute()
        users = u_resp.data or []
    else:
        # Franchise owner only sees their own assigned locations
        assignable_locations = current_user.get('locations', [])
        assignable_loc_ids = [loc['id'] for loc in assignable_locations]
        
        # Franchise owner sees users created by them or assigned to their locations
        relevant_user_ids = set()
        if assignable_loc_ids:
            loc_acc_resp = supabase.table('user_location_access').select('user_id').in_('location_id', assignable_loc_ids).execute()
            for r in (loc_acc_resp.data or []):
                relevant_user_ids.add(r['user_id'])

        created_resp = supabase.table('user_profiles').select('id').eq('created_by', user_id).execute()
        for r in (created_resp.data or []):
            relevant_user_ids.add(r['id'])

        if relevant_user_ids:
            u_resp = supabase.table('user_profiles').select('*, user_location_access(locations(store_number, name))').in_('id', list(relevant_user_ids)).order('created_at', desc=True).execute()
            users = u_resp.data or []
        else:
            users = []

    return render_template(
        'admin.html',
        current_user=current_user,
        users=users,
        assignable_locations=assignable_locations
    )

@admin_bp.route('/users/create', methods=['POST'])
@login_required
@roles_required('super_admin', 'admin')
def create_user_route():
    current_user = session['user']
    role = current_user['role']

    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    full_name = request.form.get('full_name', '').strip()
    target_role = request.form.get('role', 'store_manager')
    selected_stores = request.form.getlist('stores') # List of store numbers

    # Validation: Franchise Owners can only create 'store_manager' or 'staff'
    if role == 'admin' and target_role not in ['store_manager', 'staff', 'accountant']:
        flash("Franchise owners can only provision Store Managers, Accountants, or Staff.", "danger")
        return redirect(url_for('admin.user_management'))

    # Security check: Ensure selected stores are within current user's permitted stores
    if role != 'super_admin':
        permitted_store_nums = {str(loc['store_number']) for loc in current_user.get('locations', [])}
        for s in selected_stores:
            if s not in permitted_store_nums:
                flash(f"Unauthorized store assignment: Store #{s}", "danger")
                return redirect(url_for('admin.user_management'))

    stores_str = ",".join(selected_stores)
    success = create_or_update_user(
        email=email,
        password=password,
        full_name=full_name,
        role=target_role,
        stores=stores_str,
        org_name=current_user.get('organization_name'),
        created_by=current_user['id']
    )

    if success:
        flash(f"User {email} successfully provisioned as {target_role}!", "success")
    else:
        flash(f"Failed to provision user {email}. Check server logs.", "danger")

    return redirect(url_for('admin.user_management'))

@admin_bp.route('/upload-scorecard', methods=['POST'])
@login_required
@roles_required('super_admin')
def upload_scorecard():
    if 'file' not in request.files:
        flash("No file selected", "danger")
        return redirect(url_for('admin.user_management'))
    
    file = request.files['file']
    if file.filename == '':
        flash("No file selected", "danger")
        return redirect(url_for('admin.user_management'))

    if not file.filename.endswith(('.xlsx', '.xls')):
        flash("Please upload an Excel (.xlsx) file.", "danger")
        return redirect(url_for('admin.user_management'))

    upload_path = os.path.join(os.path.dirname(__file__), "..", ".tmp", file.filename)
    os.makedirs(os.path.dirname(upload_path), exist_ok=True)
    file.save(upload_path)

    try:
        # Run ingestion
        import subprocess
        script_path = os.path.join(os.path.dirname(__file__), "..", "ingest_scorecard.py")
        cmd = [os.sys.executable, script_path, "--file", upload_path]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        flash(f"Scorecard '{file.filename}' successfully ingested into Supabase!", "success")
    except Exception as e:
        flash(f"ETL ingestion error: {e}", "danger")

    return redirect(url_for('admin.user_management'))
