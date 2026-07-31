"""
Static reference data for the Hyper A D2C Meta Ads Audit Engine (Vercel/Postgres build).

This module holds definitions that do NOT come from prospect_source.json:
the 10 segment definitions (pain point / pitch angle), the 6-category
scoring framework documentation, and the pipeline stage list.

The actual per-company data (200 real Indian D2C companies with every
audit signal already computed) lives in api/prospect_source.json and is
loaded verbatim by index.py at seed time -- nothing in that file is
recomputed or altered here.
"""

import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROSPECT_SOURCE_PATH = os.path.join(BASE_DIR, "prospect_source.json")

# ---------------------------------------------------------------------------
# Pipeline stages (CRM)
# ---------------------------------------------------------------------------
PIPELINE_STAGES = [
    "N/A",
    "New Lead",
    "Audit Scheduled",
    "Audit Complete",
    "Ready for Outreach",
    "Contacted",
    "Replied",
    "Meeting Booked",
    "Proposal Sent",
    "Won",
    "Lost",
]

# ---------------------------------------------------------------------------
# The 10 segments -- static definitions for display. Live counts are always
# pulled from the DB (see /api/segments), never hardcoded.
# ---------------------------------------------------------------------------
SEGMENTS = [
    {
        "name": "Extreme discounting, minimal ad support",
        "pain_point": "Discounting 50%+ sitewide with little to no active Meta ad support.",
        "pitch_angle": "Full-funnel rebuild pairing a first real Meta push with reducing blanket discounting.",
    },
    {
        "name": "High ad spend, weak site conversion",
        "pain_point": "Meaningful active ad volume but the storefront lacks reviews/bundles/urgency -- spend is likely leaking through a weak funnel.",
        "pitch_angle": "CRO audit + Meta funnel realignment.",
    },
    {
        "name": "Heavy discount dependency",
        "pain_point": "Heavy-to-extreme sitewide discounting (36%+), suggesting reliance on markdowns over full-price demand generation.",
        "pitch_angle": "Offer-strategy and creative audit to reduce discount dependency.",
    },
    {
        "name": "Active but stale creative",
        "pain_point": "Ads are running, but the same creative has been live 90+ days -- ad fatigue risk.",
        "pitch_angle": "Creative refresh / testing program.",
    },
    {
        "name": "Weak site conversion (ad data inconclusive)",
        "pain_point": "No reviews/bundles/urgency on-site; Meta ad activity couldn't be reliably read.",
        "pitch_angle": "CRO audit as the opener, Meta review to follow.",
    },
    {
        "name": "No Meta ad presence",
        "pain_point": "Zero active Meta ads found.",
        "pitch_angle": "Build a first Meta ads program from scratch.",
    },
    {
        "name": "Well-optimized (scale-up candidate)",
        "pain_point": "Fresh creative, strong conversion, disciplined discounting -- already executing well.",
        "pitch_angle": "NOT a fix-it pitch -- position as a scale-up / expansion partner.",
    },
    {
        "name": "Low ad activity, healthy site",
        "pain_point": "Solid site conversion but minimal Meta spend -- funnel looks ready to absorb more traffic.",
        "pitch_angle": "Scale-up campaign strategy.",
    },
    {
        "name": "Moderate opportunity (mixed signals)",
        "pain_point": "No single dominant gap.",
        "pitch_angle": "Lightweight audit conversation to find the angle.",
    },
    {
        "name": "Audit incomplete",
        "pain_point": "Meta Ad Library was inconclusive (often a generic brand name) and/or the site fetch failed.",
        "pitch_angle": "Needs a manual audit pass before scoring / pitching confidently.",
    },
]

# ---------------------------------------------------------------------------
# Scoring framework documentation (100 pts total). Values here mirror the
# per-company score_breakdown objects already computed in prospect_source.json.
# ---------------------------------------------------------------------------
SCORING_FRAMEWORK = [
    {
        "key": "ad_activity_fit",
        "name": "Ad Activity Fit",
        "max_points": 20,
        "description": (
            "Reflects proven Meta budget. Peaks at moderate active spenders "
            "(9-20 ads = 20 pts) -- the sweet spot for an agency partnership: "
            "proven willingness to spend, not yet locked into a huge existing "
            "agency relationship."
        ),
    },
    {
        "key": "creative_fatigue_signal",
        "name": "Creative Fatigue Signal",
        "max_points": 20,
        "description": (
            "Stale creative scores highest (20) since it's the clearest, most "
            "sellable audit story; Fresh creative scores lowest (4)."
        ),
    },
    {
        "key": "discount_dependency_signal",
        "name": "Discount Dependency Signal",
        "max_points": 20,
        "description": (
            "Extreme discounting scores highest (20) -- the biggest "
            "margin-erosion story to pitch against."
        ),
    },
    {
        "key": "conversion_weakness_signal",
        "name": "Conversion Weakness Signal",
        "max_points": 15,
        "description": "Weak site conversion scores highest (15).",
    },
    {
        "key": "accessibility",
        "name": "Accessibility",
        "max_points": 15,
        "description": "5 base points, +10 if a named decision-maker was identified.",
    },
    {
        "key": "category_fit",
        "name": "Category Fit",
        "max_points": 10,
        "description": (
            "Flat 10 for all companies in this list -- every one already fits "
            "the agency's D2C fashion / apparel / beauty / lifestyle target."
        ),
    },
]

SCORE_TIERS = [
    {"tier": "A", "range": "75-100", "meaning": "Priority outreach"},
    {"tier": "B", "range": "60-74", "meaning": "Standard outreach"},
    {"tier": "C", "range": "45-59", "meaning": "Nurture / lightweight touch"},
    {"tier": "D", "range": "Below 45", "meaning": "Deprioritize"},
]


def load_prospects():
    """Load the 200 finalized prospect records verbatim. No recomputation."""
    with open(PROSPECT_SOURCE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def initial_pipeline_stage(record):
    """Seed rule: tie CRM stage to real audit state, not an arbitrary default."""
    if record.get("audit_completeness") == "Fully audited":
        return "Audit Complete"
    return "New Lead"
