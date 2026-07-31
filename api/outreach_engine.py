"""
Outreach draft generator for the Hyper A D2C Meta Ads Audit Engine.

Given one company record (a dict shaped like a row from prospect_source.json
merged with its live CRM fields), produces:
  - a LinkedIn connection request message
  - a LinkedIn follow-up message
  - a cold email with 3 subject line options
  - a follow-up email

The angle is chosen from the company's `segment` and always references a
SPECIFIC real signal already present in the record (discount_pct_found,
most_recent_ad_start_date, meta_ad_count_approx, conversion_signals_found,
etc) -- never a generic template with no company-specific detail.

Contact fields are never fabricated: decision_maker_name / business_email /
business_phone are surfaced as-is, including "Unavailable" where that is
what the audit data says.
"""

AGENCY_NAME = "Hyper A"


def _first_name(decision_maker_name):
    if not decision_maker_name or decision_maker_name == "Unavailable":
        return None
    # decision_maker_name can be "Sujata Biswas; Taniya Biswas" -- take the first
    first_person = decision_maker_name.split(";")[0].strip()
    return first_person.split(" ")[0] if first_person else None


def _greeting(decision_maker_name):
    first = _first_name(decision_maker_name)
    return f"Hi {first}," if first else "Hi there,"


def _signal_line(company):
    """Return the single most specific, real signal to open with, based on segment."""
    segment = company.get("segment", "")
    name = company.get("company_name", "your brand")
    discount = company.get("discount_pct_found") or ""
    ad_count = company.get("meta_ad_count_approx") or ""
    ad_bucket = company.get("meta_ad_count_bucket") or ""
    last_ad = company.get("most_recent_ad_start_date") or ""
    freshness = company.get("creative_freshness_bucket") or ""
    conv_signals = company.get("conversion_signals_found") or []
    conv_bucket = company.get("conversion_health_bucket") or ""

    if segment == "Extreme discounting, minimal ad support":
        return (
            f"we noticed {name} is running a sitewide sale around {discount or 'a steep markdown'} "
            f"with little to no active Meta ad support behind it right now"
        )
    if segment == "High ad spend, weak site conversion":
        return (
            f"we noticed {name} has meaningful active Meta ad volume ({ad_count or ad_bucket}) "
            f"but the storefront is light on the usual conversion levers (reviews, bundles, urgency)"
        )
    if segment == "Heavy discount dependency":
        return (
            f"we noticed {name}'s current offer sits around {discount or 'a heavy sitewide discount'}, "
            f"which usually signals reliance on markdowns rather than full-price demand"
        )
    if segment == "Active but stale creative":
        return (
            f"we noticed {name}'s last few Meta creatives have been live since {last_ad or 'a while back'} "
            f"({freshness.lower() if freshness else 'aging'}) -- often the first sign of ad fatigue"
        )
    if segment == "Weak site conversion (ad data inconclusive)":
        return (
            f"we noticed {name}'s site is missing the usual conversion signals "
            f"(reviews, bundles, urgency messaging), though we couldn't fully verify current Meta activity"
        )
    if segment == "No Meta ad presence":
        return f"we noticed {name} doesn't currently have any active Meta ads running"
    if segment == "Well-optimized (scale-up candidate)":
        sig = ", ".join(conv_signals) if conv_signals else "strong on-site conversion signals"
        return (
            f"we noticed {name} is running fresh creative with {sig} in place -- "
            f"genuinely one of the stronger setups we've audited recently"
        )
    if segment == "Low ad activity, healthy site":
        return (
            f"we noticed {name}'s site conversion signals look solid, but Meta ad activity looks "
            f"minimal ({ad_bucket or 'low'}) -- the funnel looks ready to absorb more traffic"
        )
    if segment == "Moderate opportunity (mixed signals)":
        return (
            f"we ran a quick audit on {name} and the signals are mixed -- no single dominant gap, "
            f"but a few worth a short conversation"
        )
    if segment == "Audit incomplete":
        return (
            f"we started an audit on {name} but the Meta Ad Library results were inconclusive "
            f"and/or the site was hard to read automatically -- want to confirm a few things directly"
        )
    # Fallback
    return f"we ran a quick Meta ads + site audit on {name} and found a few things worth discussing"


def _cap_first(s):
    """Capitalize only the first character; never lowercases the rest (brand
    names like 'FableStreet' must keep their internal capitalization)."""
    if not s:
        return s
    return s[0].upper() + s[1:]


def generate_outreach(company):
    name = company.get("company_name", "your brand")
    role = company.get("decision_maker_role") or "the marketing lead"
    dm_name = company.get("decision_maker_name") or "Unavailable"
    greeting = _greeting(dm_name)
    signal = _signal_line(company)
    pitch_angle = company.get("segment_pitch_angle") or "a short audit conversation"

    linkedin_connect = (
        f"{greeting} I'm with {AGENCY_NAME} -- we do Meta ads audits for Indian D2C "
        f"{company.get('industry', 'e-commerce')} brands. {_cap_first(signal)}. "
        f"Would love to connect and share a couple of quick observations."
    )

    linkedin_followup = (
        f"{greeting} following up on my note -- {signal}. "
        f"Our take: {pitch_angle} "
        f"Happy to send over the 5-minute audit summary for {name} if useful, no pitch attached."
    )

    subject_options = [
        f"Quick audit note on {name}'s Meta ads",
        f"{name} + {AGENCY_NAME}: 3 things we noticed",
        f"Found something worth flagging on {name}'s ad account",
    ]

    email_body = (
        f"{greeting}\n\n"
        f"I'm reaching out from {AGENCY_NAME} -- we run Meta ads audits specifically for Indian D2C "
        f"{company.get('industry', 'e-commerce').lower()} brands.\n\n"
        f"We ran a quick pass on {name} and {signal}.\n\n"
        f"Our suggested angle: {pitch_angle}\n\n"
        f"If it's useful, I can send over the full breakdown (creative freshness, discount depth, "
        f"conversion signals) we captured for {name} -- no cost, no obligation, just want your take on "
        f"whether it matches what you're seeing internally.\n\n"
        f"Worth 15 minutes this week or next?\n\n"
        f"Best,\n{AGENCY_NAME}"
    )

    followup_email = (
        f"{greeting}\n\n"
        f"Circling back on my note about {name} -- totally understand if it got buried. "
        f"Short version: {signal}, and our read is that {pitch_angle if pitch_angle else 'a short audit could help'}\n\n"
        f"If timing's off, no worries -- happy to send the audit summary either way so you have it on file.\n\n"
        f"Best,\n{AGENCY_NAME}"
    )

    return {
        "company_name": name,
        "decision_maker_name": dm_name,
        "decision_maker_role": role,
        "decision_maker_linkedin": company.get("decision_maker_linkedin", ""),
        "business_email": company.get("business_email", "Unavailable"),
        "business_phone": company.get("business_phone", "Unavailable"),
        "research_note": company.get("audit_notes", ""),
        "segment": company.get("segment"),
        "linkedin_connect": linkedin_connect,
        "linkedin_followup": linkedin_followup,
        "email_subject_options": subject_options,
        "email_body": email_body,
        "followup_email_body": followup_email,
    }
