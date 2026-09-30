import os
import sys
import argparse
from config import supabase

def create_or_update_user(email, password, full_name, role, stores=None, org_name=None, created_by=None):
    if not supabase:
        print("[ERROR] Supabase client not initialized. Check your .env file.")
        return False

    print(f"Creating/updating user: {email} with role: {role}...")
    
    user_id = None
    try:
        # Create user via Supabase Auth Admin API
        user_resp = supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "full_name": full_name,
                "role": role
            }
        })
        user_id = user_resp.user.id
        print(f"  > Auth account created with ID: {user_id}")
    except Exception as e:
        err_msg = str(e)
        if "already been registered" in err_msg or "already exists" in err_msg:
            print(f"  [INFO] User {email} already exists in auth. Fetching user ID...")
            users = supabase.auth.admin.list_users()
            for u in users:
                if u.email.lower() == email.lower():
                    user_id = u.id
                    break
            if not user_id:
                print(f"[ERROR] Could not resolve user ID for existing user {email}")
                return False
        else:
            print(f"[ERROR] Failed to create auth user: {e}")
            return False

    # Upsert user profile
    profile_data = {
        "id": user_id,
        "email": email,
        "full_name": full_name,
        "role": role,
        "organization_name": org_name or ("Mobile Klinik Network" if role == "super_admin" else "Franchise Group"),
        "is_active": True
    }
    if created_by:
        profile_data["created_by"] = created_by

    try:
        supabase.table("user_profiles").upsert(profile_data, on_conflict="id").execute()
        print(f"  > Profile upserted with role '{role}'.")
    except Exception as e:
        print(f"[ERROR] Failed to update user profile: {e}")
        return False

    # Store assignments
    if stores:
        store_nums = [int(s.strip()) for s in stores.split(",") if s.strip().isdigit()]
        if store_nums:
            print(f"Assigning stores: {store_nums}...")
            # Fetch location IDs
            loc_resp = supabase.table("locations").select("id, store_number").in_("store_number", store_nums).execute()
            loc_ids = [r["id"] for r in loc_resp.data]
            
            # Remove previous mappings
            supabase.table("user_location_access").delete().eq("user_id", user_id).execute()
            
            # Insert new mappings
            access_rows = [{"user_id": user_id, "location_id": lid} for lid in loc_ids]
            if access_rows:
                supabase.table("user_location_access").insert(access_rows).execute()
                print(f"  > Assigned {len(access_rows)} locations to user.")

    print(f"\n[SUCCESS] User {email} configured successfully as '{role}'!")
    return True

def update_existing_user(user_id, full_name, role, is_active=True, stores=None, password=None, org_name=None):
    if not supabase:
        print("[ERROR] Supabase client not initialized.")
        return False

    print(f"Updating user ID: {user_id}...")
    try:
        # 1. Update Auth if password or metadata changed
        auth_attrs = {
            "user_metadata": {
                "full_name": full_name,
                "role": role
            }
        }
        if password and str(password).strip():
            auth_attrs["password"] = str(password).strip()

        supabase.auth.admin.update_user_by_id(user_id, auth_attrs)
        print("  > Auth user attributes updated.")
    except Exception as e:
        print(f"[WARN] Failed to update auth attributes: {e}")

    # 2. Update user_profiles
    profile_data = {
        "full_name": full_name,
        "role": role,
        "is_active": is_active
    }
    if org_name:
        profile_data["organization_name"] = org_name

    try:
        supabase.table("user_profiles").update(profile_data).eq("id", user_id).execute()
        print("  > User profile updated.")
    except Exception as e:
        print(f"[ERROR] Failed to update user profile: {e}")
        return False

    # 3. Update store assignments
    try:
        # Remove previous mappings
        supabase.table("user_location_access").delete().eq("user_id", user_id).execute()

        if stores and role != "super_admin":
            if isinstance(stores, str):
                store_nums = [int(s.strip()) for s in stores.split(",") if s.strip().isdigit()]
            elif isinstance(stores, list):
                store_nums = [int(s) for s in stores if str(s).isdigit()]
            else:
                store_nums = []

            if store_nums:
                loc_resp = supabase.table("locations").select("id, store_number").in_("store_number", store_nums).execute()
                loc_ids = [r["id"] for r in (loc_resp.data or [])]
                access_rows = [{"user_id": user_id, "location_id": lid} for lid in loc_ids]
                if access_rows:
                    supabase.table("user_location_access").insert(access_rows).execute()
                    print(f"  > Assigned {len(access_rows)} locations to user.")
    except Exception as e:
        print(f"[ERROR] Failed to update store assignments: {e}")
        return False

    print(f"[SUCCESS] User {user_id} updated successfully!")
    return True

def main():
    parser = argparse.ArgumentParser(description="Create or update a Franchise Scorecard user")
    parser.add_argument("--email", required=True, help="User email address")
    parser.add_argument("--password", required=True, help="User password")
    parser.add_argument("--name", default="Admin User", help="User full name")
    parser.add_argument("--role", default="super_admin", choices=["super_admin", "admin", "store_manager", "accountant", "staff"], help="User role")
    parser.add_argument("--stores", help="Comma-separated store numbers (e.g. '333,334,326,824,825,336,335,328')")
    parser.add_argument("--org", help="Organization name")
    args = parser.parse_args()

    create_or_update_user(args.email, args.password, args.name, args.role, args.stores, args.org)

if __name__ == "__main__":
    main()
