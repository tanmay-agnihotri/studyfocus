"""
allowlist_config.py
====================
The editable "source of truth" for which domains are allowed, organized
by age profile. Each domain maps to an optional time limit in seconds
(None = unlimited). Add or remove a domain, or change a limit, by editing
the dicts below - no other code needs to change.
"""

ALWAYS_ALLOWED = {
    "wikipedia.org": None,
    "britannica.com": None,
    "dictionary.com": None,
    "google.com": None,
    "gstatic.com": None,
    "googleusercontent.com": None,
}

AGE_PROFILES = {
    "6-12": {
        "label": "Ages 6-12 (foundational)",
        "domains": {
            "ncert.nic.in": None,
            "diksha.gov.in": None,
            "khanacademy.org": None,
            "byjus.com": None,
            "duolingo.com": None,
            "nationalgeographic.com": None,
            "nasa.gov": None,
            "youtube.com": 3600,  # 1 hour/day cap for this age group
        },
    },
    "13-18": {
        "label": "Ages 13-18 (school / board exams)",
        "domains": {
            "vedantu.com": None,
            "unacademy.com": None,
            "physicswallah.live": None,
            "doubtnut.com": None,
            "toppr.com": None,
            "byjus.com": None,
            "khanacademy.org": None,
            "ncert.nic.in": None,
            "youtube.com": None,  # unlimited - used for lecture content at this age
        },
    },
    "18-25": {
        "label": "Ages 18-25 (college / competitive / coding)",
        "domains": {
            "geeksforgeeks.org": None,
            "w3schools.com": None,
            "stackoverflow.com": None,
            "coursera.org": None,
            "edx.org": None,
            "freecodecamp.org": None,
            "leetcode.com": None,
            "github.com": None,
            "khanacademy.org": None,
            "youtube.com": None,  # unlimited
        },
    },
}


def get_allowed_domains(age_profile: str) -> dict:
    """Returns {domain: limit_seconds_or_None} for a given age profile,
    combining the profile-specific list with the always-allowed list."""
    profile = AGE_PROFILES.get(age_profile, AGE_PROFILES["13-18"])
    combined = dict(ALWAYS_ALLOWED)
    combined.update(profile["domains"])
    return combined