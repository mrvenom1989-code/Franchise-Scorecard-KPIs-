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
            # Requirement: Total Activations is Total New Activations plus Migrations
            act_new = int(r.get('activations_new') or 0)
            act_mig = int(r.get('activations_migrations') or 0)
            r['activations_total'] = act_new + act_mig

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

        # 1. Regional, Global & Portfolio Benchmarks
        regional_benchmark = {}
        global_benchmark = {}
        portfolio_benchmark = {}
        try:
            bm_all_resp = supabase.table('monthly_kpis').select('gross_revenue_actual, sales_volume, activations_total, cpo_units_actual, repairs_oow_volume, foot_traffic_total, location_id, locations!inner(region, store_type)').eq('period_id', period_id).eq('locations.store_type', 'franchise').execute()
            all_bm_rows = bm_all_resp.data or []
            if all_bm_rows:
                sample_reg = store_rows[0].get('region', 'WEST') if store_rows else 'WEST'
                reg_rows = [r for r in all_bm_rows if r.get('locations', {}).get('region') == sample_reg]

                def make_bm_dict(rows_subset, lbl, reg_name=None):
                    c = len(rows_subset)
                    if c == 0: return {}
                    tot_act = sum(int(x.get('activations_total') or 0) for x in rows_subset)
                    tot_cpo = sum(int(x.get('cpo_units_actual') or 0) for x in rows_subset)
                    tot_rep = sum(int(x.get('repairs_oow_volume') or 0) for x in rows_subset)
                    tot_traf = sum(int(x.get('foot_traffic_total') or 0) for x in rows_subset)
                    return {
                        "label": lbl,
                        "region": reg_name or "National",
                        "store_count": c,
                        "avg_revenue": round(sum(float(x.get('gross_revenue_actual') or 0) for x in rows_subset) / c, 2),
                        "avg_sales_volume": round(sum(int(x.get('sales_volume') or 0) for x in rows_subset) / c, 1),
                        "avg_activations": round(tot_act / c, 1),
                        "avg_cpo": round(tot_cpo / c, 1),
                        "avg_repairs": round(tot_rep / c, 1),
                        "avg_traffic": round(tot_traf / c, 1),
                        "conversion_rate_pct": round(((tot_act + tot_cpo + tot_rep) / tot_traf) * 100, 2) if tot_traf > 0 else 0.0
                    }

                regional_benchmark = make_bm_dict(reg_rows, f"{sample_reg} Region Average", sample_reg)
                global_benchmark = make_bm_dict(all_bm_rows, "Global Network Average (All Stores)")

                # User's Portfolio Benchmark
                user_acc_resp = supabase.table('user_location_access').select('location_id').eq('user_id', user['id']).execute()
                user_loc_ids = {r['location_id'] for r in (user_acc_resp.data or [])}
                if user_loc_ids and len(user_loc_ids) > 1:
                    port_rows = [r for r in all_bm_rows if r.get('location_id') in user_loc_ids]
                    if port_rows:
                        portfolio_benchmark = make_bm_dict(port_rows, f"Your Portfolio Average ({len(port_rows)} Stores)")
        except Exception as e:
            print(f"[WARN] Benchmark error: {e}")

        # Sort store rows by revenue descending
        store_rows.sort(key=lambda x: x["revenue"], reverse=True)

        return jsonify({
            "period_id": period_id,
            "count": store_count,
            "summary": summary,
            "store_rows": store_rows,
            "benchmark": regional_benchmark,  # backward compatibility
            "regional_benchmark": regional_benchmark,
            "global_benchmark": global_benchmark,
            "portfolio_benchmark": portfolio_benchmark
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

@api_bp.route('/monthly-trend')
@login_required
def get_monthly_trend():
    user = session['user']
    loc_param = request.args.get('location_id', 'all')

    allowed, target_loc_ids = verify_location_access(user, loc_param)
    if not allowed:
        return jsonify({"error": "Unauthorized"}), 403

    if target_loc_ids == []:
        return jsonify({"trend": [], "mom": {}, "yoy": {}})

    try:
        # Fetch all periods (exclude 'Jan 26 MTD' to prevent duplicate Jan data points)
        p_resp = supabase.table('scorecard_periods').select('id, label, start_date, end_date').order('start_date').execute()
        periods = [p for p in (p_resp.data or []) if p['label'] != 'Jan 26 MTD']
        p_map = {p['id']: p for p in periods}

        # Query monthly_kpis for target locations
        query = supabase.table('monthly_kpis').select(
            'period_id, location_id, gross_revenue_actual, sales_volume, '
            'activations_total, activations_new, activations_migrations, '
            'activations_telus_post, activations_koodo_post, activations_koodo_pre, activations_renewals, '
            'cpo_units_actual, cpo_revenue_actual, '
            'repairs_oow_volume, repairs_oow_revenue, repairs_insurance_volume, repairs_insurance_revenue, '
            'accessories_revenue, accessories_volume, protection_bundles_volume, foot_traffic_total'
        )
        if target_loc_ids is not None:
            query = query.in_('location_id', target_loc_ids)

        kpis = query.execute().data or []

        # Group by period
        grouped = {}
        for p in periods:
            pid = p['id']
            grouped[pid] = {
                "period_id": pid,
                "label": p['label'],
                "start_date": p['start_date'],
                "end_date": p['end_date'],
                "gross_revenue_actual": 0.0,
                "sales_volume": 0,
                "activations_total": 0,
                "activations_new": 0,
                "activations_migrations": 0,
                "activations_telus_post": 0,
                "activations_koodo_post": 0,
                "activations_koodo_pre": 0,
                "activations_renewals": 0,
                "cpo_units_actual": 0,
                "cpo_revenue_actual": 0.0,
                "repairs_oow_volume": 0,
                "repairs_oow_revenue": 0.0,
                "repairs_insurance_volume": 0,
                "repairs_insurance_revenue": 0.0,
                "repairs_total_volume": 0,
                "repairs_total_revenue": 0.0,
                "accessories_revenue": 0.0,
                "accessories_volume": 0,
                "protection_bundles_volume": 0,
                "foot_traffic_total": 0,
                "conversion_rate_pct": 0.0,
                "store_count": 0
            }

        for r in kpis:
            pid = r.get('period_id')
            if pid not in grouped:
                continue
            g = grouped[pid]
            g["store_count"] += 1
            g["gross_revenue_actual"] += float(r.get('gross_revenue_actual') or 0)
            g["sales_volume"] += int(r.get('sales_volume') or 0)

            act_new = int(r.get('activations_new') or 0)
            act_mig = int(r.get('activations_migrations') or 0)
            g["activations_new"] += act_new
            g["activations_migrations"] += act_mig
            g["activations_total"] += (act_new + act_mig)
            g["activations_telus_post"] += int(r.get('activations_telus_post') or 0)
            g["activations_koodo_post"] += int(r.get('activations_koodo_post') or 0)
            g["activations_koodo_pre"] += int(r.get('activations_koodo_pre') or 0)
            g["activations_renewals"] += int(r.get('activations_renewals') or 0)

            g["cpo_units_actual"] += int(r.get('cpo_units_actual') or 0)
            g["cpo_revenue_actual"] += float(r.get('cpo_revenue_actual') or 0)

            rep_oow = int(r.get('repairs_oow_volume') or 0)
            rep_oow_rev = float(r.get('repairs_oow_revenue') or 0)
            rep_ins = int(r.get('repairs_insurance_volume') or 0)
            rep_ins_rev = float(r.get('repairs_insurance_revenue') or 0)
            g["repairs_oow_volume"] += rep_oow
            g["repairs_oow_revenue"] += rep_oow_rev
            g["repairs_insurance_volume"] += rep_ins
            g["repairs_insurance_revenue"] += rep_ins_rev
            g["repairs_total_volume"] += (rep_oow + rep_ins)
            g["repairs_total_revenue"] += (rep_oow_rev + rep_ins_rev)

            g["accessories_revenue"] += float(r.get('accessories_revenue') or 0)
            g["accessories_volume"] += int(r.get('accessories_volume') or 0)
            g["protection_bundles_volume"] += int(r.get('protection_bundles_volume') or 0)
            g["foot_traffic_total"] += int(r.get('foot_traffic_total') or 0)

        # Include periods that have recorded activity
        trend_list = [g for g in grouped.values() if g["store_count"] > 0]
        trend_list.sort(key=lambda x: x["start_date"])

        for g in trend_list:
            g["gross_revenue_actual"] = round(g["gross_revenue_actual"], 2)
            g["cpo_revenue_actual"] = round(g["cpo_revenue_actual"], 2)
            g["repairs_oow_revenue"] = round(g["repairs_oow_revenue"], 2)
            g["repairs_insurance_revenue"] = round(g["repairs_insurance_revenue"], 2)
            g["repairs_total_revenue"] = round(g["repairs_total_revenue"], 2)
            g["accessories_revenue"] = round(g["accessories_revenue"], 2)
            tot_sales = g["activations_total"] + g["cpo_units_actual"] + g["repairs_oow_volume"]
            g["conversion_rate_pct"] = round((tot_sales / g["foot_traffic_total"] * 100), 2) if g["foot_traffic_total"] > 0 else 0.0

        def calc_delta(c_val, p_val):
            diff = c_val - p_val
            pct = round((diff / p_val * 100), 1) if p_val > 0 else (100.0 if diff > 0 else 0.0)
            return {"current": c_val, "previous": p_val, "delta": round(diff, 2), "pct": pct}

        # Attach prior year matching metrics to each period in trend_list
        for item in trend_list:
            try:
                i_year, i_month = int(item["start_date"][:4]), int(item["start_date"][5:7])
                target_year = i_year - 1
                py_match = next((t for t in trend_list if int(t["start_date"][:4]) == target_year and int(t["start_date"][5:7]) == i_month), None)
            except Exception:
                py_match = None

            if py_match:
                item["py_label"] = py_match["label"]
                item["py_revenue"] = py_match["gross_revenue_actual"]
                item["py_activations"] = py_match["activations_total"]
                item["py_cpo_units"] = py_match["cpo_units_actual"]
                item["py_cpo_revenue"] = py_match["cpo_revenue_actual"]
                item["py_repairs_volume"] = py_match["repairs_total_volume"]
                item["py_repairs_revenue"] = py_match["repairs_total_revenue"]
                item["py_traffic"] = py_match["foot_traffic_total"]
                item["py_conversion_rate_pct"] = py_match["conversion_rate_pct"]
                item["yoy_growth_revenue_pct"] = calc_delta(item["gross_revenue_actual"], py_match["gross_revenue_actual"])["pct"]
                item["yoy_growth_activations_pct"] = calc_delta(item["activations_total"], py_match["activations_total"])["pct"]
                item["yoy_growth_cpo_pct"] = calc_delta(item["cpo_units_actual"], py_match["cpo_units_actual"])["pct"]
                item["yoy_growth_repairs_pct"] = calc_delta(item["repairs_total_volume"], py_match["repairs_total_volume"])["pct"]
                item["yoy_growth_traffic_pct"] = calc_delta(item["foot_traffic_total"], py_match["foot_traffic_total"])["pct"]
            else:
                item["py_label"] = None
                item["py_revenue"] = None
                item["py_activations"] = None
                item["py_cpo_units"] = None
                item["py_cpo_revenue"] = None
                item["py_repairs_volume"] = None
                item["py_repairs_revenue"] = None
                item["py_traffic"] = None
                item["py_conversion_rate_pct"] = None
                item["yoy_growth_revenue_pct"] = None
                item["yoy_growth_activations_pct"] = None
                item["yoy_growth_cpo_pct"] = None
                item["yoy_growth_repairs_pct"] = None
                item["yoy_growth_traffic_pct"] = None

        # Build 12-Month Calendar Comparison (2025 vs 2026 by Month)
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        yoy_by_month = []
        for m_idx, m_name in enumerate(month_names, 1):
            p25 = next((t for t in trend_list if int(t["start_date"][:4]) == 2025 and int(t["start_date"][5:7]) == m_idx), None)
            p26 = next((t for t in trend_list if int(t["start_date"][:4]) == 2026 and int(t["start_date"][5:7]) == m_idx), None)

            yoy_by_month.append({
                "month_num": m_idx,
                "month_name": m_name,
                "p2025": {
                    "label": p25["label"],
                    "revenue": p25["gross_revenue_actual"],
                    "activations": p25["activations_total"],
                    "cpo_units": p25["cpo_units_actual"],
                    "repairs_volume": p25["repairs_total_volume"],
                    "traffic": p25["foot_traffic_total"],
                    "conversion_rate_pct": p25["conversion_rate_pct"]
                } if p25 else None,
                "p2026": {
                    "label": p26["label"],
                    "revenue": p26["gross_revenue_actual"],
                    "activations": p26["activations_total"],
                    "cpo_units": p26["cpo_units_actual"],
                    "repairs_volume": p26["repairs_total_volume"],
                    "traffic": p26["foot_traffic_total"],
                    "conversion_rate_pct": p26["conversion_rate_pct"]
                } if p26 else None,
                "growth": {
                    "revenue_pct": calc_delta(p26["gross_revenue_actual"], p25["gross_revenue_actual"])["pct"] if (p25 and p26) else None,
                    "activations_pct": calc_delta(p26["activations_total"], p25["activations_total"])["pct"] if (p25 and p26) else None,
                    "cpo_pct": calc_delta(p26["cpo_units_actual"], p25["cpo_units_actual"])["pct"] if (p25 and p26) else None,
                    "repairs_pct": calc_delta(p26["repairs_total_volume"], p25["repairs_total_volume"])["pct"] if (p25 and p26) else None,
                    "traffic_pct": calc_delta(p26["foot_traffic_total"], p25["foot_traffic_total"])["pct"] if (p25 and p26) else None,
                }
            })

        # MoM (Month-on-Month) deltas for the latest period vs previous period
        mom = {}
        if len(trend_list) >= 2:
            curr = trend_list[-1]
            prev = trend_list[-2]
            mom = {
                "current_period": curr["label"],
                "previous_period": prev["label"],
                "revenue": calc_delta(curr["gross_revenue_actual"], prev["gross_revenue_actual"]),
                "activations": calc_delta(curr["activations_total"], prev["activations_total"]),
                "cpo_units": calc_delta(curr["cpo_units_actual"], prev["cpo_units_actual"]),
                "cpo_revenue": calc_delta(curr["cpo_revenue_actual"], prev["cpo_revenue_actual"]),
                "repairs_volume": calc_delta(curr["repairs_total_volume"], prev["repairs_total_volume"]),
                "repairs_revenue": calc_delta(curr["repairs_total_revenue"], prev["repairs_total_revenue"]),
                "traffic": calc_delta(curr["foot_traffic_total"], prev["foot_traffic_total"]),
                "conversion_rate": calc_delta(curr["conversion_rate_pct"], prev["conversion_rate_pct"])
            }

        # YoY (Year-on-Year) deltas matching same month 1 year ago
        yoy = {}
        if trend_list:
            curr = trend_list[-1]
            curr_start = curr["start_date"]
            prior_year_match = None
            try:
                c_year, c_month = int(curr_start[:4]), int(curr_start[5:7])
                target_year = c_year - 1
                for item in trend_list:
                    i_year, i_month = int(item["start_date"][:4]), int(item["start_date"][5:7])
                    if i_year == target_year and i_month == c_month:
                        prior_year_match = item
                        break
            except Exception:
                pass

            if prior_year_match:
                yoy = {
                    "current_period": curr["label"],
                    "prior_year_period": prior_year_match["label"],
                    "revenue": calc_delta(curr["gross_revenue_actual"], prior_year_match["gross_revenue_actual"]),
                    "activations": calc_delta(curr["activations_total"], prior_year_match["activations_total"]),
                    "cpo_units": calc_delta(curr["cpo_units_actual"], prior_year_match["cpo_units_actual"]),
                    "cpo_revenue": calc_delta(curr["cpo_revenue_actual"], prior_year_match["cpo_revenue_actual"]),
                    "repairs_volume": calc_delta(curr["repairs_total_volume"], prior_year_match["repairs_total_volume"]),
                    "repairs_revenue": calc_delta(curr["repairs_total_revenue"], prior_year_match["repairs_total_revenue"]),
                    "traffic": calc_delta(curr["foot_traffic_total"], prior_year_match["foot_traffic_total"]),
                    "conversion_rate": calc_delta(curr["conversion_rate_pct"], prior_year_match["conversion_rate_pct"])
                }

        # Growth Matrix for Executive Pulse Table
        growth_matrix = []
        if trend_list:
            curr = trend_list[-1]
            prev = trend_list[-2] if len(trend_list) >= 2 else None
            py = next((t for t in trend_list if int(t["start_date"][:4]) == int(curr["start_date"][:4]) - 1 and int(t["start_date"][5:7]) == int(curr["start_date"][5:7])), None)

            metrics_def = [
                ("Gross Revenue", "revenue", "currency", curr["gross_revenue_actual"], prev["gross_revenue_actual"] if prev else None, py["gross_revenue_actual"] if py else None),
                ("Total Activations", "activations", "number", curr["activations_total"], prev["activations_total"] if prev else None, py["activations_total"] if py else None),
                ("CPO Units Sold", "cpo_units", "number", curr["cpo_units_actual"], prev["cpo_units_actual"] if prev else None, py["cpo_units_actual"] if py else None),
                ("Total Repairs", "repairs", "number", curr["repairs_total_volume"], prev["repairs_total_volume"] if prev else None, py["repairs_total_volume"] if py else None),
                ("Foot Traffic", "traffic", "number", curr["foot_traffic_total"], prev["foot_traffic_total"] if prev else None, py["foot_traffic_total"] if py else None),
                ("Conversion Rate", "conversion", "percent", curr["conversion_rate_pct"], prev["conversion_rate_pct"] if prev else None, py["conversion_rate_pct"] if py else None),
            ]

            for name, key, fmt, c_v, p_v, py_v in metrics_def:
                m_delta = calc_delta(c_v, p_v) if p_v is not None else None
                y_delta = calc_delta(c_v, py_v) if py_v is not None else None
                growth_matrix.append({
                    "name": name,
                    "key": key,
                    "format": fmt,
                    "current": c_v,
                    "current_period": curr["label"],
                    "mom_previous": p_v,
                    "mom_period": prev["label"] if prev else None,
                    "mom_pct": m_delta["pct"] if m_delta else None,
                    "mom_delta": m_delta["delta"] if m_delta else None,
                    "yoy_previous": py_v,
                    "yoy_period": py["label"] if py else None,
                    "yoy_pct": y_delta["pct"] if y_delta else None,
                    "yoy_delta": y_delta["delta"] if y_delta else None,
                })

        return jsonify({
            "trend": trend_list,
            "yoy_by_month": yoy_by_month,
            "growth_matrix": growth_matrix,
            "mom": mom,
            "yoy": yoy
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
