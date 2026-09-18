"""
topic_links.py
==============
A curated map of study topics to trusted resources - explanation link,
YouTube tutorial search, and practice problems. All links point to
domains already on the StudyFocus allowlist, so recommendations never
send a student somewhere the proxy would then block.

This is intentionally simple (keyword match) rather than a full search
engine - for a student project, a small curated set of genuinely good
resources beats a large set of mediocre auto-searched ones.
"""

TOPIC_LINKS = {
    "photosynthesis": {
        "explanation": "https://www.khanacademy.org/science/biology/photosynthesis-in-plants",
        "youtube_search": "https://www.youtube.com/results?search_query=photosynthesis+explained+khan+academy",
        "practice": "https://www.khanacademy.org/science/biology/photosynthesis-in-plants/photosynthesis-review/e/photosynthesis",
    },
    "quadratic equations": {
        "explanation": "https://www.khanacademy.org/math/algebra/x2f8bb11595b61c86:quadratic-functions-equations",
        "youtube_search": "https://www.youtube.com/results?search_query=quadratic+equations+explained",
        "practice": "https://www.geeksforgeeks.org/quadratic-equation/",
    },
    "newtons laws": {
        "explanation": "https://www.khanacademy.org/science/physics/forces-newtons-laws",
        "youtube_search": "https://www.youtube.com/results?search_query=newtons+laws+of+motion+explained",
        "practice": "https://www.toppr.com/guides/physics/laws-of-motion/",
    },
    "binary search": {
        "explanation": "https://www.geeksforgeeks.org/binary-search/",
        "youtube_search": "https://www.youtube.com/results?search_query=binary+search+algorithm+explained",
        "practice": "https://leetcode.com/problems/binary-search/",
    },
    "recursion": {
        "explanation": "https://www.geeksforgeeks.org/recursion/",
        "youtube_search": "https://www.youtube.com/results?search_query=recursion+explained+for+beginners",
        "practice": "https://leetcode.com/tag/recursion/",
    },
    "cell structure": {
        "explanation": "https://www.khanacademy.org/science/biology/structure-of-a-cell",
        "youtube_search": "https://www.youtube.com/results?search_query=cell+structure+explained",
        "practice": "https://www.byjus.com/biology/cell-structure/",
    },
    "french revolution": {
        "explanation": "https://www.britannica.com/event/French-Revolution",
        "youtube_search": "https://www.youtube.com/results?search_query=french+revolution+explained",
        "practice": "https://www.ncert.nic.in/textbook.php",
    },
    "trigonometry": {
        "explanation": "https://www.khanacademy.org/math/trigonometry",
        "youtube_search": "https://www.youtube.com/results?search_query=trigonometry+basics+explained",
        "practice": "https://www.geeksforgeeks.org/trigonometric-functions/",
    },
    "linked list": {
        "explanation": "https://www.geeksforgeeks.org/data-structures/linked-list/",
        "youtube_search": "https://www.youtube.com/results?search_query=linked+list+data+structure+explained",
        "practice": "https://leetcode.com/tag/linked-list/",
    },
    "periodic table": {
        "explanation": "https://www.khanacademy.org/science/chemistry/periodic-table",
        "youtube_search": "https://www.youtube.com/results?search_query=periodic+table+explained",
        "practice": "https://www.byjus.com/chemistry/periodic-table/",
    },
}


def find_topic_links(question: str):
    """Very simple keyword matching against the question text.
    Returns a list of (topic, links_dict) for any topic mentioned."""
    q_lower = question.lower()
    matches = []
    for topic, links in TOPIC_LINKS.items():
        if topic in q_lower:
            matches.append((topic, links))
    return matches