"""
Content Relevance Gate — 4-Stage Cascade Filter
================================================

Intercepts every document upload BEFORE it enters the RAG indexing pipeline.
Cheap-first ordering ensures only genuinely ambiguous documents pay LLM cost.

Architecture:
┌──────────────────────────────────────────────────────────────────┐
│               RELEVANCE GATE (4-stage cascade)                   │
│                                                                  │
│  [A] Content Quality Checks ──FAIL──► REJECT                     │
│       • Empty / very short                                       │
│       • Spam / noise (STEM-aware symbol filtering)               │
│       • Unsupported content (binary blobs, code dumps)           │
│       • Adult / unsafe content (context-aware blocklist)         │
│       • Non-study content (receipts, forms, menus)               │
│          │ PASS                                                  │
│  [B] Heuristic Filter ──FAIL──► REJECT (garbled/OCR junk)        │
│          │ PASS                                                  │
│  [C] Embedding Similarity ──FAIL──► REJECT (off-topic)           │
│          │ PASS                                                  │
│  [D] LLM Classifier ──FAIL──► REJECT (ambiguous cases)           │
│          │ PASS                                                  │
└──────────┼───────────────────────────────────────────────────────┘
           │
           ▼
     RAG Ingestion Pipeline

Adult Content Design Principle
───────────────────────────────
Biology textbooks legitimately contain terms like "reproductive system",
"sexual reproduction", "gametes", "male/female anatomy", "genitalia" in a
purely academic context. A naive keyword blocklist would false-positive on
every biology or human anatomy document.

Solution: two-pass context-aware check.
  1. Detect academic biology/medical context markers first.
  2. If strong academic context is present → use a *strict* blocklist that
     ONLY matches clearly pornographic/commercial-sex phrases no textbook
     would ever contain (e.g. "xxx", "onlyfans", "camgirl").
  3. If no academic context → use a broader blocklist that also catches
     anatomical terms used in non-educational settings.

GateResult.rejection_code values:
  - "empty_document"     Document has no extractable text
  - "too_short"          Text is below minimum length threshold
  - "spam_noise"         High noise density detected (excluding math/science symbols)
  - "adult_content"      Explicit or unsafe keyword patterns detected
  - "non_study_content"  Structural patterns match non-academic content
  - "unsupported_format" Binary blob, source-code dump, or non-prose content
  - "garbled_text"       OCR/encoding artifacts make text unintelligible
  - "off_topic"          Embedding similarity below academic threshold
  - "llm_rejected"       LLM classifier determined non-academic content
  - ""                   Document passed
"""
from __future__ import annotations

import asyncio
import logging
import math
import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Multi-point Document Sampling Helper
# ══════════════════════════════════════════════════════════════════════════════
def _extract_multi_point_sample(
    text: str,
    total_target_chars: int = 2100,
    num_chunks: int = 3,
) -> str:
    """
    Extract stratified non-contiguous samples across the document
    (head, middle, and later section) and combine them into a single excerpt.

    This avoids misjudging documents that open with cover pages, copyright notices,
    tables of contents, or prefaces before the real academic content begins.
    """
    stripped = text.strip()
    n = len(stripped)
    if n <= total_target_chars:
        return stripped

    chunk_size = max(100, total_target_chars // num_chunks)

    # 1. Head chunk (beginning of document)
    head = stripped[:chunk_size].strip()

    # 2. Middle chunk (centered around ~50% point)
    mid_start = max(0, (n // 2) - (chunk_size // 2))
    mid = stripped[mid_start: mid_start + chunk_size].strip()

    # 3. Later chunk (centered around ~75-80% point)
    later_start = max(0, int(n * 0.75) - (chunk_size // 2))
    later_start = min(later_start, max(0, n - chunk_size))
    later = stripped[later_start: later_start + chunk_size].strip()

    return f"{head}\n\n[... middle section ...]\n\n{mid}\n\n[... later section ...]\n\n{later}"


# ══════════════════════════════════════════════════════════════════════════════
# STEM & Scientific Character Whitelist for Noise Check
# ══════════════════════════════════════════════════════════════════════════════
# Explicit whitelist of common STEM, LaTeX/ASCII-math, chemical, and punctuation characters
_LEGITIMATE_STEM_CHARS = frozenset(
    # Digits
    "0123456789"
    # Basic math operators and relations
    "+-*/=<>±∓×÷≤≥≠≈≡¬√∛∜∝∞^~"
    # Calculus, algebra, set theory, vectors
    "∫∬∭∮∑∏∂∇∆∈∉⊂⊃⊆⊇∪∩∧∨⊕⊗⊥∠"
    # Standard and curly brackets / delimiters
    "()[]{}⟨⟩«»|"
    # Standard and typographic punctuation
    ".,:;!?'\"`‘’“”_\\/@#$&"
    # Units, degrees, percentages, currency, science
    "°%‰$€£¥₹℃℉Åμℏπ"
    # Arrows
    "→←↔⇒⇐⇔↦"
    # Superscripts and subscripts
    "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎"
)


def _is_legitimate_content_char(c: str) -> bool:
    """
    Check if a character is legitimate text, number, STEM symbol, or standard punctuation.
    Returns False for non-linguistic noise, control characters, and encoding artifacts.
    """
    if c.isalnum():
        return True
    if c in _LEGITIMATE_STEM_CHARS:
        return True
    cat = unicodedata.category(c)
    # Math symbols (Sm), currency (Sc), punctuation (P*) are legitimate content characters
    if cat in ("Sm", "Sc", "Po", "Pd", "Ps", "Pe", "Pi", "Pf", "Pc"):
        return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
# Result Dataclass
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class GateResult:
    """
    Result of the content relevance gate check.
    `passed=False` → `rejection_code` and `reason` explain why.
    """
    passed: bool
    stage_reached: str          # "quality" | "heuristic" | "embedding" | "llm"
    rejection_code: str         # machine-readable code for the UI
    reason: str                 # human-readable message shown to student
    confidence: float           # 0.0–1.0
    subject_domain: str = ""    # detected academic domain (e.g. "biology")
    details: Dict = field(default_factory=dict)

    @classmethod
    def passed_result(
        cls,
        subject_domain: str,
        stage: str,
        confidence: float,
        details: Dict = None,
    ) -> "GateResult":
        return cls(
            passed=True,
            stage_reached=stage,
            rejection_code="",
            reason="",
            confidence=confidence,
            subject_domain=subject_domain,
            details=details or {},
        )

    @classmethod
    def rejected(
        cls,
        stage: str,
        rejection_code: str,
        reason: str,
        confidence: float = 1.0,
        details: Dict = None,
    ) -> "GateResult":
        return cls(
            passed=False,
            stage_reached=stage,
            rejection_code=rejection_code,
            reason=reason,
            confidence=confidence,
            subject_domain="",
            details=details or {},
        )


# ══════════════════════════════════════════════════════════════════════════════
# Stage A: Content Quality Checks
# Cost: zero LLM / embedding, pure regex + heuristics, <2ms
# ══════════════════════════════════════════════════════════════════════════════

# ── Adult content: context-aware two-pass blocklist ───────────────────────────
#
# RATIONALE:
#   Biology, human anatomy, health education, and medical textbooks contain
#   legitimate scientific terms (e.g. "reproductive system", "genitalia",
#   "sexual reproduction", "male/female gonads") that must NOT be flagged.
#   We solve this with a two-tier system:
#
#   Tier 1 — ALWAYS_BLOCKED (used regardless of academic context):
#     Contains only phrases that are unambiguously commercial-sex / pornographic
#     and would never appear in a school or university textbook.
#
#   Tier 2 — NON_ACADEMIC_BLOCKED (only used when NO academic biology/medical
#     markers are detected):
#     Contains broader terms that could appear in adult content but also in
#     legitimate anatomy or health education material.

_ACADEMIC_BIOLOGY_MARKERS = re.compile(
    r'\b('
    r'cell\s+division|meiosis|mitosis|chromosome|gamete|zygote|embryo|'
    r'reproductive\s+system|endocrine\s+system|nervous\s+system|'
    r'photosynthesis|cellular\s+respiration|dna\s+replication|'
    r'taxonomy|kingdom|phylum|genus|species|ecosystem|natural\s+selection|'
    r'anatomy|physiology|histology|pathology|clinical|medical|'
    r'sexual\s+reproduction|asexual\s+reproduction|fertilisation|fertilization|'
    r'placenta|uterus|ovary|testis|hormone|puberty\s+education|'
    r'human\s+body|organ\s+system|textbook|chapter|syllabus|curriculum'
    r')\b',
    re.IGNORECASE,
)

# Tier 1: Always blocked — clearly pornographic / commercial-sex phrases.
_ADULT_ALWAYS_BLOCKED: List[re.Pattern] = [
    re.compile(
        r'\b('
        r'xxx|pornograph|porn\s+video|porn\s+site|adult\s+film|adult\s+website|'
        r'onlyfans|camgirl|cam\s+girl|webcam\s+model|escort\s+service|'
        r'sex\s+worker\s+service|nude\s+photo|explicit\s+photo|'
        r'sexual\s+services?|massage\s+parlou?r'
        r')\b',
        re.IGNORECASE,
    ),
]

# Tier 2: Only applied when document lacks academic biology/medical markers.
_ADULT_NON_ACADEMIC_BLOCKED: List[re.Pattern] = [
    re.compile(
        r'\b('
        r'erotic|erotica|fetish|bdsm|masturbat|orgasm|'
        r'explicit\s+sex|graphic\s+sex|nude\s+model'
        r')\b',
        re.IGNORECASE,
    ),
]

_MIN_CHARS: int = getattr(settings, "RELEVANCE_GATE_MIN_CHARS", 200)
_MAX_SYMBOL_RATIO: float = getattr(settings, "RELEVANCE_GATE_MAX_SYMBOL_RATIO", 0.40)


def _has_academic_biology_context(sample: str) -> bool:
    """Return True if document sample contains academic biology/medical markers."""
    return bool(_ACADEMIC_BIOLOGY_MARKERS.search(sample))


def _check_adult_content(text: str) -> Optional[Tuple[str, str]]:
    """
    Context-aware adult content check.

    Returns (matched_phrase, tier) if adult content detected,
    or None if the document is clean.
    """
    scan_sample = text[:5000]
    context_sample = text[:3000]

    # Pass 1: Academic context detection
    has_bio_context = _has_academic_biology_context(context_sample)

    if has_bio_context:
        logger.debug("ContentRelevanceGate adult check: Academic biology/medical context detected. Applying Tier-1 only.")

    # Pass 2: Apply appropriate blocklist tier(s)
    for pattern in _ADULT_ALWAYS_BLOCKED:
        m = pattern.search(scan_sample)
        if m:
            return m.group(0)[:40], "tier1_always"

    if not has_bio_context:
        for pattern in _ADULT_NON_ACADEMIC_BLOCKED:
            m = pattern.search(scan_sample)
            if m:
                return m.group(0)[:40], "tier2_non_academic"

    return None


# ── Non-study structural patterns ────────────────────────────────────────────
_NON_STUDY_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r'\b(total\s+amount|subtotal|tax\s+\d|invoice\s+no\.?|receipt\s+no\.?|order\s+id)\b', re.I), "invoice_receipt"),
    (re.compile(r'\b(starters|main\s+course|desserts|beverages)\b.*\b(\$|€|£|₹)\s*\d', re.I | re.S), "restaurant_menu"),
    (re.compile(r'\b(check[\s-]?in|check[\s-]?out|booking\s+reference|reservation\s+id|confirmation\s+no)\b', re.I), "booking_form"),
]

_CURRENCY_ITEM_PATTERN = re.compile(
    r'(?:(?:\$|€|£|₹|Rs\.?)\s*\d[\d,.]*\s+\w+(?:\s+\w+){0,4}\n){3,}', re.M,
)

# ── Unsupported content ──────────────────────────────────────────────────────
_UNSUPPORTED_PATTERNS: List[re.Pattern] = [
    re.compile(r'(?:[a-f0-9]{32,})', re.I),        # long hex strings (binary dump)
    re.compile(r'(\w+\([\w,\s"\']+\);\s*){10,}'),  # minified JS function calls
    re.compile(r'(\\x[0-9a-f]{2}){20,}', re.I),    # hex escape sequences
]


def _stage_a_content_quality(text: str) -> Optional[GateResult]:
    """
    Stage A — Content Quality Checks (5 sub-checks, <2ms total).
    Returns GateResult(passed=False) on first failure, or None to proceed.
    """
    stripped = text.strip()

    # A1. Empty / very short
    if not stripped:
        return GateResult.rejected(
            stage="quality",
            rejection_code="empty_document",
            reason=(
                "This document appears to be empty or contains no extractable text. "
                "Please ensure your PDF has selectable text and is not a scanned "
                "image-only file."
            ),
        )

    if len(stripped) < _MIN_CHARS:
        return GateResult.rejected(
            stage="quality",
            rejection_code="too_short",
            reason=(
                f"This document is too short ({len(stripped)} characters) to be indexed "
                "as study material. Please upload a complete document with at least "
                "a few paragraphs of content."
            ),
            details={"char_count": len(stripped), "min_required": _MIN_CHARS},
        )

    # A2. Spam / noise (STEM-aware symbol and noise density + repetition)
    # Excludes digits, mathematical symbols, chemical notation, subscripts, and common punctuation
    # from counting as "noise" so STEM study material is never falsely rejected.
    total_non_whitespace = sum(1 for c in stripped if not c.isspace())
    noise_chars = sum(1 for c in stripped if not c.isspace() and not _is_legitimate_content_char(c))
    noise_ratio = noise_chars / max(total_non_whitespace, 1)

    words = stripped.lower().split()
    repetition_ratio = 0.0
    if words and len(set(words)) < 200:
        most_common = max(words.count(w) for w in set(words))
        repetition_ratio = most_common / len(words)

    if noise_ratio > _MAX_SYMBOL_RATIO and total_non_whitespace > 100:
        return GateResult.rejected(
            stage="quality",
            rejection_code="spam_noise",
            reason=(
                "This document contains an unusually high proportion of non-linguistic noise "
                "or corrupted symbols and cannot be processed. This typically happens with "
                "corrupted, password-protected, or encoding-damaged files."
            ),
            details={"noise_ratio": round(noise_ratio, 3), "threshold": _MAX_SYMBOL_RATIO},
        )

    if repetition_ratio > 0.6 and len(words) > 50:
        return GateResult.rejected(
            stage="quality",
            rejection_code="spam_noise",
            reason=(
                "This document appears to contain highly repetitive or auto-generated "
                "text and does not qualify as academic study material."
            ),
            details={"repetition_ratio": round(repetition_ratio, 3)},
        )

    # A3. Adult / unsafe content — context-aware (biology-safe)
    adult_enabled = getattr(settings, "RELEVANCE_GATE_ADULT_BLOCKLIST", True)
    if adult_enabled:
        adult_match = _check_adult_content(stripped)
        if adult_match:
            matched_phrase, tier = adult_match
            return GateResult.rejected(
                stage="quality",
                rejection_code="adult_content",
                reason=(
                    "This document contains content that is not appropriate for an "
                    "academic tutoring platform. Only educational study materials are accepted."
                ),
                details={"matched_pattern": matched_phrase, "tier": tier},
            )

    # A4. Non-study content (receipts, menus, invoices, booking forms)
    sample = stripped[:3000]
    for pattern, content_type in _NON_STUDY_PATTERNS:
        if pattern.search(sample):
            return GateResult.rejected(
                stage="quality",
                rejection_code="non_study_content",
                reason=(
                    f"This document appears to be a {content_type.replace('_', ' ')} "
                    "rather than study material. Please upload textbooks, lecture notes, "
                    "assignment sheets, or other academic documents."
                ),
                details={"detected_type": content_type},
            )

    if _CURRENCY_ITEM_PATTERN.search(stripped[:2000]):
        return GateResult.rejected(
            stage="quality",
            rejection_code="non_study_content",
            reason=(
                "This document appears to be a price list, receipt, or menu. "
                "Please upload academic documents such as textbooks or lecture notes."
            ),
        )

    # A5. Unsupported content (binary / minified code)
    for pattern in _UNSUPPORTED_PATTERNS:
        if pattern.search(stripped[:2000]):
            return GateResult.rejected(
                stage="quality",
                rejection_code="unsupported_format",
                reason=(
                    "This document appears to contain binary data, minified code, or "
                    "other non-prose content that cannot be indexed as study material."
                ),
            )

    return None  # All Stage A checks passed


# ══════════════════════════════════════════════════════════════════════════════
# Stage B: Heuristic Filter
# Cost: zero LLM / embedding, linguistic heuristics, <1ms
# ══════════════════════════════════════════════════════════════════════════════

_COMMON_WORDS = frozenset([
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "and", "or", "but",
    "if", "because", "as", "until", "while", "since", "of", "at", "by",
    "for", "with", "about", "between", "into", "through", "before", "after",
    "to", "from", "in", "on", "this", "that", "these", "those", "it",
    "its", "their", "they", "we", "our", "you", "your", "he", "she",
    "his", "her", "which", "who", "what", "how", "when", "where", "why",
])

_LOREM_IPSUM_PATTERN = re.compile(r'\blorem\s+ipsum\b', re.I)
_OCR_JUNK_PATTERN = re.compile(
    r'(?:[^\w\s]{4,})|'        # 4+ consecutive unclassified symbols
    r'(?:\b\w{1}\s+){8,}|'    # 8+ single-letter tokens in a row
    r'(?:[A-Z]{18,})',         # very long all-caps runs
)


def _stage_b_heuristic_filter(text: str) -> Optional[GateResult]:
    """
    Stage B — Heuristic linguistic filter. Returns None to proceed to Stage C.
    """
    # Sample multi-point to evaluate whole document
    sample = _extract_multi_point_sample(text, total_target_chars=3000, num_chunks=3)
    words = re.findall(r'\b[a-zA-Z]{2,}\b', sample.lower())
    total_words = len(words)

    if total_words < 20:
        return GateResult.rejected(
            stage="heuristic",
            rejection_code="garbled_text",
            reason=(
                "This document contains too few recognizable words to be indexed. "
                "It may be a scanned image, corrupted file, or unsupported format."
            ),
            details={"real_word_count": total_words},
        )

    real_words = sum(1 for w in words if w in _COMMON_WORDS or len(w) >= 4)
    real_word_ratio = real_words / max(total_words, 1)

    if real_word_ratio < 0.25:
        return GateResult.rejected(
            stage="heuristic",
            rejection_code="garbled_text",
            reason=(
                "This document's text appears garbled or corrupted — possibly a scanned "
                "image-based PDF, a password-protected file, or a document with encoding issues."
            ),
            details={"real_word_ratio": round(real_word_ratio, 3)},
        )

    if _LOREM_IPSUM_PATTERN.search(sample):
        return GateResult.rejected(
            stage="heuristic",
            rejection_code="spam_noise",
            reason=(
                "This document contains placeholder 'lorem ipsum' filler text "
                "and is not valid study material."
            ),
        )

    junk_matches = _OCR_JUNK_PATTERN.findall(sample)
    if len(junk_matches) > 15:
        return GateResult.rejected(
            stage="heuristic",
            rejection_code="garbled_text",
            reason=(
                "This document contains a high density of OCR artifacts or encoding noise. "
                "Please try re-scanning at a higher resolution or uploading a cleaner version."
            ),
            details={"junk_match_count": len(junk_matches)},
        )

    return None


# ══════════════════════════════════════════════════════════════════════════════
# Stage C: Embedding Similarity vs Academic Anchor Corpus
# Cost: 1 embedding call (~50-150ms), NO LLM
# ══════════════════════════════════════════════════════════════════════════════

_ACADEMIC_ANCHORS: List[str] = [
    # Mathematics
    "mathematical proof theorem calculus algebra equations derivatives integrals",
    "linear algebra matrices eigenvalues probability statistics distributions",
    "geometry trigonometry functions polynomials number theory combinatorics",
    # Physics
    "physics mechanics kinematics dynamics Newton laws force velocity acceleration",
    "thermodynamics heat entropy quantum mechanics wave optics electromagnetism",
    "relativity nuclear physics atomic structure periodic table elements",
    # Chemistry
    "chemistry chemical reactions bonding molecular structure organic compounds",
    "stoichiometry acids bases pH titration electrochemistry thermochemistry",
    "biochemistry polymers coordination compounds reaction mechanisms",
    # Biology (intentionally includes anatomical/reproductive terms — legitimate academic content)
    "biology cell structure DNA genetics evolution natural selection taxonomy",
    "human anatomy physiology nervous system immune system photosynthesis reproduction",
    "ecology ecosystem biodiversity microbiology virology genetics meiosis mitosis",
    # Computer Science
    "computer science algorithms data structures programming software engineering",
    "machine learning neural networks artificial intelligence deep learning",
    "operating systems networking databases compiler design complexity theory",
    # History & Social Sciences
    "history civilization world war colonialism revolution political science",
    "economics GDP inflation monetary policy fiscal microeconomics macroeconomics",
    "geography climate environment geology plate tectonics",
    # Language & Literature
    "literature prose poetry grammar syntax semantics linguistics phonology",
    "reading comprehension writing essay composition vocabulary",
    # General Academic
    "lecture notes study material textbook chapter syllabus curriculum assignment",
    "research paper abstract introduction methodology results conclusion bibliography",
    "examination past paper model answer marking scheme grade assessment",
]

_EMBED_THRESHOLD: float = getattr(settings, "RELEVANCE_GATE_EMBED_THRESHOLD", 0.35)
_AMBIGUOUS_BAND: float = getattr(settings, "RELEVANCE_GATE_AMBIGUOUS_BAND", 0.10)

_anchor_embeddings_cache: Optional[List[List[float]]] = None
_anchor_cache_lock: Optional[asyncio.Lock] = None
_anchor_last_failed_at: float = 0.0
_ANCHOR_RETRY_COOLDOWN_SECONDS: float = 30.0

_DOMAIN_LABELS = [
    "mathematics", "mathematics", "mathematics",
    "physics", "physics", "physics",
    "chemistry", "chemistry", "chemistry",
    "biology", "biology", "biology",
    "computer_science", "computer_science", "computer_science",
    "social_sciences", "social_sciences", "social_sciences",
    "language_arts", "language_arts",
    "general_academic", "general_academic", "general_academic",
]


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def _get_anchor_embeddings() -> Optional[List[List[float]]]:
    """
    Lazily embed all anchor phrases and cache them for the process lifetime.
    If the embedding service fails, does NOT permanently cache an empty list,
    allowing automatic retry after a short backoff cooldown.
    """
    global _anchor_embeddings_cache, _anchor_cache_lock, _anchor_last_failed_at

    if _anchor_cache_lock is None:
        _anchor_cache_lock = asyncio.Lock()

    async with _anchor_cache_lock:
        if _anchor_embeddings_cache is not None and len(_anchor_embeddings_cache) > 0:
            return _anchor_embeddings_cache

        now = time.monotonic()
        # If a failure occurred recently, observe cooldown before retrying
        if now - _anchor_last_failed_at < _ANCHOR_RETRY_COOLDOWN_SECONDS:
            logger.warning(
                "ContentRelevanceGate Stage C: Running in degraded/fail-open mode "
                "(anchor embeddings unavailable; retry cooldown active, %.1fs remaining).",
                _ANCHOR_RETRY_COOLDOWN_SECONDS - (now - _anchor_last_failed_at),
            )
            return None

        try:
            from app.rag.pipeline.embedder import embedding_pipeline
            logger.info("ContentRelevanceGate: Embedding %d academic anchors...", len(_ACADEMIC_ANCHORS))
            embeddings = await embedding_pipeline.embed_batch(_ACADEMIC_ANCHORS)
            if embeddings and len(embeddings) == len(_ACADEMIC_ANCHORS):
                _anchor_embeddings_cache = embeddings
                logger.info("ContentRelevanceGate: Anchor embeddings cached successfully (%d anchors).", len(embeddings))
                return _anchor_embeddings_cache
            else:
                logger.warning("ContentRelevanceGate: Anchor embedding returned empty/incomplete list. Retrying after cooldown.")
                _anchor_last_failed_at = now
                _anchor_embeddings_cache = None
                return None
        except Exception as exc:
            _anchor_last_failed_at = now
            _anchor_embeddings_cache = None  # Do NOT cache empty list permanently!
            logger.warning(
                "ContentRelevanceGate: Anchor embedding failed with error: %s. "
                "Stage C will run in degraded/fail-open mode for the next %.0fs.",
                exc,
                _ANCHOR_RETRY_COOLDOWN_SECONDS,
                exc_info=True,
            )
            return None


async def _stage_c_embedding_similarity(
    text: str,
    topic_id: str = "",
) -> Tuple[Optional[GateResult], float, str]:
    """
    Stage C — Embedding similarity against academic anchor corpus.
    Uses multi-point stratified sampling (head, middle, later section) across the document.
    Returns (rejection_or_None, best_score, matched_domain).
    """
    try:
        from app.rag.pipeline.embedder import embedding_pipeline

        # Sample across multiple points in the document to prevent misjudging cover pages/prefaces
        sample = _extract_multi_point_sample(text, total_target_chars=2100, num_chunks=3)
        doc_embedding = await embedding_pipeline.embed(sample)
        anchor_embeddings = await _get_anchor_embeddings()

        if not anchor_embeddings:
            logger.warning(
                "ContentRelevanceGate Stage C: Running in degraded/fail-open mode "
                "(anchor embeddings unavailable). Skipping similarity check for topic=%s.",
                topic_id,
            )
            return None, 0.5, "unknown"

        scores = [_cosine_similarity(doc_embedding, anc) for anc in anchor_embeddings]
        best_score = max(scores)
        best_idx = scores.index(best_score)
        matched_domain = _DOMAIN_LABELS[best_idx] if best_idx < len(_DOMAIN_LABELS) else "general_academic"

        logger.debug(
            "ContentRelevanceGate Stage C: score=%.3f domain=%s threshold=%.2f topic=%s",
            best_score, matched_domain, _EMBED_THRESHOLD, topic_id,
        )

        if best_score >= _EMBED_THRESHOLD - _AMBIGUOUS_BAND:
            # Pass (clear pass or ambiguous band → Stage D decides)
            return None, best_score, matched_domain

        # Definitively off-topic
        return (
            GateResult.rejected(
                stage="embedding",
                rejection_code="off_topic",
                reason=(
                    "This document does not appear to be academic study material. "
                    "IndieTutor accepts textbooks, lecture notes, research papers, "
                    "past exam papers, and course materials."
                ),
                confidence=1.0 - best_score,
                details={
                    "best_similarity": round(best_score, 4),
                    "threshold": _EMBED_THRESHOLD,
                    "nearest_domain": matched_domain,
                },
            ),
            best_score,
            matched_domain,
        )
    except Exception as exc:
        logger.warning(
            "ContentRelevanceGate Stage C: Error during similarity check (%s). "
            "Running in degraded/fail-open mode for topic=%s.",
            exc, topic_id, exc_info=True,
        )
        return None, 0.5, "unknown"


# ══════════════════════════════════════════════════════════════════════════════
# Stage D: LLM Classifier — Ambiguous Cases Only
# Cost: 1 short LLM call (~50-100 tokens in, ~20 out), ~500ms-2s
# Only reached when Stage C score lands in the ambiguous band.
# ══════════════════════════════════════════════════════════════════════════════

_LLM_CLASSIFIER_PROMPT = """\
You are a content moderation classifier for an academic tutoring platform.
Analyze the following text sample from a student-uploaded document.

Academic study material includes: textbooks, lecture notes, research papers,
past exam papers, assignment sheets, course slides, scientific reports,
biology/anatomy/medical education texts, and language learning materials.

NOT academic: personal letters, menus, receipts, invoices, marketing materials,
social media posts, adult entertainment content, travel itineraries, booking forms.

NOTE: Biology and health education documents that contain anatomical or
reproductive terminology in a scientific context ARE considered academic.

Text Sample:
---
{sample}
---

Respond ONLY with valid JSON:
{{"is_academic": true/false, "confidence": 0.0-1.0, "reason": "brief reason"}}"""


async def _stage_d_llm_classifier(
    text: str,
    topic_id: str = "",
) -> Optional[GateResult]:
    """
    Stage D — LLM classifier for ambiguous documents.
    Uses multi-point stratified sampling across the document.
    Fails open (returns None) on LLM error if RELEVANCE_GATE_LLM_FALLBACK=True.
    """
    llm_fallback = getattr(settings, "RELEVANCE_GATE_LLM_FALLBACK", True)
    try:
        from app.rag.ollama_client import ollama
        import json

        # Sample across multiple points (head, middle, later section)
        sample = _extract_multi_point_sample(text, total_target_chars=600, num_chunks=3)
        prompt = _LLM_CLASSIFIER_PROMPT.format(sample=sample)
        messages = [
            {"role": "system", "content": "You are a JSON-only content classifier. Respond only with valid JSON."},
            {"role": "user", "content": prompt},
        ]

        response_text = ""
        async for token in ollama.stream(messages):
            response_text += token
            if len(response_text) > 600:
                break  # safety cap

        json_match = re.search(r'\{[^}]+\}', response_text, re.S)
        if not json_match:
            logger.warning(
                "ContentRelevanceGate Stage D: Failed to parse LLM JSON response, "
                "failing open on ambiguous document (topic=%s, fallback=%s). Response: %s",
                topic_id, llm_fallback, response_text[:100],
            )
            return None

        result = json.loads(json_match.group())
        is_academic = bool(result.get("is_academic", True))
        confidence = float(result.get("confidence", 0.5))
        reason = str(result.get("reason", ""))

        if not is_academic and confidence >= 0.70:
            return GateResult.rejected(
                stage="llm",
                rejection_code="llm_rejected",
                reason=(
                    f"This document was classified as non-academic content: {reason}. "
                    "Please upload textbooks, lecture notes, research papers, or other study materials."
                ),
                confidence=confidence,
                details={"llm_reason": reason, "llm_confidence": confidence},
            )
        return None

    except Exception as exc:
        logger.warning(
            "ContentRelevanceGate Stage D: LLM classifier failed (%s), %s",
            exc,
            f"failing open on ambiguous document (topic={topic_id}, fallback=enabled)."
            if llm_fallback
            else f"rejecting document (topic={topic_id}, fallback=disabled).",
            exc_info=True,
        )
        if llm_fallback:
            return None
        return GateResult.rejected(
            stage="llm",
            rejection_code="llm_rejected",
            reason="Document relevance could not be verified. Please try again later.",
            confidence=0.5,
        )


# ══════════════════════════════════════════════════════════════════════════════
# Public API: ContentRelevanceGate
# ══════════════════════════════════════════════════════════════════════════════
class ContentRelevanceGate:
    """
    4-stage content relevance gate. Singleton — call `.check(pages, topic_id)` per upload.
    """

    async def check(
        self,
        pages: List[Dict],
        topic_id: str = "",
        *,
        full_text: Optional[str] = None,
    ) -> GateResult:
        """
        Run the full 4-stage cascade on document pages.

        Args:
            pages:      List of page dicts with 'text' keys (from DocumentParser).
            topic_id:   Namespace string for logging context.
            full_text:  Pre-joined text (optional, avoids double-joining).

        Returns:
            GateResult — always returns, never raises.
        """
        if not getattr(settings, "RELEVANCE_GATE_ENABLED", True):
            return GateResult.passed_result("general", "disabled", 1.0)

        if full_text is None:
            full_text = "\n\n".join(
                p.get("text", "") for p in pages if p.get("text", "").strip()
            )

        logger.info(
            "ContentRelevanceGate: Checking (topic=%s, text_length=%d chars)",
            topic_id, len(full_text),
        )

        # ── Stage A: Content Quality Checks ───────────────────────────────
        result = _stage_a_content_quality(full_text)
        if result:
            logger.info("ContentRelevanceGate: REJECTED Stage A [%s]", result.rejection_code)
            return result

        # ── Stage B: Heuristic Filter ──────────────────────────────────────
        result = _stage_b_heuristic_filter(full_text)
        if result:
            logger.info("ContentRelevanceGate: REJECTED Stage B [%s]", result.rejection_code)
            return result

        # ── Stage C: Embedding Similarity ─────────────────────────────────
        result, best_score, domain = await _stage_c_embedding_similarity(full_text, topic_id=topic_id)
        if result:
            logger.info("ContentRelevanceGate: REJECTED Stage C [off_topic score=%.3f]", best_score)
            return result

        # Determine if score is in the ambiguous band
        is_ambiguous = (
            best_score < _EMBED_THRESHOLD
            and best_score >= _EMBED_THRESHOLD - _AMBIGUOUS_BAND
        )

        # ── Stage D: LLM Classifier (ambiguous only) ───────────────────────
        if is_ambiguous:
            logger.info("ContentRelevanceGate: Ambiguous (%.3f) — escalating to Stage D (topic=%s).", best_score, topic_id)
            result = await _stage_d_llm_classifier(full_text, topic_id=topic_id)
            if result:
                logger.info("ContentRelevanceGate: REJECTED Stage D [llm_rejected]")
                return result
            stage_reached = "llm"
        else:
            stage_reached = "embedding"

        # All stages passed
        logger.info(
            "ContentRelevanceGate: PASSED (score=%.3f, domain=%s, stage=%s, topic=%s)",
            best_score, domain, stage_reached, topic_id,
        )
        return GateResult.passed_result(
            subject_domain=domain,
            stage=stage_reached,
            confidence=best_score,
            details={"best_similarity": round(best_score, 4), "domain": domain},
        )

    def check_sync(self, pages: List[Dict], topic_id: str = "") -> GateResult:
        """
        Synchronous quick-check — runs Stage A + B only (no embedding/LLM).
        Useful for immediate pre-validation before async indexing.
        """
        full_text = "\n\n".join(
            p.get("text", "") for p in pages if p.get("text", "").strip()
        )
        result = _stage_a_content_quality(full_text)
        if result:
            return result
        result = _stage_b_heuristic_filter(full_text)
        if result:
            return result
        return GateResult.passed_result("unknown", "heuristic", 0.9)


# Singleton
content_relevance_gate = ContentRelevanceGate()
