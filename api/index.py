"""
Hyper A D2C Meta Ads Audit Engine -- Vercel / Postgres version.

WSGI entrypoint for Vercel's @vercel/python builder. Connects to Postgres
via DATABASE_URL (or POSTGRES_URL / POSTGRES_URL_NON_POOLING /
POSTGRES_PRISMA_URL, as provided by Vercel's Storage tab), lazily creates
its schema and seeds the 200-company dataset from prospect_source.json on
first request.
"""

import sys
import os

# ---------------------------------------------------------------------------
# Vercel's Python runtime does NOT add this file's own directory to
# sys.path, so a plain `from seed_data import (...)` fails with
# ModuleNotFoundError in production even though seed_data.py sits right
# next to this file. Fix: explicitly add our own directory to sys.path
# BEFORE importing sibling modules.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import csv
import io
import json

import psycopg2
import psycopg2.extras
from flask import Flask, jsonify, request, Response, render_template

from seed_data import (
    PIPELINE_STAGES,
    SEGMENTS,
    SCORING_FRAMEWORK,
    SCORE_TIERS,
    load_prospects,
    initial_pipeline_stage,
)
from outreach_engine import generate_outreach

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(os.path.dirname(BASE_DIR), "templates")
STATIC_DIR = os.path.join(os.path.dirname(BASE_DIR), "static")

app = Flask(
    __name__,
    template_folder=TEMPLATE_DIR,
    static_folder=STATIC_DIR,
)

_initialized = False


# ---------------------------------------------------------------------------
# DB connection
# ---------------------------------------------------------------------------

def get_database_url():
    for key in ("DATABASE_URL", "POSTGRES_URL", "POSTGRES_URL_NON_POOLING", "POSTGRES_PRISMA_URL"):
        val = os.environ.get(key)
        if val:
            return val
    return None


def get_conn():
    url = get_database_url()
    if not url:
        raise RuntimeError(
            "No database connection string found. Set DATABASE_URL (or "
            "POSTGRES_URL / POSTGRES_URL_NON_POOLING / POSTGRES_PRISMA_URL)."
        )
    return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)


SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    prospect_id TEXT UNIQUE,
    company_name TEXT NOT NULL,
    industry TEXT,
    sub_category TEXT,
    website TEXT,
    linkedin_company TEXT,
    instagram_lookup TEXT,
    decision_maker_name TEXT,
    decision_maker_role TEXT,
    decision_maker_linkedin TEXT,
    business_email TEXT,
    business_phone TEXT,
    contact_confidence TEXT,
    contact_data_score INTEGER,
    meta_ad_count_approx TEXT,
    meta_ad_count_bucket TEXT,
    meta_data_confidence TEXT,
    most_recent_ad_start_date TEXT,
    creative_freshness_bucket TEXT,
    discount_pct_found TEXT,
    discount_depth_bucket TEXT,
    conversion_signals_found TEXT,
    conversion_health_bucket TEXT,
    audit_date TEXT,
    audit_completeness TEXT,
    audit_notes TEXT,
    segment TEXT,
    segment_pain_point TEXT,
    segment_pitch_angle TEXT,
    score_breakdown TEXT,
    opportunity_score INTEGER,
    score_tier TEXT,
    pipeline_stage TEXT DEFAULT 'N/A',
    notes TEXT DEFAULT '',
    follow_up_date TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

COLUMNS = [
    "prospect_id", "company_name", "industry", "sub_category", "website",
    "linkedin_company", "instagram_lookup", "decision_maker_name",
    "decision_maker_role", "decision_maker_linkedin", "business_email",
    "business_phone", "contact_confidence", "contact_data_score",
    "meta_ad_count_approx", "meta_ad_count_bucket", "meta_data_confidence",
    "most_recent_ad_start_date", "creative_freshness_bucket",
    "discount_pct_found", "discount_depth_bucket", "conversion_signals_found",
    "conversion_health_bucket", "audit_date", "audit_completeness",
    "audit_notes", "segment", "segment_pain_point", "segment_pitch_angle",
    "score_breakdown", "opportunity_score", "score_tier", "pipeline_stage",
    "notes", "follow_up_date",
]


def ensure_schema_and_seed():
    """Idempotent: create schema if missing, seed 200 companies if table is empty."""
    global _initialized
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(SCHEMA)
        cur.execute(
            "CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        conn.commit()

        # One-time reset (runs exactly once, guarded by app_meta, then never
        # again): the pipeline stage list was simplified and every company's
        # stage is reset to N/A so nobody is stuck on a stage value from an
        # earlier version of this app. After this runs once, stage changes
        # made through the app persist normally across deploys/cold starts.
        cur.execute("SELECT value FROM app_meta WHERE key = %s", ("stage_reset_v1",))
        already_reset = cur.fetchone()
        if not already_reset:
            cur.execute("UPDATE companies SET pipeline_stage = 'N/A'")
            cur.execute(
                "INSERT INTO app_meta (key, value) VALUES (%s, %s) "
                "ON CONFLICT (key) DO NOTHING",
                ("stage_reset_v1", "done"),
            )
            conn.commit()

        cur.execute("SELECT COUNT(*) AS c FROM companies")
        count = cur.fetchone()["c"]
        if count == 0:
            prospects = load_prospects()
            col_names = ", ".join(COLUMNS)
            placeholders = ", ".join(["%s"] * len(COLUMNS))
            insert_sql = f"INSERT INTO companies ({col_names}) VALUES ({placeholders})"
            for rec in prospects:
                row = {
                    "prospect_id": rec.get("prospect_id"),
                    "company_name": rec.get("company_name"),
                    "industry": rec.get("industry"),
                    "sub_category": rec.get("sub_category"),
                    "website": rec.get("website"),
                    "linkedin_company": rec.get("linkedin_company"),
                    "instagram_lookup": rec.get("instagram_lookup"),
                    "decision_maker_name": rec.get("decision_maker_name"),
                    "decision_maker_role": rec.get("decision_maker_role"),
                    "decision_maker_linkedin": rec.get("decision_maker_linkedin"),
                    "business_email": rec.get("business_email"),
                    "business_phone": rec.get("business_phone"),
                    "contact_confidence": rec.get("contact_confidence"),
                    "contact_data_score": rec.get("contact_data_score"),
                    "meta_ad_count_approx": rec.get("meta_ad_count_approx"),
                    "meta_ad_count_bucket": rec.get("meta_ad_count_bucket"),
                    "meta_data_confidence": rec.get("meta_data_confidence"),
                    "most_recent_ad_start_date": rec.get("most_recent_ad_start_date"),
                    "creative_freshness_bucket": rec.get("creative_freshness_bucket"),
                    "discount_pct_found": rec.get("discount_pct_found"),
                    "discount_depth_bucket": rec.get("discount_depth_bucket"),
                    "conversion_signals_found": json.dumps(rec.get("conversion_signals_found") or []),
                    "conversion_health_bucket": rec.get("conversion_health_bucket"),
                    "audit_date": rec.get("audit_date"),
                    "audit_completeness": rec.get("audit_completeness"),
                    "audit_notes": rec.get("audit_notes"),
                    "segment": rec.get("segment"),
                    "segment_pain_point": rec.get("segment_pain_point"),
                    "segment_pitch_angle": rec.get("segment_pitch_angle"),
                    "score_breakdown": json.dumps(rec.get("score_breakdown") or {}),
                    "opportunity_score": rec.get("opportunity_score"),
                    "score_tier": rec.get("score_tier"),
                    "pipeline_stage": initial_pipeline_stage(rec),
                    "notes": "",
                    "follow_up_date": "",
                }
                cur.execute(insert_sql, [row[c] for c in COLUMNS])
            conn.commit()
        _initialized = True
    finally:
        conn.close()


@app.before_request
def _before_request_seed():
    # Cheap after the first successful call in a warm serverless instance;
    # still safe (idempotent) to re-run per cold start.
    if request.path == "/api/health":
        return  # health check handles its own errors / init
    global _initialized
    if not _initialized:
        ensure_schema_and_seed()


def row_to_dict(row):
    d = dict(row)
    if d.get("conversion_signals_found"):
        try:
            d["conversion_signals_found"] = json.loads(d["conversion_signals_found"])
        except (TypeError, ValueError):
            d["conversion_signals_found"] = []
    if d.get("score_breakdown"):
        try:
            d["score_breakdown"] = json.loads(d["score_breakdown"])
        except (TypeError, ValueError):
            d["score_breakdown"] = {}
    return d


# ---------------------------------------------------------------------------
# Routes -- pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def api_health():
    try:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(SCHEMA)
            conn.commit()
            cur.execute("SELECT COUNT(*) AS c FROM companies")
            count = cur.fetchone()["c"]
            if count == 0:
                ensure_schema_and_seed()
                cur.execute("SELECT COUNT(*) AS c FROM companies")
                count = cur.fetchone()["c"]
        finally:
            conn.close()
        return jsonify({
            "status": "ok",
            "companies": count,
            "database_url_set": get_database_url() is not None,
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "database_url_set": get_database_url() is not None,
        }), 500


# ---------------------------------------------------------------------------
# Routes -- meta / static reference data
# ---------------------------------------------------------------------------

@app.route("/api/meta")
def api_meta():
    conn = get_conn()
    try:
        cur = conn.cursor()

        def distinct(col):
            cur.execute(
                f"SELECT DISTINCT {col} AS v FROM companies WHERE {col} IS NOT NULL AND {col} != '' ORDER BY {col}"
            )
            return [r["v"] for r in cur.fetchall()]

        result = {
            "industries": distinct("industry"),
            "segments": distinct("segment"),
            "score_tiers": ["A", "B", "C", "D"],
            "pipeline_stages": PIPELINE_STAGES,
            "meta_ad_count_buckets": distinct("meta_ad_count_bucket"),
            "discount_depth_buckets": distinct("discount_depth_bucket"),
            "audit_completeness_values": distinct("audit_completeness"),
            "creative_freshness_buckets": distinct("creative_freshness_bucket"),
            "conversion_health_buckets": distinct("conversion_health_bucket"),
        }
        return jsonify(result)
    finally:
        conn.close()


@app.route("/api/segments")
def api_segments():
    conn = get_conn()
    try:
        cur = conn.cursor()
        result = []
        for seg in SEGMENTS:
            cur.execute(
                "SELECT COUNT(*) AS c, AVG(opportunity_score) AS avgscore FROM companies WHERE segment = %s",
                (seg["name"],),
            )
            row = cur.fetchone()
            avg = row["avgscore"]
            result.append({
                **seg,
                "company_count": row["c"] or 0,
                "avg_opportunity_score": round(float(avg), 1) if avg is not None else None,
            })
        return jsonify(result)
    finally:
        conn.close()


@app.route("/api/scoring")
def api_scoring():
    conn = get_conn()
    try:
        cur = conn.cursor()
        tier_counts = {}
        for t in ["A", "B", "C", "D"]:
            cur.execute("SELECT COUNT(*) AS c FROM companies WHERE score_tier = %s", (t,))
            tier_counts[t] = cur.fetchone()["c"]
        return jsonify({
            "framework": SCORING_FRAMEWORK,
            "tiers": SCORE_TIERS,
            "tier_counts": tier_counts,
            "total_companies": sum(tier_counts.values()),
        })
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Routes -- companies CRUD
# ---------------------------------------------------------------------------

FILTERABLE = {
    "industry": "industry",
    "segment": "segment",
    "score_tier": "score_tier",
    "pipeline_stage": "pipeline_stage",
    "meta_ad_count_bucket": "meta_ad_count_bucket",
    "discount_depth_bucket": "discount_depth_bucket",
    "audit_completeness": "audit_completeness",
}

SORTABLE = {
    "company_name", "industry", "segment", "score_tier", "opportunity_score",
    "pipeline_stage", "meta_ad_count_bucket", "discount_depth_bucket",
    "creative_freshness_bucket", "conversion_health_bucket", "audit_completeness",
    "audit_date",
}


def build_filtered_query(args):
    where = []
    params = []
    for qkey, col in FILTERABLE.items():
        val = args.get(qkey)
        if val:
            where.append(f"{col} = %s")
            params.append(val)
    q = args.get("q")
    if q:
        where.append("(company_name ILIKE %s OR sub_category ILIKE %s OR decision_maker_name ILIKE %s)")
        like = f"%{q}%"
        params.extend([like, like, like])

    sql = "SELECT * FROM companies"
    if where:
        sql += " WHERE " + " AND ".join(where)

    sort = args.get("sort", "opportunity_score")
    if sort not in SORTABLE:
        sort = "opportunity_score"
    direction = args.get("dir", "desc").lower()
    direction = "ASC" if direction == "asc" else "DESC"
    sql += f" ORDER BY {sort} {direction}"
    return sql, params


@app.route("/api/companies")
def api_companies_list():
    conn = get_conn()
    try:
        cur = conn.cursor()
        sql, params = build_filtered_query(request.args)
        cur.execute(sql, params)
        rows = cur.fetchall()
        companies = [row_to_dict(r) for r in rows]
        return jsonify({"companies": companies, "count": len(companies)})
    finally:
        conn.close()


@app.route("/api/companies/<int:company_id>", methods=["GET"])
def api_company_get(company_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM companies WHERE id = %s", (company_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "not found"}), 404
        return jsonify(row_to_dict(row))
    finally:
        conn.close()


EDITABLE_FIELDS = [
    "pipeline_stage", "notes", "follow_up_date", "segment",
    "decision_maker_name", "decision_maker_role", "decision_maker_linkedin",
    "business_email", "business_phone", "company_name", "industry",
    "sub_category", "website",
]


@app.route("/api/companies/<int:company_id>", methods=["PUT"])
def api_company_update(company_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        data = request.get_json(force=True) or {}
        cur.execute("SELECT * FROM companies WHERE id = %s", (company_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "not found"}), 404

        updates = []
        params = []
        for field in EDITABLE_FIELDS:
            if field in data:
                updates.append(f"{field} = %s")
                params.append(data[field])
        if not updates:
            return jsonify({"error": "no editable fields provided"}), 400

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(company_id)
        cur.execute(f"UPDATE companies SET {', '.join(updates)} WHERE id = %s", params)
        conn.commit()
        cur.execute("SELECT * FROM companies WHERE id = %s", (company_id,))
        row = cur.fetchone()
        return jsonify(row_to_dict(row))
    finally:
        conn.close()


@app.route("/api/companies/<int:company_id>", methods=["DELETE"])
def api_company_delete(company_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM companies WHERE id = %s", (company_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "not found"}), 404
        cur.execute("DELETE FROM companies WHERE id = %s", (company_id,))
        conn.commit()
        return jsonify({"deleted": company_id})
    finally:
        conn.close()


@app.route("/api/companies", methods=["POST"])
def api_company_create():
    conn = get_conn()
    try:
        cur = conn.cursor()
        data = request.get_json(force=True) or {}
        if not data.get("company_name"):
            return jsonify({"error": "company_name is required"}), 400

        row = {
            "prospect_id": data.get("prospect_id") or f"MANUAL-{os.urandom(3).hex()}",
            "company_name": data.get("company_name"),
            "industry": data.get("industry", ""),
            "sub_category": data.get("sub_category", ""),
            "website": data.get("website", ""),
            "linkedin_company": data.get("linkedin_company", ""),
            "instagram_lookup": data.get("instagram_lookup", ""),
            "decision_maker_name": data.get("decision_maker_name", "Unavailable"),
            "decision_maker_role": data.get("decision_maker_role", ""),
            "decision_maker_linkedin": data.get("decision_maker_linkedin", ""),
            "business_email": data.get("business_email", "Unavailable"),
            "business_phone": data.get("business_phone", "Unavailable"),
            "contact_confidence": data.get("contact_confidence", "Unavailable"),
            "contact_data_score": data.get("contact_data_score", 0),
            "meta_ad_count_approx": data.get("meta_ad_count_approx", "Not verified"),
            "meta_ad_count_bucket": data.get("meta_ad_count_bucket", "Not verified"),
            "meta_data_confidence": data.get("meta_data_confidence", "Not verified"),
            "most_recent_ad_start_date": data.get("most_recent_ad_start_date", ""),
            "creative_freshness_bucket": data.get("creative_freshness_bucket", "Not verified"),
            "discount_pct_found": data.get("discount_pct_found", ""),
            "discount_depth_bucket": data.get("discount_depth_bucket", "Not audited"),
            "conversion_signals_found": json.dumps(data.get("conversion_signals_found", [])),
            "conversion_health_bucket": data.get("conversion_health_bucket", "Not audited"),
            "audit_date": data.get("audit_date", ""),
            "audit_completeness": data.get("audit_completeness", "Needs audit"),
            "audit_notes": data.get("audit_notes", "Manually added company -- not yet audited."),
            "segment": data.get("segment", "Audit incomplete"),
            "segment_pain_point": data.get("segment_pain_point", ""),
            "segment_pitch_angle": data.get("segment_pitch_angle", ""),
            "score_breakdown": json.dumps(data.get("score_breakdown", {})),
            "opportunity_score": data.get("opportunity_score", 0),
            "score_tier": data.get("score_tier", "D"),
            "pipeline_stage": data.get("pipeline_stage", "N/A"),
            "notes": data.get("notes", ""),
            "follow_up_date": data.get("follow_up_date", ""),
        }
        col_names = ", ".join(COLUMNS)
        placeholders = ", ".join(["%s"] * len(COLUMNS))
        cur.execute(
            f"INSERT INTO companies ({col_names}) VALUES ({placeholders}) RETURNING id",
            [row[c] for c in COLUMNS],
        )
        new_id = cur.fetchone()["id"]
        conn.commit()
        cur.execute("SELECT * FROM companies WHERE id = %s", (new_id,))
        new_row = cur.fetchone()
        return jsonify(row_to_dict(new_row)), 201
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Routes -- outreach + export
# ---------------------------------------------------------------------------

@app.route("/api/companies/<int:company_id>/outreach")
def api_company_outreach(company_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM companies WHERE id = %s", (company_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "not found"}), 404
        company = row_to_dict(row)
        draft = generate_outreach(company)
        return jsonify(draft)
    finally:
        conn.close()


@app.route("/api/export/csv")
def api_export_csv():
    conn = get_conn()
    try:
        cur = conn.cursor()
        sql, params = build_filtered_query(request.args)
        cur.execute(sql, params)
        rows = cur.fetchall()
        companies = [row_to_dict(r) for r in rows]

        output = io.StringIO()
        fieldnames = [
            "prospect_id", "company_name", "industry", "sub_category", "website",
            "decision_maker_name", "decision_maker_role", "business_email",
            "business_phone", "contact_confidence", "meta_ad_count_approx",
            "meta_ad_count_bucket", "creative_freshness_bucket",
            "most_recent_ad_start_date", "discount_pct_found",
            "discount_depth_bucket", "conversion_health_bucket",
            "audit_completeness", "segment", "opportunity_score", "score_tier",
            "pipeline_stage", "follow_up_date", "notes", "audit_notes",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for c in companies:
            writer.writerow(c)

        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=d2c_audit_engine_export.csv"},
        )
    finally:
        conn.close()


# Local dev entrypoint (not used by Vercel, which imports `app` directly).
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5051, debug=True)
