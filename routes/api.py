import io
import csv
from flask import Blueprint, request, jsonify, session, Response
from routes.auth import login_required
from config import supabase

api_bp = Blueprint('api', __name__)

import uuid

def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, AttributeError, TypeError):
        return False

def verify_location_access(user, requested_location_id):
    """Verifies that the user has permission to view the requested location(s), supporting comma-separated IDs."""
    user_role = user.get('role')
    user_loc_ids = set(user.get('location_ids', []))

    if requested_location_id in ['none', 'empty']:
        return True, []

    if requested_location_id in ['all', 'portfolio', '', None]:
        if user_role == 'super_admin':
            return True, None
        return True, list(user_loc_ids)

    # Split comma-separated IDs
    req_list = [x.strip() for x in str(requested_location_id).split(',') if x.strip()]
    if not req_list:
        if user_role == 'super_admin':
            return True, None
        return True, list(user_loc_ids)

    if user_role == 'super_admin':
        valid_uuids = [x for x in req_list if is_valid_uuid(x)]
        return True, valid_uuids

    # Ensure every requested ID is a valid UUID and in user's permitted locations
    validated = []
    for lid in req_list:
        if lid in user_loc_ids:
            validated.append(lid)
        else:
            return False, []
    return True, validated

@api_bp.route('/scorecard-data')
@login_required
def get_scorecard_data():
    user = session['user']
    period_id = request.args.get('period_id')
    loc_param = request.args.get('location_id', 'all')

    # Security verification
    allowed, target_loc_ids = verify_location_access(user, loc_param)
    if not allowed:
        return jsonify({"error": "Unauthorized access to requested location."}), 403

    # If user explicitly deselected all stores
    if target_loc_ids == []:
        return jsonify({
            "period_id": period_id,
            "count": 0,
            "summary": {
                "gross_revenue_actual": 0.0,
                "gross_revenue_projected": 0.0,
                "sales_volume": 0,
                "asp": 0.0,
                "daily_avg_revenue": 0.0,
                "activations_total": 0,
                "activations_new": 0,
                "activations_renewals": 0,
                "activations_migrations": 0,
                "activations_telus_post": 0,
                "activations_koodo_post": 0,
                "activations_koodo_pre": 0,
                "koodo_finance": 0,
                "telus_finance": 0,
                "cpo_units_actual": 0,
                "cpo_units_projected": 0,
                "cpo_revenue_actual": 0.0,
                "cpo_attach_activations_count": 0,
                "cpo_avg_sale": 0.0,
                "trade_in_units": 0,
                "repairs_oow_volume": 0,
                "repairs_oow_revenue": 0.0,
                "repairs_oow_daily_avg": 0.0,
                "repair_attach_activations_count": 0,
                "repairs_insurance_volume": 0,
                "repairs_insurance_revenue": 0.0,
                "accessories_volume": 0,
                "accessories_revenue": 0.0,
                "protection_bundles_volume": 0,
                "foot_traffic_total": 0,
                "foot_traffic_daily_avg": 0.0,
                "foot_traffic_7day_ma": 0.0,
                "tickets_opened_7day_ma": 0.0,
                "conversion_rate_pct": 0.0
            },
            "store_rows": [],
            "benchmark": {}
        })

    try:
        # Default to latest period if none provided
        if not period_id:
            p_resp = supabase.table('scorecard_periods').select('id, label').order('end_date', desc=True).limit(1).execute()
            if p_resp.data:
                period_id = p_resp.data[0]['id']
            else:
                return jsonify({"error": "No periods found"}), 404

        # Query monthly_kpis
        query = supabase.table('monthly_kpis').select('*, locations(id, store_number, name, short_name, region, store_type)').eq('period_id', period_id)
        if target_loc_ids is not None:
            query = query.in_('location_id', target_loc_ids)

        kpi_resp = query.execute()
        rows = kpi_resp.data or []

        if not rows:
            return jsonify({
                "period_id": period_id,
                "count": 0,
                "summary": {},
                "store_rows": [],
                "benchmark": {}
            })

        # Aggregation
        summary = {
            "gross_revenue_actual": 0.0,
            "gross_revenue_projected": 0.0,
            "sales_volume": 0,
            "asp": 0.0,
            "daily_avg_revenue": 0.0,
            "activations_total": 0,
            "activations_new": 0,
            "activations_renewals": 0,
            "activations_migrations": 0,
            "activations_telus_post": 0,
            "activations_koodo_post": 0,
            "activations_koodo_pre": 0,
            "koodo_finance": 0,
            "telus_finance": 0,
            "cpo_units_actual": 0,
            "cpo_units_projected": 0,
            "cpo_revenue_actual": 0.0,
            "cpo_attach_activations_count": 0,
            "cpo_avg_sale": 0.0,
            "trade_in_units": 0,
            "repairs_oow_volume": 0,
            "repairs_oow_revenue": 0.0,
            "repairs_oow_daily_avg": 0.0,
            "repair_attach_activations_count": 0,
            "repairs_insurance_volume": 0,
            "repairs_insurance_revenue": 0.0,
            "accessories_volume": 0,
            "accessories_revenue": 0.0,
            "protection_bundles_volume": 0,
            "foot_traffic_total": 0,
            "foot_traffic_daily_avg": 0.0,
            "foot_traffic_7day_ma": 0.0,
            "tickets_opened_7day_ma": 0.0,
        }

        store_rows = []
        for r in rows:
            loc = r.get('locations') or {}
            for k in summary:
                val = r.get(k) or 0
                summary[k] += float(val) if isinstance(val, (int, float)) else 0

            # Store level item
            store_rows.append({
                "location_id": r.get('location_id'),
                "store_number": loc.get('store_number'),
                "name": loc.get('name'),
                "region": loc.get('region'),
                "store_type": loc.get('store_type'),
                "revenue": float(r.get('gross_revenue_actual') or 0),
                "revenue_projected": float(r.get('gross_revenue_projected') or 0),
                "sales_volume": int(r.get('sales_volume') or 0),
                "activations": int(r.get('activations_total') or 0),
                "cpo_units": int(r.get('cpo_units_actual') or 0),
                "cpo_revenue": float(r.get('cpo_revenue_actual') or 0),
                "cpo_attach_pct": round(float(r.get('cpo_attach_activations_pct') or 0) * 100, 1),
                "repairs_oow": int(r.get('repairs_oow_volume') or 0),
                "repairs_oow_rev": float(r.get('repairs_oow_revenue') or 0),
                "repairs_insurance": int(r.get('repairs_insurance_volume') or 0),
                "repairs_ins_rev": float(r.get('repairs_insurance_revenue') or 0),
                "accessories_rev": float(r.get('accessories_revenue') or 0),
                "protection_bundles": int(r.get('protection_bundles_volume') or 0),
                "traffic": int(r.get('foot_traffic_total') or 0),
                "conversion_rate_pct": float(r.get('conversion_rate_pct') or 0)
            })

        store_count = len(rows)
        # Calculate rates
        summary["cpo_attach_rate_pct"] = round((summary["cpo_attach_activations_count"] / summary["cpo_units_actual"] * 100.0) if summary["cpo_units_actual"] > 0 else 0.0, 1)
        summary["repair_attach_rate_pct"] = round((summary["repair_attach_activations_count"] / summary["repairs_oow_volume"] * 100.0) if summary["repairs_oow_volume"] > 0 else 0.0, 1)
        summary["conversion_rate_pct"] = round(((summary["activations_total"] + summary["cpo_units_actual"] + summary["repairs_oow_volume"]) / summary["foot_traffic_total"] * 100.0) if summary["foot_traffic_total"] > 0 else 0.0, 2)
        summary["asp"] = round(summary["gross_revenue_actual"] / summary["sales_volume"], 2) if summary["sales_volume"] > 0 else 0.0
        summary["daily_avg_revenue"] = round(summary["daily_avg_revenue"] / store_count, 2) if store_count > 0 else 0.0

        # Anonymized Regional Benchmark (e.g. WEST Region Average across all franchise stores)
        benchmark = {}
        try:
            sample_reg = store_rows[0].get('region', 'WEST') if store_rows else 'WEST'
            bm_resp = supabase.table('monthly_kpis').select('gross_revenue_actual, sales_volume, activations_total, cpo_units_actual, repairs_oow_volume, foot_traffic_total, locations!inner(region, store_type)').eq('period_id', period_id).eq('locations.region', sample_reg).eq('locations.store_type', 'franchise').execute()
            bm_data = bm_resp.data or []
            if bm_data:
                b_cnt = len(bm_data)
                benchmark = {
                    "region": sample_reg,
                    "store_count": b_cnt,
                    "avg_revenue": round(sum(float(x.get('gross_revenue_actual') or 0) for x in bm_data) / b_cnt, 2),
                    "avg_activations": round(sum(int(x.get('activations_total') or 0) for x in bm_data) / b_cnt, 1),
                    "avg_cpo": round(sum(int(x.get('cpo_units_actual') or 0) for x in bm_data) / b_cnt, 1),
                    "avg_repairs": round(sum(int(x.get('repairs_oow_volume') or 0) for x in bm_data) / b_cnt, 1),
                    "avg_traffic": round(sum(int(x.get('foot_traffic_total') or 0) for x in bm_data) / b_cnt, 1)
                }
        except Exception as e:
            print(f"[WARN] Benchmark error: {e}")

        # Sort store rows by revenue descending
        store_rows.sort(key=lambda x: x["revenue"], reverse=True)

        return jsonify({
            "period_id": period_id,
            "count": store_count,
            "summary": summary,
            "store_rows": store_rows,
            "benchmark": benchmark
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/weekly-trend')
@login_required
def get_weekly_trend():
    user = session['user']
    metric_type = request.args.get('metric_type', 'activation')
    loc_param = request.args.get('location_id', 'all')

    allowed, target_loc_ids = verify_location_access(user, loc_param)
    if not allowed:
        return jsonify({"error": "Unauthorized"}), 403

    if target_loc_ids == []:
        return jsonify({
            "metric_type": metric_type,
            "trend": []
        })

    try:
        query = supabase.table('weekly_kpis').select('week_end_date, value, wow_delta, location_id').eq('metric_type', metric_type).order('week_end_date')
        if target_loc_ids is not None:
            query = query.in_('location_id', target_loc_ids)

        resp = query.execute()
        raw_rows = resp.data or []

        # Group by week_end_date
        weekly_map = {}
        for r in raw_rows:
            w_date = r['week_end_date']
            val = float(r.get('value') or 0)
            if w_date not in weekly_map:
                weekly_map[w_date] = {"date": w_date, "total": 0.0, "count": 0}
            weekly_map[w_date]["total"] += val
            weekly_map[w_date]["count"] += 1

        trend_data = []
        for d in sorted(weekly_map.keys()):
            item = weekly_map[d]
            trend_data.append({
                "week_end_date": d,
                "total": round(item["total"], 2),
                "avg": round(item["total"] / max(1, item["count"]), 2)
            })

        return jsonify({
            "metric_type": metric_type,
            "trend": trend_data
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/export-csv')
@login_required
def export_csv():
    user = session['user']
    period_id = request.args.get('period_id')
    loc_param = request.args.get('location_id', 'all')

    allowed, target_loc_ids = verify_location_access(user, loc_param)
    if not allowed:
        return Response("Unauthorized", status=403)

    if target_loc_ids == []:
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow([
            "Store #", "Store Name", "Region", "Gross Revenue ($)", "Projected Revenue ($)",
            "Sales Volume", "ASP ($)", "Total Activations", "New Activations", "Renewals",
            "CPO Units", "CPO Revenue ($)", "CPO Attach %", "OOW Repairs", "OOW Revenue ($)",
            "Insurance Repairs", "Insurance Revenue ($)", "Accessory Revenue ($)",
            "Protection Bundles", "Foot Traffic", "Conversion Rate %"
        ])
        return Response(
            si.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=scorecard_export.csv"}
        )

    query = supabase.table('monthly_kpis').select('*, locations(store_number, name, region)').eq('period_id', period_id)
    if target_loc_ids is not None:
        query = query.in_('location_id', target_loc_ids)
    
    rows = query.execute().data or []

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow([
        "Store #", "Store Name", "Region", "Gross Revenue ($)", "Projected Revenue ($)",
        "Sales Volume", "ASP ($)", "Total Activations", "New Activations", "Renewals",
        "CPO Units", "CPO Revenue ($)", "CPO Attach %", "OOW Repairs", "OOW Revenue ($)",
        "Insurance Repairs", "Insurance Revenue ($)", "Accessory Revenue ($)",
        "Protection Bundles", "Foot Traffic", "Conversion Rate %"
    ])

    for r in rows:
        loc = r.get('locations') or {}
        cw.writerow([
            loc.get('store_number'),
            loc.get('name'),
            loc.get('region'),
            r.get('gross_revenue_actual'),
            r.get('gross_revenue_projected'),
            r.get('sales_volume'),
            r.get('asp'),
            r.get('activations_total'),
            r.get('activations_new'),
            r.get('activations_renewals'),
            r.get('cpo_units_actual'),
            r.get('cpo_revenue_actual'),
            r.get('cpo_attach_activations_pct'),
            r.get('repairs_oow_volume'),
            r.get('repairs_oow_revenue'),
            r.get('repairs_insurance_volume'),
            r.get('repairs_insurance_revenue'),
            r.get('accessories_revenue'),
            r.get('protection_bundles_volume'),
            r.get('foot_traffic_total'),
            r.get('conversion_rate_pct')
        ])

    return Response(
        si.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=scorecard_export.csv"}
    )
