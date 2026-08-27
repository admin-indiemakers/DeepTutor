"""
Topic & Concept Sanitizer for DeepTutor.
Ensures extracted key topics, headings, and quiz/flashcard concept suggestions
are high-yield academic concepts and free of table artifacts, citations, and boilerplate.
"""
import re
from typing import List, Optional, Set

# Structural academic paper boilerplate sections & meta-info (not concepts to study)
BOILERPLATE_HEADINGS: Set[str] = {
    "abstract", "introduction", "conclusion", "conclusions", "references", "reference",
    "bibliography", "acknowledgment", "acknowledgments", "acknowledgements",
    "table of contents", "contents", "index", "appendix", "appendices",
    "results and discussion", "discussion", "results", "materials and methods", "methodology",
    "methods", "overview", "background", "related work", "literature review",
    "author contributions", "conflict of interest", "competing interests",
    "data availability", "ethics statement", "supplementary material",
    "characteristics of publication outputs", "publication outputs",
    "keywords", "key words", "keywords plus", "table", "figure", "figures", "tables",
    "ieee", "springer", "elsevier", "wiley", "mdpi", "arxiv", "scopus", "web of science",
    "science core collection", "sci-expanded", "thomson reuters", "google scholar",
    "proceedings", "conference", "symposium", "department", "university", "faculty",
    "edition", "published", "copyright", "rights reserved", "editorial", "preface",
    "table 1", "table 2", "table 3", "figure 1", "figure 2", "figure 3", "fig 1", "fig 2",
    "main ideas", "key themes", "core concepts", "summary overview",
    "research paper", "paper", "author biography", "biography", "about the authors",
    "bibliometric analysis", "citation history", "citation histories",
    "citation histories of the most frequently cited articles",
    "web of science categories and journals", "categories and journals",
    "open research challenges and opportunities relative to global south regions",
    "open research challenges", "research challenges", "global south regions",
    "limitations and prospects", "classical machine learning limitations and prospects",
    "funding statement", "financial support", "disclaimer", "declaration", "peer review"
}

# Substrings that disqualify candidate topic strings immediately
META_SUBSTRINGS: Set[str] = {
    "bibliometric", "citation histor", "author bio", "biography", "web of science",
    "scopus", "publication output", "conflict of interest", "acknowledg", "research paper",
    "limitations and prospect", "global south", "peer review", "copyright"
}

# Noisy stop words / country / generic tokens
STOP_WORDS: Set[str] = {
    "tc", "tp", "cpp", "lr", "roc", "usa", "uk", "china", "india", "japan", "germany",
    "south africa", "north america", "europe", "asia", "global", "international",
    "author", "authors", "editor", "volume", "issue", "pages", "journal", "p", "pp", "vol",
    "no", "num", "et al", "etc", "e g", "i e", "via", "using", "based", "approach", "paper"
}


# Textbook question directives and boilerplate patterns to strip or reject
QUESTION_DIRECTIVES_PATTERNS = [
    r'^(?:give|providing|provide)\s+(?:reasons?|explanations?|details?|answers?)\s+(?:for\s+)?(?:the\s+following)?[:\s-]*',
    r'^(?:write|prepare)\s+(?:a\s+)?(?:short\s+)?(?:note|notes|summary|brief|essay)\s+(?:on|about)?[:\s-]*',
    r'^(?:explain|describe|discuss|elaborate|clarify|illustrate|state|define|mention|list|name|identify|examine|analyze)\s+(?:the\s+following)?[:\s-]*',
    r'^(?:what\s+is\s+meant\s+by|what\s+is|what\s+are|how\s+does|how\s+do|why\s+does|why\s+do|why\s+is|why\s+are|how\s+is|how\s+are)\s+(?:the\s+)?',
    r'^(?:fill\s+in\s+the\s+blanks?|match\s+the\s+following|choose\s+the\s+correct|tick\s+the\s+correct|true\s+or\s+false|multiple\s+choice)[:\s-]*',
    r'^(?:short\s+answer|long\s+answer|very\s+short\s+answer|essay\s+type|questions?\s+and\s+answers?|exercises?|activities|activity|project\s+work)[:\s-]*',
    r'^(?:answer\s+(?:the\s+following|in\s+brief|in\s+detail|the\s+questions?|each\s+question))[:\s-]*',
    r'^(?:read\s+the\s+(?:source|passage|extract|text)|look\s+at\s+the\s+(?:figure|picture|image|map))[:\s-]*',
]

EXERCISE_BOILERPLATE: Set[str] = {
    "give reasons for the following", "give reasons", "give explanations for the following",
    "give explanations", "give reasons for", "write a note on", "write a short note on",
    "write a note", "explain the following", "explain", "explained", "explaining",
    "what is meant by", "what is meant by the", "discuss the following", "discuss",
    "fill in the blanks", "match the following", "choose the correct answer", "choose the correct",
    "short answer questions", "long answer questions", "multiple choice questions",
    "exercises", "exercise", "question bank", "review questions", "sample questions",
    "practice questions", "chapter review", "let us assess", "extended activities",
    "points to remember", "summary", "activity", "activities", "questions", "question",
    "fill in", "match following", "answer the following", "give explanation for",
    "explain following", "write note on", "tick correct", "state true or false"
}


def is_valid_academic_topic(text: str) -> bool:
    """
    Returns True only if the candidate string is a meaningful, clean technical/academic concept.
    Rejects:
      - Question instructions ('Give reasons for the following', 'Write a note on:', 'Explain:')
      - Incomplete sentence fragments (ending in prepositions or ellipses)
      - Table column headers / code soup
      - Citation parentheticals & structural boilerplate
    """
    if not text or not isinstance(text, str):
        return False

    t = text.strip()
    # Length limits
    if len(t) < 4 or len(t) > 85:
        return False

    t_lower = t.lower()

    # 1. Exact or stripped match against boilerplate, meta substrings, or exercise headers
    if t_lower in BOILERPLATE_HEADINGS or t_lower in EXERCISE_BOILERPLATE:
        return False

    if any(sub in t_lower for sub in META_SUBSTRINGS):
        return False

    # Check against raw question stems without trailing punctuation
    clean_stem = re.sub(r'[:\.\?\!\-\s]+$', '', t_lower).strip()
    if clean_stem in EXERCISE_BOILERPLATE or clean_stem in BOILERPLATE_HEADINGS:
        return False

    # Strip section numbering prefix like '1.2 ', 'IV. ', 'Section 3: '
    stripped_prefix = re.sub(r'^(?:(?:section|chapter|part)\s+)?(?:(?:\d+(?:\.\d+)*)|[ivxlcdm]+)[.\)\s:-]+\s*', '', t_lower).strip()
    if stripped_prefix in BOILERPLATE_HEADINGS or stripped_prefix in EXERCISE_BOILERPLATE or any(sub in stripped_prefix for sub in META_SUBSTRINGS) or len(stripped_prefix) < 3:
        return False

    # 2. Reject incomplete sentence fragments & dangling prepositions (e.g. 'for the...', 'exported two-thirds of')
    if re.search(r'\b(?:of|the|a|an|in|on|at|by|to|for|from|with|and|or|is|are|was|were|that|which)\s*$', t_lower):
        return False
    if t.endswith(('-', '...', ':', ',')):
        return False

    # 3. Check for URLs, DOIs, file extensions, ISBNs
    if re.search(r'(?:doi:|https?://|https?:|www\.|\.pdf|\.docx?|\.txt|\.html?|isbn|issn)', t_lower):
        return False

    # 4. Check for citation artifacts, year brackets, parenthetical dumps
    if re.search(r'et\s+al\.?', t_lower):
        return False
    if re.match(r'^\(?\s*[A-Za-z]{1,4}\d{4}\s*\)?(?:\s*\(?\s*[A-Za-z]{1,4}\d{4}\s*\)?)*$', t):
        return False
    if re.search(r'\(\s*\d{4}\s*\)', t) or re.search(r'\[\s*\d+\s*\]', t):
        return False
    if t.startswith("(") and t.endswith(")"):
        return False

    # 5. Check alphabetic letter ratio (must be >= 70% letters/spaces, not symbol/digit soup)
    letter_space_count = sum(1 for c in t if c.isalpha() or c.isspace() or c in "-'")
    if letter_space_count / max(len(t), 1) < 0.70:
        return False

    # 6. Check word composition
    words = re.findall(r'[a-zA-Z0-9]+', t)
    if not words or len(words) > 11:
        return False

    # Check for repeated word/code tokens
    lower_words = [w.lower() for w in words]
    if len(lower_words) != len(set(lower_words)) and len(lower_words) >= 4:
        return False

    # Check for alphanumeric code-words (e.g. Cpp202, Ipir202)
    alphanumeric_codes = sum(
        1 for w in words
        if len(w) >= 3 and any(c.isdigit() for c in w) and any(c.isalpha() for c in w)
    )
    if alphanumeric_codes >= 2:
        return False

    # Check for all-numbers
    if all(w.isdigit() for w in words):
        return False

    # 7. Must not be table / figure caption headers
    if re.match(r'^(?:table|figure|fig|tab|eq|equation|page|p|box)\b[.\s:-]*\d*', t_lower):
        return False

    # 8. Reject full narrative sentences with past-tense transitive verbs and fact clauses
    if len(words) >= 4 and re.search(r'\b(?:exported|imported|produced|increased|decreased|established|signed|died|born|located|consisted|belonged|dominated|divided|ruled|fought|won|lost)\b', t_lower):
        return False

    # 9. Check if topic is just a single stop-word
    if len(words) == 1 and lower_words[0] in STOP_WORDS:
        return False

    return True


def clean_and_format_topic(topic: str) -> Optional[str]:
    """
    Sanitizes, strips question boilerplate, and formats a candidate topic string.
    Returns cleaned, Title Cased topic string or None if invalid.
    """
    if not topic or not isinstance(topic, str):
        return None

    t = topic.strip()

    # Strip question directives (e.g., 'Write a note on: Treaty of Vienna' -> 'Treaty of Vienna')
    for pat in QUESTION_DIRECTIVES_PATTERNS:
        t = re.sub(pat, '', t, flags=re.IGNORECASE).strip()

    # Strip question marks and trailing punctuation
    t = re.sub(r'[\?:]+$', '', t).strip()

    if not is_valid_academic_topic(t):
        return None

    # Strip leading numbers, bullets, colons
    t = re.sub(r'^(?:(?:section|chapter|part)\s+)?(?:(?:\d+(?:\.\d+)*)|[ivxlcdm]+)[.\)\s:-]+\s*', '', t, flags=re.IGNORECASE)
    t = re.sub(r'^[•\-\*#\s:]+', '', t)
    t = t.strip()

    # Normalize whitespace
    t = re.sub(r'\s+', ' ', t)

    if not is_valid_academic_topic(t):
        return None

    # Standardize casing (keep well-known acronyms all-caps, title case everything else)
    KNOWN_ACRONYMS = {"SVM", "KNN", "ML", "AI", "CNN", "RNN", "LSTM", "BERT", "LLM", "NLP", "PCA", "RAG", "DNA", "RNA", "USA", "UK", "USSR", "UN", "NATO", "EU", "OPEC", "WTO", "IMF"}
    words = t.split()
    formatted_words = []
    for w in words:
        w_upper = w.upper()
        if w_upper in KNOWN_ACRONYMS:
            formatted_words.append(w_upper)
        elif w.lower() in ("of", "and", "in", "on", "the", "for", "to", "a", "an", "at", "by", "with", "from") and formatted_words:
            formatted_words.append(w.lower())
        else:
            formatted_words.append(w.capitalize())

    if formatted_words:
        formatted_words[0] = formatted_words[0].capitalize()

    t = " ".join(formatted_words)
    return t


def deduplicate_and_rank_topics(topics: List[str], max_topics: int = 15) -> List[str]:
    """
    Filters, sanitizes, deduplicates, and ranks topics.
    Eliminates redundant substring overlaps (e.g. keeping longer informative concept).
    """
    cleaned_topics: List[str] = []
    seen_lower: Set[str] = set()

    for candidate in topics:
        clean = clean_and_format_topic(candidate)
        if not clean:
            continue
        c_lower = clean.lower()
        if c_lower in seen_lower:
            continue
        seen_lower.add(c_lower)
        cleaned_topics.append(clean)

    # Substring deduplication: if 'Support Vector Machines' exists, omit redundant 'Vector Machines'
    final_topics: List[str] = []
    for i, t in enumerate(cleaned_topics):
        t_lower = t.lower()
        # Check if t is an exact substring of a longer topic in the list
        is_sub = False
        for other in cleaned_topics:
            other_lower = other.lower()
            if t_lower != other_lower and t_lower in other_lower and len(other_lower) - len(t_lower) <= 25:
                # Substring overlap — keep the more specific/longer one
                is_sub = True
                break
        if not is_sub:
            final_topics.append(t)

    return final_topics[:max_topics]
