import re

CATEGORY_KEYWORDS = {
    "skincare": ["skin", "serum", "spf", "moisturiser", "moisturizer", "glow",
                 "acne", "sunscreen", "face wash", "toner", "cleanser", "derma",
                 "cream", "lotion", "beauty", "cosmetic", "makeup"],
    "fitness":  ["gym", "workout", "protein", "supplement", "yoga", "fitness",
                 "health", "exercise", "training", "muscle", "weight loss",
                 "nutrition", "diet", "athlete", "sports"],
    "fashion":  ["fashion", "clothing", "apparel", "outfit", "style", "wear",
                 "dress", "shoes", "accessories", "wardrobe", "trend"],
    "finance":  ["finance", "invest", "trading", "crypto", "saving", "money",
                 "stock", "mutual fund", "insurance", "loan", "banking", "fintech"],
    "food":     ["food", "recipe", "cooking", "restaurant", "snack", "drink",
                 "beverage", "cuisine", "cafe", "meal", "chef", "baking"],
    "tech":     ["tech", "gadget", "app", "software", "device", "phone",
                 "laptop", "saas", "startup", "digital", "electronics"],
}

GOAL_KEYWORDS = {
    "sales":       ["sales", "sell", "purchase", "buy", "revenue", "drive sales",
                    "online sales", "ecommerce", "shop", "order"],
    "awareness":   ["awareness", "reach", "brand", "visibility", "exposure",
                    "recognition", "introduce", "launch", "known"],
    "engagement":  ["engagement", "community", "interact", "comment", "share",
                    "followers", "likes", "viral", "buzz"],
    "conversions": ["conversion", "lead", "signup", "download", "install",
                    "register", "trial", "demo", "enquiry"],
}

TONE_KEYWORDS = {
    "luxury":         ["luxury", "premium", "exclusive", "high-end", "elite"],
    "fun, playful":   ["fun", "playful", "quirky", "bold", "energetic", "vibrant"],
    "science-backed": ["science", "clinical", "research", "dermatologist", "proven"],
    "trustworthy":    ["trust", "honest", "authentic", "reliable", "genuine"],
    "minimalist":     ["minimal", "clean", "simple", "pure", "natural"],
    "inspirational":  ["inspire", "motivate", "empower", "transform", "journey"],
}

GOAL_WEIGHTS = {
    "sales":       {"impact": 0.40, "authenticity": 0.35, "match": 0.15, "cost": 0.10},
    "awareness":   {"impact": 0.30, "authenticity": 0.20, "match": 0.35, "cost": 0.15},
    "engagement":  {"impact": 0.25, "authenticity": 0.30, "match": 0.30, "cost": 0.15},
    "conversions": {"impact": 0.45, "authenticity": 0.30, "match": 0.15, "cost": 0.10},
}


def _extract_budget(text: str, ui_budget: int) -> int:
    patterns = [
        (r"₹?\s*(\d+(?:\.\d+)?)\s*cr(?:ore)?", lambda m: int(float(m.group(1)) * 10_000_000)),
        (r"₹?\s*(\d+(?:\.\d+)?)\s*l(?:akh)?",  lambda m: int(float(m.group(1)) * 100_000)),
        (r"₹?\s*(\d+(?:\.\d+)?)\s*k",           lambda m: int(float(m.group(1)) * 1_000)),
        (r"₹\s*([\d,]+)",                        lambda m: int(m.group(1).replace(",", ""))),
        (r"\b(\d{4,})\b",                        lambda m: int(m.group(1))),
    ]
    for pattern, converter in patterns:
        match = re.search(pattern, text.lower())
        if match:
            try:
                val = converter(match)
                if 1_000 <= val <= 100_000_000:
                    return val
            except Exception:
                continue
    return ui_budget


def parse_brief(brief_text: str, budget: int = 300_000, goal_hint: str = "sales") -> dict:
    text = brief_text.lower()

    category, category_score = "skincare", 0
    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for k in keywords if k in text)
        if score > category_score:
            category_score, category = score, cat

    goal, goal_score = goal_hint or "sales", 0
    for g, keywords in GOAL_KEYWORDS.items():
        score = sum(1 for k in keywords if k in text)
        if score > goal_score:
            goal_score, goal = score, g

    age_match = re.search(r"(\d{2})\s*[–\-to]+\s*(\d{2})", brief_text)
    age_min = max(13, min(int(age_match.group(1)) if age_match else 22, 60))
    age_max = max(age_min + 1, min(int(age_match.group(2)) if age_match else 35, 70))

    gender = "all"
    female_signals = ["women", "female", "her ", "she ", "girl", "ladies", "woman"]
    male_signals   = ["men", "male", "him ", "he ", "boy", "guys", "man "]
    f_count = sum(1 for w in female_signals if w in text)
    m_count = sum(1 for w in male_signals if w in text)
    if f_count > 0 and f_count >= m_count:
        gender = "female"
    elif m_count > 0 and m_count > f_count:
        gender = "male"

    geo = "India"
    for keyword, country in {
        "india": "India", "indian": "India",
        "usa": "USA", "united states": "USA", "america": "USA",
        "uk": "UK", "united kingdom": "UK",
        "australia": "Australia", "singapore": "Singapore",
        "global": "Global", "worldwide": "Global",
    }.items():
        if keyword in text:
            geo = country
            break

    tone, tone_score = "authentic", 0
    for t, keywords in TONE_KEYWORDS.items():
        score = sum(1 for k in keywords if k in text)
        if score > tone_score:
            tone_score, tone = score, t

    return {
        "category":          category,
        "target_audience":   {"age_min": age_min, "age_max": age_max, "gender": gender, "geo": geo},
        "budget":            _extract_budget(brief_text, budget),
        "goal":              goal,
        "tone":              tone,
        "objective_weights": GOAL_WEIGHTS.get(goal, GOAL_WEIGHTS["sales"]),
        "parsed_by":         "rule-based",
    }


def apply_parsed_brief(parsed: dict):
    import streamlit as st
    b = st.session_state.brief
    b["category"] = parsed["category"]
    b["goal"]     = parsed["goal"]
    b["budget"]   = parsed["budget"]
    b["tone"]     = parsed["tone"]
    b["weights"]  = parsed["objective_weights"]
    b["audience"]["age_min"] = parsed["target_audience"]["age_min"]
    b["audience"]["age_max"] = parsed["target_audience"]["age_max"]
    b["audience"]["gender"]  = parsed["target_audience"]["gender"]
    b["audience"]["geo"]     = parsed["target_audience"]["geo"]