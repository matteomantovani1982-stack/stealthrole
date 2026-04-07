"""
app/services/profile/strength_scorer.py

Pure heuristic profile strength scoring. No LLM calls.

Scoring breakdown (100 points max):
  - Headline:     10 pts
  - Context:      10 pts
  - Experiences:  50 pts (count + completeness)
  - Preferences:  15 pts (roles, regions, sectors)
  - CV uploaded:  15 pts
"""


def score_profile(profile_dict: dict | None, has_cv: bool = False) -> dict:
    """
    Score a candidate profile and return breakdown + next action.

    Args:
        profile_dict: from CandidateProfile.to_prompt_dict() or None
        has_cv: whether the user has uploaded at least one CV

    Returns:
        {score, max, breakdown[], next_action}
    """
    if not profile_dict:
        return {
            "score": 0 + (15 if has_cv else 0),
            "max": 100,
            "breakdown": [
                {"category": "headline", "score": 0, "max": 10},
                {"category": "context", "score": 0, "max": 10},
                {"category": "experiences", "score": 0, "max": 50},
                {"category": "preferences", "score": 0, "max": 15},
                {"category": "cv_uploaded", "score": 15 if has_cv else 0, "max": 15},
            ],
            "next_action": "Create your candidate profile to unlock better AI recommendations.",
        }

    headline_score = 0
    context_score = 0
    experience_score = 0
    preferences_score = 0
    cv_score = 15 if has_cv else 0

    # Headline (10 pts)
    headline = profile_dict.get("headline", "")
    if headline:
        headline_score = 10 if len(headline) >= 20 else 5

    # Global context (10 pts)
    context = profile_dict.get("global_context", "")
    if context:
        context_score = 10 if len(context) >= 50 else 5

    # Experiences (50 pts)
    experiences = profile_dict.get("experiences", [])
    if experiences:
        # Count: up to 20 pts for having 3+ experiences
        count_pts = min(20, len(experiences) * 7)

        # Completeness: up to 30 pts
        completeness_total = 0
        for exp in experiences[:5]:  # Cap at 5 for scoring
            fields_present = sum(1 for k in ["context", "contribution", "outcomes", "methods", "hidden"]
                                 if exp.get(k))
            completeness_total += fields_present

        max_completeness = min(len(experiences), 5) * 5
        completeness_ratio = completeness_total / max_completeness if max_completeness > 0 else 0
        completeness_pts = round(completeness_ratio * 30)

        experience_score = min(50, count_pts + completeness_pts)

    # Preferences (15 pts)
    # Check if global_context contains __preferences or if preferences dict exists
    import json
    prefs = {}
    raw_context = profile_dict.get("global_context", "")
    if raw_context:
        try:
            ctx = json.loads(raw_context)
            prefs = ctx.get("__preferences", {})
        except (json.JSONDecodeError, TypeError):
            pass

    if prefs:
        has_roles = bool(prefs.get("roles"))
        has_regions = bool(prefs.get("regions"))
        has_sectors = bool(prefs.get("sectors"))
        preferences_score = sum([
            5 if has_roles else 0,
            5 if has_regions else 0,
            5 if has_sectors else 0,
        ])

    total = headline_score + context_score + experience_score + preferences_score + cv_score

    # Determine next action
    next_action = _get_next_action(
        headline_score, context_score, experience_score,
        preferences_score, cv_score, experiences,
    )

    return {
        "score": total,
        "max": 100,
        "breakdown": [
            {"category": "headline", "score": headline_score, "max": 10},
            {"category": "context", "score": context_score, "max": 10},
            {"category": "experiences", "score": experience_score, "max": 50},
            {"category": "preferences", "score": preferences_score, "max": 15},
            {"category": "cv_uploaded", "score": cv_score, "max": 15},
        ],
        "next_action": next_action,
    }


def _get_next_action(headline, context, experience, preferences, cv, experiences_list) -> str:
    if cv == 0:
        return "Upload your CV to get started."
    if headline == 0:
        return "Add a headline to your profile — describe yourself in one line."
    if context == 0:
        return "Add career context — your goals, constraints, and what you're looking for."
    if not experiences_list:
        return "Add your work experiences with detailed context for each role."
    if experience < 30:
        incomplete = [e for e in experiences_list if sum(1 for k in ["context", "contribution", "outcomes"] if e.get(k)) < 3]
        if incomplete:
            return f"Complete the details for your role at {incomplete[0].get('company', 'your company')}."
    if preferences == 0:
        return "Set your job search preferences — target roles, regions, and sectors."
    if experience < 50:
        return "Add more work experiences to strengthen your profile."
    return "Your profile is strong! Keep it updated as your goals evolve."
