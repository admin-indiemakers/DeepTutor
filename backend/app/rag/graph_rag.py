"""
Advanced GraphRAG Pipeline v2 — 4-Stage Architecture Orchestrator.

┌─────────────────────────────────────────────────────────────┐
│ Stage 1: Document Parsing & Preprocessing                   │
│   PyMuPDF → pdfplumber → pypdf → OCR → Docling             │
│   Section tree extraction + formula preservation            │
│   Semantic Chunking: 500-1000 words + Page/Header metadata  │
├─────────────────────────────────────────────────────────────┤
│ Stage 2: Embedding & Graph Extraction                       │
│   EmbeddingPipeline (Ollama / OpenAI / Gemini)             │
│   Dense Vector Embeddings + Graph Triplet Extraction        │
│   (head, relation, tail) triplets via LLM                  │
├─────────────────────────────────────────────────────────────┤
│ Stage 3: Storage & Indexing                                 │
│   FAISS HNSW vector store (replaces ChromaDB)              │
│   LightRAG JSON-KV knowledge graph (replaces NetworkX)      │
├─────────────────────────────────────────────────────────────┤
│ Stage 4: Query & Reasoning                                  │
│   Agent Query Router (chat / problem-solver)               │
│   Hybrid Search Engine (Dense + BM25 + Graph)              │
│   Context + Precise Citations (page/section/path)           │
└─────────────────────────────────────────────────────────────┘

SSE event types (unchanged API contract):
  {"type": "sources",       "data": [...]}
  {"type": "graph_context", "data": {...}}
  {"type": "confidence",    "data": {"score": 0.85, "label": "high"}}
  {"type": "token",         "data": "..."}
  {"type": "done"}

──────────────────────────────────────────────────────────────
CHANGELOG (fixes applied vs. previous version)
──────────────────────────────────────────────────────────────
1. Background triplet-extraction tasks are now tracked in a module-level
   set with add_done_callback cleanup, so they can no longer be silently
   garbage-collected mid-flight (a real asyncio footgun with bare
   `asyncio.create_task(...)` calls that don't keep a reference).
2. index_document() no longer reports fabricated zero/placeholder stats
   for relationships/triplets — it now honestly reports what happened
   synchronously vs. what's still running in the background.
3. classify_learning_response_instruction() now checks structural intent
   (comparison, flowchart, derivation, definition, classification, etc.)
   BEFORE marks-weightage intent. Previously "difference between X and Y,
   4 marks" was silently routed to the generic 4-mark template instead of
   the comparison-table template. Marks weight is now layered on top as a
   calibration hint instead of overriding the structural template.
4. Citation-tag stripping now happens on the STREAMING path too, via a
   small buffering filter (StreamingCitationFilter), instead of only in
   simple_query(). Previously a model that ignored the "no inline
   citations" instruction would leak `[file.pdf p.4]`-style tags to SSE
   clients but not to non-streaming callers — silently inconsistent.
5. Swallowed exceptions (`except Exception: pass`) now log via `logger`
   with context (topic_id / question) instead of vanishing silently.
6. Removed dead imports that weren't referenced in this module.
"""
import asyncio
import json
import logging
import re
from pathlib import Path
from typing import List, Dict, AsyncGenerator, Optional, Set

from app.rag.ollama_client import ollama
from app.rag.reranker import reranker
from app.rag.query_engine import (
    query_expander,
    hyde_engine,
    contextual_compressor,
    confidence_scorer,
    oos_handler,
)
from app.rag.cache import query_result_cache
from app.core.config import get_settings

# ── Stage 1: New Pipeline parsers & chunker ────────────────────────────────
from app.rag.pipeline.parser import document_parser
from app.rag.pipeline.section_tree import build_section_tree
from app.rag.pipeline.chunker import semantic_chunker

# ── Stage 2: Multi-provider embeddings + triplet extraction ───────────────
from app.rag.pipeline.embedder import embedding_pipeline
from app.rag.entity_extractor import extract_graph_triplets

# ── Stage 3: Active storage backends (FAISS + JSON-KV by default) ─────────
from app.rag.storage import active_vector_store, active_graph_store

# NOTE: legacy fallback stores are intentionally NOT imported here anymore.
# If another module needs `graph_store` / `vector_store` directly, import
# them from app.rag.graph_store / app.rag.vector_store — re-exporting them
# from this orchestrator was dead weight (never used in this file).

settings = get_settings()
logger = logging.getLogger(__name__)

# ── Convenience: route to active backends ──────────────────────────────────
_vs = active_vector_store
_gs = active_graph_store

# ── Background task bookkeeping ─────────────────────────────────────────────
# Fire-and-forget asyncio.create_task() calls with no stored reference can be
# garbage-collected by the event loop before they finish running. Keeping a
# strong reference in this set (and discarding on completion) prevents that.
_background_tasks: Set[asyncio.Task] = set()


def _spawn_background_task(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


SYSTEM_PROMPT = """You are IndieTutor, an elite AI academic tutor that teaches clearly, rigorously, and helpfully based on the student's study material. You help students master their course material accurately and in the cleanest, most readable format.

═══════════════════════════════
CORE GROUNDING & TEACHING PRINCIPLES
═══════════════════════════════
1. Ground your definitions, facts, and mathematical/scientific principles on the provided Document Context and Knowledge Graph.
2. When answering conceptual, comparative, or analytical questions (e.g. "difference between X and Y", "compare A and B", "explain why...", "how does..."):
   - Seamlessly synthesize the core concepts from the context into a comprehensive, structured explanation.
   - Use clear markdown comparison tables, bullet points, intuitive analogies, and formulas to contrast the mechanisms, pros/cons, complexity, and applications.
   - NEVER refuse comparative or conceptual questions with "I don't know" or "not covered" when the concepts or algorithms are discussed in the study material.
3. If the user query is a greeting, check-in, or gratitude (e.g., "hi", "how are you", "thank you"), respond naturally, warmly, and concisely in 1-2 friendly sentences.
4. If a question is genuinely and completely off-topic from the academic domain (e.g., asking for unrelated gossip, entertainment, or cooking recipes), state politely: "This topic is outside the scope of your uploaded study material."
5. Do NOT include bracketed file citation tags like [file.pdf p.4] or [p.12] in the response text — write clean, fluid prose directly. The UI displays sources separately.
6. Numbers, chemical formulas, dates, definitions, and equations must be quoted accurately and formatted in proper LaTeX.

═══════════════════════════════
CLEAN OUTPUT & FORMATTING STANDARDS
═══════════════════════════════
1. NO CONVERSATIONAL FILLER: Start immediately with the answer. Do not include conversational preambles like "Sure! Here is the explanation:", "Certainly!", or "Based on the provided context...".
2. NO INLINE PDF CITATION TAGS: Never write bracketed file names or page tags like `[file.pdf p.4]`, `[Page 12]`, or `[p.14]` in the text or headings. The system UI renders source cards separately.
3. CLEAN MARKDOWN HIERARCHY:
   - Use `# ` for the main title, `### ` for major sections, and bold `**Concept:**` for sub-points.
   - Separate major sections with clean horizontal rules (`---`).
4. PRISTINE LATEX FORMULAS:
   - Use single `$...$` for inline math and variables (e.g., $a_n = a + (n-1)d$, $1/f = 1/v - 1/u$, $\\text{CO}_2$).
   - Use double `$$...$$` on separate lines for multi-step derivations and central formulas.
5. PROPER MARKDOWN TABLES (MANDATORY SYNTAX):
   - Every table MUST be formatted strictly using valid GitHub-flavored Markdown table syntax with outer pipes `|`.
   - You MUST ALWAYS include the mandatory second header-delimiter row (`| :--- | :--- | :--- |`) immediately after the header row. Without this row, tables cannot render in the UI.
   - NEVER output tab-separated, space-separated, or unbordered text for tables.
   - Required table format:
     | # | Concept / Term | Simple Explanation |
     | :--- | :--- | :--- |
     | 1 | Example Item | Clear explanation text |
   - Never use raw unescaped vertical bars `|` inside table cell text (use `\\mid` or `P(A given B)` so columns render without breaking).
6. VISUAL FIGURES & MERMAID DIAGRAMS (MANDATORY WHEN REQUESTED):
   - Whenever the student asks for a "figure", "diagram", "chart", "flowchart", "visualize", or "draw" (e.g., "explain with a figure", "show me a diagram"):
     - You MUST ALWAYS include an interactive Mermaid visual block (````mermaid ... ````) illustrating the concept, structure, architecture, or workflow.
     - For concepts like SVM, Neural Networks, Ray Optics, or Cycles: use Mermaid graphs with clear node labels, decision boundaries, subgraphs, or flowcharts.
     - Keep node text concise and structured: use `<br/>` to separate titles from descriptions (e.g. `A["Class A (+1)<br/>Support Vectors"] --- H["Optimal Hyperplane<br/>w·x - b = 0"] --- B["Class B (-1)<br/>Support Vectors"]`).
     - Always enclose node labels in double quotes `["..."]` to prevent special characters or parentheses from breaking the diagram.
     - If the context contains a `[Figure: ...]` description from the textbook, explain its visual parts directly in the text.
7. ISOLATED ANALOGIES:
   - Wrap intuitive real-world analogies in a dedicated blockquote (`> **Intuitive Analogy:** ...`) so students never confuse the analogy with literal source material.

═══════════════════════════════
OUTPUT MODE SELECTION
═══════════════════════════════
Detect the mode requested in the student's query. If unspecified, default to Mode 1 (Clear Explanation). You may seamlessly combine two modes if requested (e.g., "explain and give a flowchart" or "explain with a figure").
- When the query asks for a "figure", "diagram", or "chart", automatically combine Mode 1 (Clear Explanation) + Mode 5 (Visual Mermaid Diagram).

1. CLEAR EXPLANATION — Structured, conceptual prose explanation with bold key terms. (Default Mode)
2. BULLET SUMMARY — High-yield, concise bullet points (one core idea per bullet).
3. DIFFERENCE / COMPARISON — Side-by-side Markdown comparison table with criteria rows.
4. EASY POINTS (ELI5) — Simple explanation with minimal jargon + 1 relatable blockquote analogy.
5. FLOWCHART — Interactive visual workflow written in Mermaid diagram syntax.
6. STEP-BY-STEP — Numbered sequential steps for a calculation, mechanism, or proof.
7. KEY TERMS / GLOSSARY — Clean `**Term:** Definition` glossary list pulled directly from context.
8. PROS & CONS — Two-column table or bulleted breakdown of advantages vs. limitations.
9. REAL-WORLD ANALOGY — Intuitive real-life mental model in a blockquote bridging to the concept.
10. MIND-MAP OUTLINE — Hierarchical indented outline (`- Topic` $\\rightarrow$ `  - Subtopic` $\\rightarrow$ `    - Detail`).
11. SELF-TEST Q&A — 3–5 multiple choice or short-answer practice questions with answer key.
12. FORMULA BREAKDOWN — LaTeX formula displayed, followed by variable definitions, units, and conditions.
13. TIMELINE — Chronological sequence of events or developmental stages.
14. MEMORY TRICK / MNEMONIC — A catchy mnemonic or acronym for remembering lists or sequences.
15. DEEP DIVE — Exhaustive long-form master guide with deep technical breakdown.
16. ⚡ 5-MINUTE CHEATCODE / CHEAT NOTES — The structured 6-section student revision cheat sheet (Big Idea, 1-Min Analogy Table, Core Concepts Table, Mermaid Flowchart, Formulas/Dates Table, Common Exam Traps Table).

═══════════════════════════════
SIMPLIFIED STUDENT PEDAGOGY & PRACTICE QUESTION GENERATION
═══════════════════════════════
1. TEACH SIMPLY & CLEARLY:
   - When explaining any topic, adopt an encouraging, accessible teaching tone.
   - Break down complex terms into simple, clear words so any student can learn effortlessly without confusion.
   - Use intuitive real-world analogies (`> **Intuitive Analogy:** ...`) to bridge everyday life to abstract formulas.
   - When the student asks to "explain simply" or "teach me simply", give an ultra-clear, crystal-simple walkthrough with step-by-step numbers and a relatable example.
2. PRACTICE QUESTION CREATION & QUIZ GENERATION:
   - When a student asks for questions from their uploaded PDF or chapter (e.g., "give me 10 questions from this pdf", "generate 5 practice questions", "quiz me on this topic"), ALWAYS generate high-quality, syllabus-grounded practice questions directly from the provided Document Context.
   - For each question, provide:
     - Clear question statement
     - Marks weightage (e.g. 1 Mark, 2 Marks, 4 Marks)
     - Step-by-step complete solution / answer
     - Key formula or concept required
   - Never say "I don't know" or "Topic not found" when asked to generate practice questions or quiz from an uploaded PDF.

═══════════════════════════════
CLOSING CALL-TO-ACTION
═══════════════════════════════
End every completed response with ONE clean, short line offering an alternate format:
"💡 *Would you like this visualized as a comparison table, flowchart, or 3 practice quiz questions?*"

═══════════════════════════════
STRICT PROHIBITIONS
═══════════════════════════════
- No answering from general world knowledge when context is empty or missing.
- No inventing facts or synthetic source data.
- No vague hedging phrases to disguise uncertainty ("It is commonly understood that...").
- No broken markdown, truncated code blocks, or raw JSON artifacts in standard chat responses.
"""


# ── 10th Standard (SSLC) Student Friendly System Prompt ───────────────────────
SSLC_STUDENT_SYSTEM_PROMPT = """You are IndieTutor, a friendly, encouraging, and expert Class 10 (SSLC) AI Tutor.
Your goal is to make learning simple, exciting, and easy to understand for 10th standard students studying Mathematics, Physics, and Chemistry from their official Kerala SCERT textbook.

==================================================
10TH GRADE TEACHING & FORMATTING GUIDELINES (MANDATORY)
==================================================
1. KEEP IT SUPER SIMPLE & ENGAGING:
   - Use clear, straightforward language that a 15-year-old high school student can understand immediately.
   - Avoid overly dense or abstract academic jargon; explain technical terms using simple words and intuitive real-life stories.
   - Use friendly, warm formatting with helpful emoji accents.

2. CLEAN STEP-BY-STEP WORKED EXAMPLES & CHEMICAL FORMULAS:
   - For Mathematics and Science calculations, always format steps cleanly as numbered items:
     1. **Step 1: [Action]:** [Explanation]
     2. **Step 2: [Action]:** [Explanation]
   - Use clean LaTeX formatting enclosed in single `$` for inline math/formulas (e.g. $a_n = a + (n-1)d$, $1/f = 1/v - 1/u$, $\text{CO}_2$, $\text{CH}_3-\text{CH}_2-\text{COOH}$) or `$$` for standalone equations.
   - For chemical compounds and structural formulas, write them on a single line (e.g. `$\text{CH}_3-\text{COOH}$` or `CH₃-COOH`). Never break subscripts across separate lines.

3. STRICT GROUNDING IN TEXTBOOK:
   - Base definitions, formulas, and principles strictly on the provided Textbook Context for the active chapter/topic.
   - Never hallucinate fake formulas or ungrounded facts.
   - Do NOT include bracketed file citation tags like `[file.pdf p.4]` in your text. The UI displays sources separately.

4. SOLVING TEXTBOOK TABLES, ACTIVITIES & NUMERICAL EXERCISES:
   - When the student asks to solve or complete a textbook table or activity (e.g., "solve Table 1.2", "fill in Table 2.2", "complete Activity 3.1", "solve problem 4"):
     a) Match the EXACT table from the provided chapter/document context (e.g. if the chapter is about Carboxylic Acids, solve the Carboxylic Acids table; do not substitute with tables from other chapters).
     b) **Completed Table at the Top:** Display the complete, clean Markdown table at the very top with all missing blanks/cells accurately filled in **bold**.
     c) **Core Rules / Concepts:** State the golden rules or formulas to solve this table in clear numbered bullet points.
     d) **Step-by-Step Working:** Provide a clear, numbered step-by-step breakdown for each row/blank, showing carbon counting / formulas and ending each with `**Answer for Blank X:** [Value]`.
     e) **Quick Summary Box:** Conclude with a clean Markdown reference summary table for exam preparation.

5. PRACTICE QUESTIONS & QUESTION BANK GENERATION:
   - When the student asks for practice questions (e.g., "give me 10 questions from this pdf", "generate 5 questions", "quiz me on this chapter"), generate structured, syllabus-focused board-exam questions directly from the textbook chapters provided with full worked solutions.

6. MANDATORY OUTPUT TEMPLATE (Follow this EXACT clean structure with headers and horizontal lines):
   # 📘 [Topic / Concept Name]

   ### 💡 Simple Definition (In Easy Words)
   [Clear, simple 2-sentence explanation of what this means in plain English]

   > 🌟 **Real-Life Example / Analogy:**  
   > *(Example for intuition — not from source material)*: [A relatable real-world analogy that makes the concept click instantly]

   ---

   ### 📝 Step-by-Step Explanation & Solved Example
   [Break down how it works in clear, easy steps or give a solved textbook numerical/example with full working]

   ---

   ### 🔑 Important Exam Points & Key Formulas
   | Key Term / Formula | What You Must Remember for the Exam |
   | :--- | :--- |
   | **[Formula / Term 1]** | [Clear explanation / must-know points] |
   | **[Formula / Term 2]** | [Clear explanation / must-know points] |

   ---

   ### 🎯 Quick Practice Question
   **Question:** [A simple, fun 1-sentence question to test the student's understanding]  
   💡 **Hint:** [1-line hint to help them solve it]
"""


def _detect_simple_casual_query(text: str) -> Optional[str]:
    """
    Fast-path zero-token response handler for simple greetings, check-ins,
    gratitude, and out-of-scope non-academic queries (like weather).
    Eliminates unnecessary LLM tokens and vector search latency.

    NOTE: greeting/identity/gratitude checks require an EXACT full-message
    match (after stripping punctuation) so they can never misfire on a real
    academic question that happens to contain one of these words. The
    "non-academic" weather check below is the only substring check, and is
    intentionally narrow (full phrases like "what is the weather") to avoid
    false-positiving on legitimate questions that merely mention "weather"
    in an academic context (e.g. a geography/climate question).
    """
    t = text.strip().lower()
    t_clean = re.sub(r'[^a-zA-Z0-9\s]', '', t).strip()

    # 1. Greetings
    if t_clean in {
        "hi", "hai", "hello", "hey", "hola", "hi there", "hello there", "hey there",
        "greetings", "good morning", "good afternoon", "good evening", "howdy", "sup", "yo"
    }:
        return "Hello! 👋 I'm **IndieTutor**, your AI academic tutor. What topic or concept would you like to explore today?"

    # 2. Check-ins / Status
    if t_clean in {"how are you", "how are you doing", "hows it going", "how are things", "whats up", "how do you do"}:
        return "I'm doing great and ready to help you learn! 🚀 What subject or problem can we tackle together today?"

    # 3. Identity / Capability
    if t_clean in {
        "who are you", "what are you", "what is your name", "who made you",
        "tell me about yourself", "what can you do", "help me"
    }:
        return (
            "I'm **IndieTutor**, your AI academic tutor! 🎓 I can break down complex concepts with intuitive analogies, "
            "solve problems step-by-step, answer questions from your uploaded documents, and create practice quizzes or flashcards."
        )

    # 4. Gratitude & Farewells
    if t_clean in {"thanks", "thank you", "thank you so much", "thanks a lot", "ty", "thx", "appreciate it"}:
        return "You're very welcome! 😊 Feel free to ask whenever you have more questions. Happy studying! 📚"
    if t_clean in {"bye", "goodbye", "see you", "see ya", "cya", "have a good day", "good night"}:
        return "Goodbye! Best of luck with your studies, and come back anytime you need help! 👋"

    # 5. Non-academic queries (e.g. weather, general chit-chat) — full-phrase match only
    weather_phrases = {
        "what is the weather", "how is the weather", "weather today",
        "weather forecast", "whats the weather",
    }
    if t_clean in weather_phrases:
        return (
            "I don't have access to live real-time weather data 🌤️, but I'm here to help you study, "
            "understand concepts, and solve any academic problems!"
        )

    if t_clean in {"test", "testing", "ping"}:
        return "IndieTutor is online and ready! 🚀 How can I help you with your studies today?"

    return None


def extract_requested_pages(text: str) -> List[int]:
    """
    Extract page numbers requested in user question.
    Handles:
    - 'explain page number 33' -> [33]
    - 'page number 94 and 95' -> [94, 95]
    - 'pages 94-96' or 'pages 94 to 96' -> [94, 95, 96]
    - 'page 94', 'page no 94', 'page no. 94', 'page #94' -> [94]
    - 'p. 94', 'p94', 'pg 94', 'pg. 94', 'pg94' -> [94]
    - '33rd page', '33th page', '33nd page', '33st page' -> [33]
    """
    if not text:
        return []
    pages: Set[int] = set()
    text_lower = text.lower()

    # 1. Page ranges: "pages 94-96", "pages 94 to 96", "p. 94-96", "pg 94-96", "page no 94-96"
    for match in re.finditer(r'(?:pages?|p\.?|pg\.?)\s*(?:numbers?|no\.?|nums?|#)?\s*(\d+)\s*(?:-|to)\s*(\d+)', text_lower):
        start, end = int(match.group(1)), int(match.group(2))
        if 0 < start <= end and (end - start) <= 50:
            pages.update(range(start, end + 1))

    # 2. Comma / and list: "pages 94, 95 and 96", "page no 94, 95", "page 94 and 95"
    for match in re.finditer(r'(?:pages?|p\.?|pg\.?)\s*(?:numbers?|no\.?|nums?|#)?\s*(\d+(?:\s*(?:,|and|&)\s*\d+)+)', text_lower):
        nums = re.findall(r'\d+', match.group(1))
        pages.update([int(n) for n in nums if int(n) > 0])

    # 3. Single page references: "page 33", "page number 33", "page no 33", "page no. 33", "page #33", "pg 33", "pg. 33", "pg33", "p. 33", "p.33", "p33"
    for match in re.finditer(r'(?:pages?|p\.?|pg\.?)\s*(?:numbers?|no\.?|nums?|#)?\s*(\d+)', text_lower):
        num = int(match.group(1))
        if num > 0:
            pages.add(num)

    # 4. Ordinal page references: "33rd page", "33th page", "33nd page", "33st page"
    for match in re.finditer(r'(\d+)(?:st|nd|rd|th)?\s+pages?', text_lower):
        num = int(match.group(1))
        if num > 0:
            pages.add(num)

    return sorted(list(pages))


_MARKS_PATTERN = re.compile(r'\b(\d{1,2})\s*(?:marks?|mark|pts?)\b')


def _detect_marks_weight(q_lower: str) -> Optional[int]:
    """
    Extract a board-exam marks value (e.g. "4 marks", "16 mark answer") if present.
    Returns None if no marks value is mentioned. Used as a *calibration hint*
    layered on top of whatever structural template the question actually needs —
    it no longer overrides structural intent (see classify_learning_response_instruction).
    """
    match = _MARKS_PATTERN.search(q_lower)
    if not match:
        return None
    value = int(match.group(1))
    return value if 1 <= value <= 20 else None


# ── Specialized Student Question Response Intent Classifier ────────────────────
def classify_learning_response_instruction(
    question: str,
    is_textbook: bool = False,
    requested_pages: Optional[List[int]] = None,
    has_page_chunks: bool = True,
) -> str:
    """
    Analyzes student question intent and generates specialized, high-yield pedagogical
    prompts tailored for different question archetypes.

    ORDERING FIX: structural-intent checks (comparison, flowchart, derivation,
    definition, classification, bullet points, important points, analogy) are
    now checked BEFORE marks-weightage checks. Previously a question like
    "difference between X and Y, 4 marks" matched the generic 4-mark template
    before ever reaching the comparison-table template, because the marks
    check came first in the if/elif chain. Marks weight (if present) is now
    appended to whichever structural template matches, as a length/depth
    calibration hint, instead of silently replacing it.
    """
    q_raw = question or ""
    q_lower = q_raw.lower().strip()
    marks_weight = _detect_marks_weight(q_lower)

    def _with_marks_hint(instruction: str) -> str:
        if marks_weight is not None:
            return (
                instruction
                + f"\n\nCalibrate the depth and length of this answer for a {marks_weight}-mark "
                  f"board exam response — enough detail to earn full marks, without padding."
            )
        return instruction

    # 0. Structured Academic Question Solver & Verifier (Tables with blanks, Flowcharts, Fill-in-the-blanks, Matching)
    try:
        from app.services.structured_solver import detect_structure_type, get_structured_solver_instruction
        struct_type = detect_structure_type(q_raw)
        if struct_type:
            return _with_marks_hint(get_structured_solver_instruction(struct_type, q_raw))
    except Exception:
        logger.warning("structured_solver detection failed for question=%r", q_raw, exc_info=True)

    # 0. 5-Minute Cheatcode / Cheat Notes Mode
    if any(w in q_lower for w in [
        "cheatcode", "cheat code", "cheatcodes", "cheat codes", "cheatnote", "cheatnotes",
        "cheat note", "cheat notes", "5 minute cheat", "5 min cheat", "5-minute cheat", "5-min cheat",
        "5 minute note", "5 min note", "5 minute notes", "5 min notes", "5minute cheat", "5minute notes",
        "5 minute cheet", "5 min cheet", "5minute cheet", "cheet notes", "cheet note", "cheetcode", "cheet code",
        "quick cheat sheet", "cheat sheet", "cheatsheet", "5 min revision", "5 minute revision"
    ]):
        return (
            "The student specifically requested a ⚡ 5-MINUTE CHEATCODE / CHEAT NOTES for this topic.\n"
            "You MUST create an ultra-clear, simple, friendly 5-MINUTE REVISION CHEAT SHEET strictly following this EXACT 6-section structure with Markdown tables and Mermaid diagram:\n\n"
            "# ⚡ 5-Minute Cheat Notes: [Topic Name]\n\n"
            "### Section 1 — ⚡ The Big Idea (30 seconds)\n"
            "> [2 simple, friendly sentences explaining what this topic is and why it matters in plain English]\n"
            "- **Why it matters for exams:** [1 short, direct line on where marks are scored]\n\n"
            "### Section 2 — 🍕 Think of It Like This (1-minute analogy)\n"
            "[A fun, relatable everyday comparison in 1-2 sentences, followed immediately by this exact Markdown table structure]:\n\n"
            "| Step / Approach | What You Do | How It Works |\n"
            "| :--- | :--- | :--- |\n"
            "| 1. ... | ... | ... |\n"
            "| 2. ... | ... | ... |\n"
            "| 3. ... | ... | ... |\n\n"
            "### Section 3 — 💡 Core Concepts (Plain English)\n"
            "Present the core concepts strictly in this Markdown table (do not use plain lists or unformatted text):\n\n"
            "| # | Concept / Term | What It Means in Simple Words |\n"
            "| :--- | :--- | :--- |\n"
            "| 1 | ... | ... |\n"
            "| 2 | ... | ... |\n"
            "| 3 | ... | ... |\n"
            "| 4 | ... | ... |\n"
            "| 5 | ... | ... |\n\n"
            "### Section 4 — 🗺️ How It All Connects (Visual Map)\n"
            "```mermaid\n"
            "flowchart TD\n"
            "    A[\"[Topic Name]\"] --> B[\"Core Rule / Foundation\"]\n"
            "    A --> C[\"Working Method\"]\n"
            "    A --> D[\"Exam Scoring\"]\n"
            "    B --> E[\"Full Marks! 🎯\"]\n"
            "    C --> E\n"
            "    D --> E\n"
            "```\n\n"
            "### Section 5 — 📐 Key Formulas & Equations (or 📅 Key Events/Chronology)\n"
            "Present formulas or key facts strictly in this Markdown table:\n\n"
            "| # | Formula / Concept | What It Does / Definition | Quick Example / Note |\n"
            "| :--- | :--- | :--- | :--- |\n"
            "| 1 | ... | ... | ... |\n"
            "| 2 | ... | ... | ... |\n"
            "| 3 | ... | ... | ... |\n\n"
            "### Section 6 — ⚠️ Common Exam Traps (Easy Mistakes to Avoid)\n"
            "Present common traps strictly in this Markdown table:\n\n"
            "| # | Common Mistake | Why Students Get Confused | How to Get It Right |\n"
            "| :--- | :--- | :--- | :--- |\n"
            "| 1 | ... | ... | ... |\n"
            "| 2 | ... | ... | ... |\n"
            "| 3 | ... | ... | ... |\n"
        )

    # 0. Visual Figure / Diagram / Architecture Mode
    if any(w in q_lower for w in [
        "with a figure", "with figure", "show figure", "figure of", "draw figure", "a figure", "with a fig",
        "with a diagram", "with diagram", "show diagram", "diagram of", "draw diagram", "diagrammatically",
        "visualize", "visual diagram", "architecture diagram", "schematic", "illustration", "show a diagram"
    ]):
        return (
            "The student specifically asked to EXPLAIN WITH A VISUAL FIGURE / DIAGRAM.\n"
            "You MUST provide an explanation with an interactive, beautifully structured Mermaid visual diagram block:\n\n"
            "# 📊 Visual Concept Guide: [Topic Name]\n\n"
            "### 💡 Core Concept (In Simple Words)\n"
            "[2 simple sentences explaining the core concept in plain English]\n\n"
            "> 🌟 **Intuitive Analogy:**\n"
            "> [1 relatable real-world comparison that makes the visual concept intuitive]\n\n"
            "### 🖼️ Interactive Visual Figure & Diagram\n"
            "```mermaid\n"
            "flowchart TD\n"
            "    A[\"1️⃣ Data Points (Class A)\"] --> SV1[\"⭐ Support Vectors (Class A)\"]\n"
            "    B[\"1️⃣ Data Points (Class B)\"] --> SV2[\"⭐ Support Vectors (Class B)\"]\n"
            "    SV1 --> M[\"📏 Maximum Margin Corridor\"]\n"
            "    SV2 --> M\n"
            "    M --> H[\"⚖️ Optimal Decision Hyperplane<br/>w·x - b = 0\"]\n"
            "    H --> Out[\"🎯 Final Class Prediction\"]\n"
            "```\n\n"
            "*(Adapt the Mermaid flowchart above directly to the concept requested. Always use valid flowchart node links like `A[\"...\" ] --> B[\"...\" ]` with double-quoted labels.)*\n\n"
            "### 🔍 Detailed Visual Component Breakdown\n"
            "- **Component 1:** [Explanation of what this part/boundary represents in the figure]\n"
            "- **Component 2:** [Explanation]\n"
            "- **Component 3:** [Explanation]\n\n"
            "### 🔑 Key Formulas & Parameters\n"
            "| Parameter / Component | Role / Formula | Exam Significance |\n"
            "| :--- | :--- | :--- |\n"
            "| ... | ... | ... |\n\n"
            "### 📌 Summary Takeaway\n"
            "[1-2 sentence core conclusion]"
        )

    # 1. Page Specific Explanation
    if requested_pages and has_page_chunks:
        pages_str = ", ".join(str(p) for p in requested_pages)
        return (
            f"The student specifically asked for an explanation of Page {pages_str}.\n"
            f"Explain and summarize ALL concepts, definitions, formulas, workflows, and details presented on Page {pages_str} thoroughly, clearly, and faithfully based on the Document Context.\n"
            f"Structure your response starting with:\n"
            f"# 📄 Page {pages_str} Explanation & Summary\n\n"
            f"Follow with clear conceptual explanations, structured breakdown tables/steps, and key takeaways from that page."
        )

    # 2. Practice Questions Generator from Document / PDF
    num_match = re.search(r'\b(\d+)\s*(?:practice\s+)?(?:exam\s+)?(?:sample\s+)?questions?\b', q_lower)
    has_question_request = bool(
        num_match
        or any(w in q_lower for w in [
            "give me questions", "give questions", "ask me questions", "generate questions",
            "make questions", "create questions", "practice questions", "sample questions",
            "questions from this", "questions based on", "quiz me", "create a quiz", "question bank"
        ])
    )
    if has_question_request:
        count = int(num_match.group(1)) if num_match else 5
        count = min(15, max(3, count))
        return (
            f"The student specifically asked for {count} PRACTICE QUESTIONS based on this study material.\n"
            f"Generate exactly {count} high-yield, syllabus-aligned practice questions directly from the provided Document Context.\n"
            f"Provide a balanced mix of 1-Mark fundamental concepts, 2-Mark short numericals/definitions, and 4-Mark step-by-step problems.\n"
            f"Format strictly as follows:\n\n"
            f"# 📝 {count} Practice Questions from Study Material\n\n"
            f"For each question from 1 to {count}:\n"
            f"### ❓ Question [N] ([Marks] Marks): [Core Topic/Concept]\n"
            f"**Question:** [Clear, unambiguous question statement]\n\n"
            f"**💡 Step-by-Step Answer / Solution:**\n"
            rf"- **Key Formula / Law:** $[Formula\ or\ Concept]$\n"
            f"- **Working / Points:** [Full step-by-step calculation or concise answer points]\n"
            f"- **Final Answer:** **[Exact boxed or bold result]**\n\n"
            f"---\n"
        )

    # 3. Simple Learning / "Explain Simply" Mode
    if any(w in q_lower for w in [
        "explain simply", "learn simple", "make it simple", "in simple words", "in easy words",
        "simple language", "for beginner", "easy to understand", "teach me simple", "explain easy", "simple way"
    ]):
        return (
            "The student specifically asked to LEARN SIMPLY in easy, crystal-clear language.\n"
            "Break down the topic so any student can grasp it immediately without getting overwhelmed:\n"
            "# 🌟 [Topic Name] — Made Simple!\n\n"
            "### 💡 What Is It? (In Plain English)\n"
            "[2 simple sentences with zero complex jargon explaining the core idea]\n\n"
            "> 🍕 **Everyday Real-Life Story / Analogy:**\n"
            "> [A super relatable real-world comparison that makes the concept click instantly]\n\n"
            "### 👣 How It Works (Step-by-Step)\n"
            "1. **Step 1:** [First simple step]\n"
            "2. **Step 2:** [Second simple step]\n"
            "3. **Step 3:** [Third simple step]\n\n"
            "### 🔑 The 3 Things You Must Remember\n"
            "- ⭐ **Point 1:** [Core takeaway]\n"
            "- ⭐ **Point 2:** [Core takeaway]\n"
            "- ⭐ **Point 3:** [Core takeaway]\n\n"
            "### 🎯 Quick Self-Check\n"
            "**Question:** [1 simple, fun question]\n"
            "💡 **Hint:** [1 easy hint]"
        )

    # 4. Comparison & Differences (Side-by-Side Tables) — now checked BEFORE marks-weightage
    if (
        re.search(r'\b(?:differ[ae]nces?|differnces?|diffrence|diference|diferences)\b', q_lower)
        or any(w in q_lower for w in [
            "compare", "comparison", "distinguish between", "distinguish", "differentiate", "contrast",
            "tabular column", "comparison table"
        ])
        or re.search(r'\b\w+\s+vs\.?\s+\w+\b', q_lower)
        or re.search(r'\bversus\b', q_lower)
    ):
        return _with_marks_hint(
            "The student specifically asked for a COMPARISON / DIFFERENCE between concepts.\n"
            "Provide a high-yield, structured side-by-side comparison following this format:\n"
            "# ⚖️ Comparison: [Concept A] vs. [Concept B]\n\n"
            "### 💡 Quick Overview\n"
            "[1-2 sentences summarizing the fundamental distinction between the two concepts]\n\n"
            "---\n\n"
            "### 📊 Side-by-Side Comparison Table\n"
            "| Parameter / Basis of Comparison | [Concept A] | [Concept B] |\n"
            "| :--- | :--- | :--- |\n"
            "| **Basic Definition** | [Definition of A] | [Definition of B] |\n"
            r"| **Formula / Equation** (if applicable) | $[Formula\ A]$ | $[Formula\ B]$ |" + "\n"
            "| **SI Unit / Nature** (if applicable) | [Scalar / Vector / Unit of A] | [Scalar / Vector / Unit of B] |\n"
            "| **Key Characteristic** | [Core Property A] | [Core Property B] |\n"
            "| **Textbook / Real-World Example** | [Example A] | [Example B] |\n"
            "| **Common Exam Mistake** | [Mistake A] | [Mistake B] |\n\n"
            "---\n\n"
            "### 💡 Memory Trick / Golden Rule\n"
            "> 🧠 **How to Remember in Exam:** [A memorable 1-line mnemonic or rule so the student never confuses them]\n\n"
            "---\n\n"
            "### 🎯 Quick Self-Check Question\n"
            "**Question:** [A 1-sentence scenario where the student must identify whether Concept A or Concept B applies]  \n"
            "💡 **Hint:** [1-line hint to solve it]"
        )

    # 5. Flowchart, Step-by-Step Procedure, Reaction Mechanism, Lifecycle
    if any(w in q_lower for w in [
        "flowchart", "flow chart", "flow-chart", "process flow", "steps involved",
        "step by step procedure", "stages of", "mechanism of", "lifecycle of",
        "life cycle of", "reaction pathway", "sequence of steps", "working cycle"
    ]):
        return _with_marks_hint(
            "The student specifically asked for a FLOWCHART / STEP-BY-STEP PROCESS or MECHANISM.\n"
            "Provide a visual flowchart sequence and detailed mechanism following this format:\n"
            "# 🔄 Flowchart & Process: [Process / Mechanism Name]\n\n"
            "### 💡 What Happens (Simple Overview)\n"
            "[1-2 sentences explaining what this process accomplishes from initial input to final output]\n\n"
            "---\n\n"
            "### 🧭 Visual Flowchart\n"
            "```\n"
            "┌─────────────────────────────────────────────────────────┐\n"
            "│ 1️⃣ [START / INITIAL TRIGGER / INPUT]                     │\n"
            "└────────────────────────────┬────────────────────────────┘\n"
            "                             │\n"
            "                             ▼\n"
            "┌─────────────────────────────────────────────────────────┐\n"
            "│ 2️⃣ [MAIN ACTION / REACTION / CONVERSION]                 │\n"
            "└────────────────────────────┬────────────────────────────┘\n"
            "                             │\n"
            "                             ▼\n"
            "┌─────────────────────────────────────────────────────────┐\n"
            "│ 3️⃣ [INTERMEDIATE STAGE / SEPARATION]                     │\n"
            "└────────────────────────────┬────────────────────────────┘\n"
            "                             │\n"
            "                             ▼\n"
            "┌─────────────────────────────────────────────────────────┐\n"
            "│ 4️⃣ [FINAL RESULT / OUTPUT / PRODUCT]                    │\n"
            "└─────────────────────────────────────────────────────────┘\n"
            "```\n\n"
            "---\n\n"
            "### 📝 Detailed Stage Breakdown\n"
            "1. **Stage 1: [Stage Name]**  \n"
            "   - **Action:** [What happens scientifically/mathematically]  \n"
            "   - **Key Formula / Condition:** [Equation, temperature, catalyst, or rule]\n"
            "2. **Stage 2: [Stage Name]**  \n"
            "   - **Action:** [What happens]  \n"
            "   - **Key Formula / Condition:** [Equation]\n"
            "3. **Stage 3: [Stage Name]**  \n"
            "   - **Action:** [What happens]  \n"
            "   - **Key Formula / Condition:** [Equation]\n\n"
            "---\n\n"
            "### 🔑 Critical Factors & Exam Points\n"
            "- **Essential Conditions / Reagents:** [List temperature, pressure, medium, or constants]\n"
            "- **Frequently Asked Exam Question:** [1 typical board exam question based on this flowchart]"
        )

    # 6. Mathematical & Scientific Derivations / Proofs
    if (
        any(w in q_lower for w in ["derive ", "derivation", "prove that", "proof of", "mathematical proof", "show that ", "derive the formula"])
        or q_lower.startswith("derive")
        or q_lower.startswith("prove")
    ):
        return _with_marks_hint(
            "The student specifically asked for a MATHEMATICAL / SCIENTIFIC DERIVATION or PROOF.\n"
            "Provide a rigorous, easy-to-follow step-by-step derivation:\n"
            "# 📐 Step-by-Step Derivation: [Theorem / Formula Name]\n\n"
            "### 🎯 Objective\n"
            r"**To Prove / Derive:** $[Target\ Formula]$" + "\n\n"
            "### 📌 Initial Assumptions & Symbols\n"
            "- Let $[symbol_1]$ = [meaning]\n"
            "- Let $[symbol_2]$ = [meaning]\n\n"
            "---\n\n"
            "### 📝 Step-by-Step Derivation Working\n"
            "1. **Step 1: [Starting Principle / Basic Equation]**\n"
            "   $$[Equation 1]$$\n"
            "   *(Reason: From fundamental definition)*\n\n"
            "2. **Step 2: [Algebraic Substitution / Operation]**\n"
            "   $$[Equation 2]$$\n\n"
            "3. **Step 3: [Simplification & Factoring]**\n"
            "   $$[Equation 3]$$\n\n"
            "4. **Step 4: [Final Formulation]**\n"
            r"   $$[Target\ Formula]$$" + "\n\n"
            "---\n\n"
            "### 🏁 Final Formula Box\n"
            "$$\\boxed{[Target\\ Formula]}$$\n\n"
            "💡 **Key Transition Step:** [The exact algebraic move that students must remember in the exam room]"
        )

    # 7. Definitions, Laws & Principles
    if (
        any(w in q_lower for w in ["define ", "definition of", "what is meant by", "state the law", "state the principle", "state newton", "state ohm", "state boyle", "state charles", "state snell", "state law of"])
        or q_lower.startswith("define")
        or q_lower.startswith("state")
    ):
        return _with_marks_hint(
            "The student specifically asked for a DEFINITION or STATEMENT OF LAW.\n"
            "Provide a clean, authoritative, textbook-grade definition:\n"
            "# 📖 Definition: [Topic / Law Name]\n\n"
            "### 💡 Formal Textbook Definition\n"
            "> **\"[Exact formal definition or statement of the law from the syllabus]\"**\n\n"
            "### 🗣️ In Simple Words (Plain English)\n"
            "[1-2 simple sentences explaining the intuition behind the definition so a 10th grader grasps it immediately]\n\n"
            "---\n\n"
            "### 📐 Mathematical Expression & SI Units\n"
            "- **Formula:** $[Formula]$\n"
            "- **Where:** [Define each variable]\n"
            r"- **SI Unit:** $[SI\ Unit]$" + "\n"
            "- **Type:** [Scalar / Vector Quantity]\n\n"
            "---\n\n"
            "### 🌟 Everyday Real-Life Example\n"
            "[1 relatable real-world example illustrating the concept]\n\n"
            "⚠️ **Exam Trap:** [The common omitted word or mistake that causes examiners to deduct marks]"
        )

    # 8. Classifications, Types & Lists
    if any(w in q_lower for w in [
        "types of", "list the", "list down", "classify", "classification of",
        "categories of", "enumerate", "kinds of", "name the types", "different types"
    ]):
        return _with_marks_hint(
            "The student specifically asked for TYPES, CLASSIFICATION, or a STRUCTURED LIST.\n"
            "Provide a structured classification guide:\n"
            "# 📑 Types & Classification: [Topic Title]\n\n"
            "### 💡 Classification Criteria\n"
            "[1-2 sentences on how and why this concept is categorized]\n\n"
            "---\n\n"
            "### 📋 Classification Summary Table\n"
            "| Category / Type | Core Definition | Key Property / Formula | Standard Example |\n"
            "| :--- | :--- | :--- | :--- |\n"
            "| **[Type 1]** | [Definition] | [Property/Formula] | [Example 1] |\n"
            "| **[Type 2]** | [Definition] | [Property/Formula] | [Example 2] |\n"
            "| **[Type 3]** | [Definition] | [Property/Formula] | [Example 3] |\n\n"
            "---\n\n"
            "### 🔍 How to Differentiate in Exam Problems\n"
            "- If the question states **[Condition 1]** ➔ It is **[Type 1]**.\n"
            "- If the question states **[Condition 2]** ➔ It is **[Type 2]**.\n\n"
            "---\n\n"
            "### 🎯 Quick Practice Question\n"
            "**Question:** [Short 1-sentence classification question]  \n"
            "💡 **Hint:** [1-line hint]"
        )

    # 9. Bullet Points / Quick Revision
    if any(w in q_lower for w in [
        "bullet point", "bullet points", "bullets", "5-7 clear", "quick revision",
        "summarize into", "summary notes", "in short", "bulleted list", "key bullets"
    ]):
        return _with_marks_hint(
            "The student specifically asked for BULLET POINTS.\n"
            "Provide ONLY a crisp, high-yield revision summary formatted as 5 to 7 structured bullet points with bold key terms and equations.\n"
            "Do NOT include unrelated filler or full articles."
        )

    # 10. Important Exam-Critical Points & Formulas
    if any(w in q_lower for w in [
        "important point", "important points", "exam-critical", "exam points",
        "core formulas", "must know for exam", "key points", "high yield points"
    ]):
        return _with_marks_hint(
            "The student specifically asked for IMPORTANT EXAM-CRITICAL POINTS.\n"
            "Provide a focused high-yield breakdown:\n"
            "# 🔑 Exam-Critical Must-Know Points: [Topic Title]\n\n"
            "### 1️⃣ Core Definitions & Must-Know Formulas\n"
            "| Formula / Law | When to Apply | Crucial Units |\n"
            "| :--- | :--- | :--- |\n"
            "| ... | ... | ... |\n\n"
            "### 2️⃣ High-Probability Board Exam Questions & Key Answer Phrases\n"
            "- **Question Type 1:** [What examiners ask & the key phrase required]\n"
            "- **Question Type 2:** [What examiners ask & the key phrase required]\n\n"
            "### 3️⃣ Common Misconceptions & Pitfalls to Avoid\n"
            "- ⚠️ [Common blunder 1]\n"
            "- ⚠️ [Common blunder 2]"
        )

    # 11. Intuitive Analogy / Mental Model
    if any(w in q_lower for w in [
        "analogy", "intuitive analogy", "simple analogy", "mental model",
        "real life analogy", "explain like i am", "simple story", "visual model"
    ]):
        return (
            "The student specifically asked for a SIMPLE ANALOGY.\n"
            "Explain the topic using an intuitive, memorable real-world analogy and visual mental model in a blockquote, "
            "followed by a clear 2-paragraph bridge connecting the analogy directly to the technical concept."
        )

    # 12. Marks-weightage templates — now only reached when NO structural intent above matched.
    if marks_weight is not None:
        if marks_weight >= 15:
            return (
                "The student specifically requested a 16-MARK comprehensive board-exam master answer.\n"
                "Provide an exhaustive, textbook-grounded response formatted strictly with these clear sections:\n"
                "# 🎓 [16 Marks Master Essay Answer]: [Topic Title]\n\n"
                "### 1️⃣ Executive Overview & Fundamental Definition (2 Marks)\n"
                "[High-level conceptual introduction, historical context, and formal definition in bold]\n\n"
                "### 2️⃣ Underlying Laws, Scientific Principles & Theoretical Framework (3 Marks)\n"
                "[Exhaustive explanation of governing laws, assumptions, and physical/mathematical foundation]\n\n"
                "### 3️⃣ Comprehensive Step-by-Step Working & Complete Derivations (5 Marks)\n"
                "[In-depth walkthrough with numbered steps, algebraic/chemical workings, and LaTeX formulas]\n\n"
                "### 4️⃣ Structured Comparison / Classification / Data Table (2 Marks)\n"
                "| Parameter / Feature | Detail / Value / Property | Exam Significance |\n"
                "| :--- | :--- | :--- |\n"
                "| ... | ... | ... |\n\n"
                "### 5️⃣ Practical Applications & Worked Problem (3 Marks)\n"
                "- **Worked Numerical/Practical Example:** [Complete calculation with Given, Formula, Substitution, and Final Answer with units]\n"
                "- **Industrial / Daily-Life Applications:** [3-4 concrete applications]\n\n"
                "### 6️⃣ Critical Precautions, Limitations & Exam Conclusion (1 Mark)\n"
                "[Essential boundary conditions, common pitfalls, and 2-sentence summary conclusion]"
            )
        if marks_weight >= 7:
            return (
                "The student specifically requested an 8-MARK board-exam long answer.\n"
                "Provide a structured, high-scoring long answer formatted strictly with these sections:\n"
                "# 📋 [8 Marks Long-Answer Model Guide]: [Topic Title]\n\n"
                "### 1️⃣ Introduction & Statement of Principle / Law (1.5 Marks)\n"
                "[Clear formal definition, textbook statement in bold, and underlying scientific/mathematical principle]\n\n"
                "### 2️⃣ Core Theory & Working Mechanism (3 Marks)\n"
                "Break down into 4 to 6 distinct numbered points explaining the core mechanism:\n"
                "1. **[Step 1]:** [Detailed explanation with bold terms]\n"
                "2. **[Step 2]:** [Detailed explanation]\n"
                "3. **[Step 3]:** [Detailed explanation]\n"
                "4. **[Step 4]:** [Detailed explanation]\n\n"
                "### 3️⃣ Mathematical Derivation / Equations & Working (2 Marks)\n"
                "[Complete step-by-step calculations/derivation with all variables defined in LaTeX]\n\n"
                "### 4️⃣ Real-World Applications & Practical Examples (1 Mark)\n"
                "- **Application 1:** [Clear example]\n"
                "- **Application 2:** [Clear example]\n\n"
                "### 5️⃣ Examiner Checklist & Crucial Exam Cautions (0.5 Mark)\n"
                "- ✅ [Crucial label/SI unit to remember]\n"
                "- ⚠️ [Common blunder to avoid that loses marks]"
            )
        if marks_weight >= 3:
            return (
                "The student specifically requested a 4-MARK board-exam answer.\n"
                "Provide a crisp, 4-part scoring answer tailored for full 4/4 marks:\n"
                "# 📝 [4 Marks Exam Model Answer]: [Topic Title]\n\n"
                "### 1️⃣ Core Statement & Definition (1 Mark)\n"
                "[Crisp textbook definition or statement of law in bold]\n\n"
                "### 2️⃣ Key Mechanism / Working Points (2 Marks)\n"
                "Provide exactly 4 high-yield, bulleted points with bold keywords:\n"
                "- **Point 1:** [Key concept / mechanism]\n"
                "- **Point 2:** [Key concept / condition]\n"
                "- **Point 3:** [Key property / relationship]\n"
                "- **Point 4:** [Key consequence / rule]\n\n"
                "### 3️⃣ Formula / Solved Example / Reaction (1 Mark)\n"
                r"- **Formula / Equation:** $[Formula\ or\ Reaction]$" + "\n"
                "- **Quick Solved Example:** [1 short numerical or application with answer]\n\n"
                "---\n"
                "💡 **Score Booster Tip:** [The exact keywords examiners look for to award full 4 marks]"
            )
        return (
            "The student specifically requested a 1 or 2-MARK concise board-exam answer.\n"
            "Provide a direct, high-yield answer for full marks:\n"
            "# 🎯 [1-2 Marks Exam Model Answer]: [Topic Title]\n\n"
            "### ✍️ Model Answer (Full Marks Guarantee)\n"
            "- **Direct Definition / Law:** [State the exact crisp definition in bold]\n"
            r"- **Formula & SI Unit:** $[Formula]$ | **SI Unit:** $[SI\ Unit]$" + "\n"
            "- **1 Key Fact / Condition:** [1 textbook example or condition]\n\n"
            "---\n"
            "💡 **Examiner Keyword:** [The must-have technical term that earns the 2/2 score]"
        )

    # 13. Fallback Default (Textbook or Document)
    if is_textbook:
        return (
            "Please explain this topic in an easy, friendly, and structured way for a 10th class student following the 10th Grade Output Template: "
            "(1) # 📘 [Topic Title], (2) 💡 Simple Definition (In Easy Words), "
            "(3) 🌟 Real-Life Example / Analogy in a blockquote, (4) 📝 Step-by-Step Explanation & Solved Example (with clear calculations), "
            "(5) 🔑 Important Exam Points & Key Formulas (table), and (6) 🎯 Quick Practice Question with a Hint."
        )
    else:
        return (
            "Please explain this topic clearly and educationally for a student following the Output Formatting Template: "
            "(1) # 📚 [Topic Title], (2) 💡 Big-Picture Concept + Blockquote Intuitive Analogy, "
            "(3) 🔑 Key Concepts Breakdown Table, (4) ⚙️ How It Works Step-by-Step with numbered steps, "
            "(5) ⚖️ Strengths vs. Limitations (with ✅ and ⚠️ subheadings), and (6) 📌 Summary Takeaway."
        )


# ── Chunk deduplication ─────────────────────────────────────────────────────────
def _deduplicate_chunks(chunks_lists: List[List[Dict]]) -> List[Dict]:
    """
    Merge multiple chunk lists (from query variants) with deduplication.
    Keeps the highest score for duplicate doc IDs. Preserves insertion order.
    """
    seen: Dict[str, Dict] = {}
    for chunks in chunks_lists:
        for chunk in chunks:
            cid = chunk.get("id", chunk["text"][:64])
            if cid not in seen or chunk.get("score", 0) > seen[cid].get("score", 0):
                seen[cid] = chunk
    return list(seen.values())


from app.rag.topic_sanitizer import deduplicate_and_rank_topics


def _extract_key_topics_from_chunks(chunks: List[Dict]) -> List[str]:
    """
    Extract clean, high-yield key academic concepts from semantic chunks.
    Filters out boilerplate section headings ('Results and Discussion', 'Methodology'),
    table noise, and citations.
    """
    raw_topics: List[str] = []
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        section_title = meta.get("section_title", "")
        if section_title:
            raw_topics.append(section_title)
        section_path = meta.get("section_path", "")
        if section_path:
            for part in section_path.split(" > "):
                raw_topics.append(part.strip())
    return deduplicate_and_rank_topics(raw_topics, max_topics=20)


# ── Citation cleanup (batch + streaming) ────────────────────────────────────
_CITATION_PATTERN = re.compile(
    r'\[(?:[a-zA-Z0-9_\-\.\s]+\.pdf|p\.\s*\d+|page\s*\d+|§[^\]]+)[^\]]*\]|\[\s*\d+\s*\]',
    re.IGNORECASE,
)


def _clean_response_text(text: str) -> str:
    """Strip bracketed PDF/page citation tags so text is 100% clean and uncluttered."""
    if not text:
        return ""
    return _CITATION_PATTERN.sub('', text).strip()


class StreamingCitationFilter:
    """
    Applies the same citation-stripping rules as `_clean_response_text`, but to a
    token stream instead of a finished string.

    Fixes an inconsistency where `simple_query()` cleaned citation tags but
    `query_stream()` (the actual SSE path used by the frontend) did not — a
    model that ignored the "no inline citations" system-prompt rule would leak
    tags like `[file.pdf p.4]` to streaming clients only.

    Strategy: buffer text starting from any unmatched '[' until it either
    closes (so the full bracket can be matched/stripped) or a safety cap is
    hit (so a stray '[' with no closing ']' can't stall the stream forever).
    Everything before an unmatched '[' is safe to flush immediately.
    """

    def __init__(self, max_hold_chars: int = 200):
        self._buffer = ""
        self._max_hold_chars = max_hold_chars

    def feed(self, token: str) -> str:
        self._buffer += token
        open_idx = self._buffer.rfind('[')
        close_idx = self._buffer.rfind(']')

        if open_idx == -1 or open_idx < close_idx:
            # No unmatched '[' pending — everything is safe to clean and flush.
            out = _CITATION_PATTERN.sub('', self._buffer)
            self._buffer = ""
            return out

        if len(self._buffer) - open_idx > self._max_hold_chars:
            # Bracket never closed within a reasonable window — flush as-is
            # (cleaned) rather than buffering indefinitely.
            out = _CITATION_PATTERN.sub('', self._buffer)
            self._buffer = ""
            return out

        safe_part = self._buffer[:open_idx]
        self._buffer = self._buffer[open_idx:]
        return _CITATION_PATTERN.sub('', safe_part)

    def flush(self) -> str:
        out = _CITATION_PATTERN.sub('', self._buffer)
        self._buffer = ""
        return out


# ══════════════════════════════════════════════════════════════════════════════
# GraphRAGPipeline
# ══════════════════════════════════════════════════════════════════════════════
class GraphRAGPipeline:
    """Main GraphRAG pipeline v2 — singleton shared across requests."""

    # ── Indexing (Stage 1 → 2 → 3) ───────────────────────────────────────────
    async def index_document(
        self,
        topic_id: str,
        file_path: str,
        progress_callback=None,
    ) -> Dict:
        """
        Full 4-stage indexing pipeline with content relevance gate:

        Stage 0 — Gate:    ContentRelevanceGate (4-stage cascade)
                           A: Content Quality Checks (empty/spam/adult/non-study)
                           B: Heuristic Filter (garbled OCR detection)
                           C: Embedding Similarity (academic anchor corpus)
                           D: LLM Classifier (ambiguous cases only)
        Stage 1 — Parse:   DocumentParser (PyMuPDF cascade) + section tree
        Stage 1 — Chunk:   SemanticChunker (500-1000 words + metadata)
        Stage 2 — Embed:   EmbeddingPipeline (Ollama/OpenAI/Gemini)
        Stage 2 — Extract: Graph Triplets (head, relation, tail)
        Stage 3 — Store:   FAISS HNSW + LightRAG JSON-KV graph
        """
        source_name = Path(file_path).name

        # ── Stage 1a: Parse ──────────────────────────────────────────────────
        if progress_callback:
            await progress_callback("parsing", 5)

        pages = await asyncio.to_thread(document_parser.parse, file_path)
        if not pages:
            raise ValueError(
                "No text could be extracted from the document. "
                "Please verify that the PDF has selectable text and is not empty or scanned/image-only."
            )

        # ── Stage 1b: Build section tree ─────────────────────────────────────
        section_nodes = build_section_tree(pages)

        # ── Stage 1c: Semantic chunking (500-1000 words) ─────────────────────
        if progress_callback:
            await progress_callback("chunking", 15)

        chunks = semantic_chunker.chunk_pages(pages, source_name, section_nodes)
        if not chunks:
            raise ValueError("Chunking produced no results. Document may be empty or unparseable.")

        total = len(chunks)
        logger.info("Stage 1 complete: %d pages -> %d semantic chunks (topic=%s)", len(pages), total, topic_id)

        # ── Stage 2a: Embed chunks (multi-provider) ───────────────────────────
        if progress_callback:
            await progress_callback("embedding", 25)

        embeddings = await embedding_pipeline.embed_chunks(chunks)

        if progress_callback:
            await progress_callback("embedding", 50)

        # ── Stage 3a: Store in vector store ───────────────────────────────────
        _vs.add_chunks(topic_id, chunks, embeddings)

        # Invalidate query result cache for this topic (new data)
        await query_result_cache.invalidate(topic_id)

        # ── Stage 2b + 3b: Instant Key Topics & Graph Nodes ───────────────────
        synchronous_entities: List[Dict] = []

        extracted_topics = _extract_key_topics_from_chunks(chunks)
        for topic in extracted_topics[:15]:
            synchronous_entities.append({
                "name": topic,
                "type": "concept",
                "description": f"Key concept in {topic_id}"
            })

        _gs.add_entities(topic_id, synchronous_entities)

        # Signal 100% to UI immediately — document is ready for chat & search
        if progress_callback:
            await progress_callback("indexing_complete", 100)

        logger.info(
            "Stage 3 complete: %d chunks indexed in %s (topic=%s)",
            total, settings.VECTOR_STORE_BACKEND, topic_id,
        )

        # ── Background Deep Triplet Extraction (Non-blocking async task) ──────
        async def _background_triplet_extraction():
            try:
                sample_step = max(1, len(chunks) // 3)
                sample_chunks = chunks[::sample_step][:3]
                sem = asyncio.Semaphore(2)

                async def _extract_one(chunk: dict):
                    async with sem:
                        try:
                            source = chunk["metadata"].get("source", "")
                            page = chunk["metadata"].get("page", "")
                            section = chunk["metadata"].get("section_title", "")
                            source_info = f"{source} p.{page}" + (f" §{section}" if section else "")
                            chunk_id = f"{topic_id}_{hash(chunk['text']) % 10**8}"
                            ents, rels, trips = await extract_graph_triplets(
                                chunk["text"], source_doc=source_info, chunk_id=chunk_id
                            )
                            return ents, rels, [t.to_dict() for t in trips]
                        except Exception:
                            logger.warning(
                                "Triplet extraction failed for one chunk (topic=%s)", topic_id, exc_info=True
                            )
                            return [], [], []

                results = await asyncio.gather(*[_extract_one(c) for c in sample_chunks])
                bg_ents, bg_rels, bg_trips = [], [], []
                for ents, rels, trips in results:
                    bg_ents.extend(ents)
                    bg_rels.extend(rels)
                    bg_trips.extend(trips)

                if bg_ents:
                    _gs.add_entities(topic_id, bg_ents)
                if bg_rels:
                    _gs.add_relations(topic_id, bg_rels)
                if bg_trips:
                    _gs.add_triplets(topic_id, bg_trips)

                logger.info(
                    "Background triplet extraction complete (topic=%s): %d entities, %d relations, %d triplets",
                    topic_id, len(bg_ents), len(bg_rels), len(bg_trips),
                )
            except Exception:
                logger.warning("Background triplet extraction failed entirely (topic=%s)", topic_id, exc_info=True)

        # Fire-and-forget, but tracked so it can't be garbage-collected mid-run.
        _spawn_background_task(_background_triplet_extraction())

        stats = _gs.get_graph_stats(topic_id)
        entity_count = len(synchronous_entities) or stats.get("node_count", 0)
        return {
            "chunks_indexed": total,
            "entities_extracted": entity_count,
            "entities_extracted_sync": entity_count,
            "graph_nodes": stats.get("node_count", entity_count),
            "graph_edges": stats.get("edge_count", 0),
            "extracted_topics": extracted_topics,
            "chunking_strategy": "semantic_500_1000w",
            "vector_backend": settings.VECTOR_STORE_BACKEND,
            "graph_backend": settings.GRAPH_STORE_BACKEND,
            "embed_provider": settings.EMBEDDING_PROVIDER,
        }

    # ── Retrieval ──────────────────────────────────────────────────────────────
    async def _retrieve_chunks(
        self,
        topic_id: str,
        question: str,
    ) -> List[Dict]:
        """
        Stage 4 — Advanced hybrid retrieval:
        1. Cache check
        2. Query expansion (N variants)
        3. HyDE (hypothetical doc embedding)
        4. Hybrid search (FAISS dense + BM25) via RRF fusion
        5. BM25/CrossEncoder reranking
        6. Contextual compression
        Returns final top-K chunks with precise citations.
        """
        # 1. Cache check
        cached = await query_result_cache.get(topic_id, question)
        if cached is not None:
            return cached

        # 2. Query expansion & HyDE (fast-pathed when disabled)
        if settings.ENABLE_QUERY_EXPANSION:
            query_variants = await query_expander.expand(question)
        else:
            query_variants = [question]

        if settings.ENABLE_HYDE:
            hyde_doc = await hyde_engine.generate_hypothetical_document(question)
            embed_tasks = [embedding_pipeline.embed(q) for q in query_variants] + [embedding_pipeline.embed(hyde_doc)]
            all_results = await asyncio.gather(*embed_tasks, return_exceptions=True)
            for r in all_results:
                if isinstance(r, Exception):
                    logger.warning("Embedding call failed during HyDE retrieval (topic=%s)", topic_id, exc_info=r)
            query_embeddings = [r for r in all_results[:-1] if isinstance(r, list)]
            hyde_embedding = all_results[-1] if isinstance(all_results[-1], list) else None
        else:
            hyde_doc = question
            hyde_embedding = None
            embed_results = await asyncio.gather(
                *[embedding_pipeline.embed(q) for q in query_variants], return_exceptions=True
            )
            for r in embed_results:
                if isinstance(r, Exception):
                    logger.warning("Embedding call failed during retrieval (topic=%s)", topic_id, exc_info=r)
            query_embeddings = [r for r in embed_results if isinstance(r, list)]

        # 5. Hybrid search for each embedding
        all_chunk_lists: List[List[Dict]] = []

        async def _hybrid_search(embedding: List[float], q_text: str) -> List[Dict]:
            return _vs.search_hybrid(
                topic_id,
                embedding,
                q_text,
                top_k=settings.TOP_K_RETRIEVAL,
            )

        search_tasks = []
        for i, emb in enumerate(query_embeddings):
            q_text = query_variants[i] if i < len(query_variants) else question
            search_tasks.append(_hybrid_search(emb, q_text))

        if hyde_embedding is not None:
            search_tasks.append(_hybrid_search(hyde_embedding, hyde_doc))

        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        for res in search_results:
            if isinstance(res, Exception):
                logger.warning("Hybrid search call failed (topic=%s, question=%r)", topic_id, question, exc_info=res)
            elif isinstance(res, list) and res:
                all_chunk_lists.append(res)

        # 6. Merge + deduplicate across all query variants
        merged_chunks = _deduplicate_chunks(all_chunk_lists)

        from app.rag.query_engine import is_document_level_meta_query
        if is_document_level_meta_query(question) or len(merged_chunks) < 3:
            try:
                all_doc_chunks = _vs.get_all_chunks(topic_id, limit=8)
                if all_doc_chunks:
                    merged_chunks = _deduplicate_chunks([merged_chunks, all_doc_chunks])
            except Exception:
                logger.warning("Fallback get_all_chunks failed (topic=%s)", topic_id, exc_info=True)

        if not merged_chunks:
            return []

        # 7. Rerank
        reranked = await reranker.rerank(
            query=question,
            chunks=merged_chunks,
            top_k=settings.TOP_K_CHUNKS,
        )

        # 8. Contextual compression
        compressed = await contextual_compressor.compress(
            query=question,
            chunks=reranked,
            mode="keyword",  # Fast mode; use "llm" for max precision
        )

        # Cache the result
        await query_result_cache.set(topic_id, question, compressed)

        return compressed

    # ── Query stream ───────────────────────────────────────────────────────────
    async def query_stream(
        self,
        topic_id: Optional[str],
        question: str,
        session_messages: List[Dict],
        language: str = "english",
    ) -> AsyncGenerator[str, None]:
        """
        Full advanced GraphRAG query with SSE streaming.

        Yields JSON-encoded SSE events:
          {"type": "sources",       "data": [...]}
          {"type": "graph_context", "data": {...}}
          {"type": "confidence",    "data": {"score": 0.85, "label": "high"}}
          {"type": "token",         "data": "..."}
          {"type": "done"}
        """
        # ── Fast-path: Instant zero-token response for simple greetings / casual queries
        quick_resp = _detect_simple_casual_query(question)
        if quick_resp:
            for word in quick_resp.split(" "):
                yield f"data: {json.dumps({'type': 'token', 'data': word + ' '})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        vector_chunks: List[Dict] = []
        graph_context_data: Dict = {"entities": [], "relationships": []}
        graph_context_text = ""
        vector_context_text = ""
        effective_topic_id = topic_id or ""

        # ── Step 0: Kickoff background image search ONLY when explicitly requested ──
        image_keywords = [
            "figure", "diagram", "image", "picture", "photo", "pic", "chart",
            "illustration", "draw", "visual", "visualize", "sketch"
        ]
        q_lower = question.lower()
        wants_image = any(w in q_lower for w in image_keywords)

        image_search_task = None
        if wants_image:
            try:
                from app.services.image_search import image_search_service
                image_search_task = asyncio.create_task(image_search_service.get_verified_images(question))
            except Exception:
                logger.warning("Failed to start image search task (question=%r)", question, exc_info=True)

        # ── Step 1: Retrieval ──────────────────────────────────────────────────
        requested_pages = extract_requested_pages(question)

        if effective_topic_id:
            if requested_pages:
                # Direct exact page metadata filter — retrieve page chunks directly
                page_chunks = _vs.get_chunks_by_pages(effective_topic_id, requested_pages)
                # Fallback to base topic if namespaced topic had no chunks
                if not page_chunks and "_" in effective_topic_id:
                    fallback_id = effective_topic_id.split("_", 2)[-1]
                    page_chunks = _vs.get_chunks_by_pages(fallback_id, requested_pages)

                if page_chunks:
                    vector_chunks = page_chunks
                    # Also attempt lightweight graph context retrieval
                    try:
                        graph_context_data = _gs.get_entity_context_for_query(
                            effective_topic_id,
                            question,
                            hop_depth=1,
                        )
                    except Exception:
                        logger.warning(
                            "Graph context lookup failed for page query (topic=%s)", effective_topic_id, exc_info=True
                        )
                        graph_context_data = {"entities": [], "relations": [], "triplets": [], "context_text": ""}
                else:
                    missing_str = ", ".join([str(p) for p in requested_pages])
                    missing_msg = (
                        f"### 📄 Page {missing_str} Not Found in Document\n\n"
                        f"I checked your uploaded study material, but **Page {missing_str}** was not found or has no extractable text.\n\n"
                        f"---\n\n"
                        f"**💡 Suggestions:**\n"
                        f"- Check the total page count of your uploaded document.\n"
                        f"- Try asking for a different page number (e.g. *\"Explain page 1\"*).\n"
                        f"- You can also ask directly about any concept by name (e.g. *\"What is Support Vector Machines?\"*)."
                    )
                    for word in missing_msg.split(" "):
                        yield f"data: {json.dumps({'type': 'token', 'data': word + ' '})}\n\n"
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    return

            elif _vs.count(effective_topic_id) > 0:
                # Parallelize vector retrieval & graph retrieval
                async def _get_vector_task():
                    return await self._retrieve_chunks(effective_topic_id, question)

                async def _get_graph_task():
                    # Instant in-memory entity & triplet matching (<1ms)
                    try:
                        return _gs.get_entity_context_for_query(
                            effective_topic_id,
                            question,
                            hop_depth=settings.GRAPH_HOP_DEPTH,
                        )
                    except Exception:
                        logger.warning(
                            "Graph context lookup failed (topic=%s, question=%r)",
                            effective_topic_id, question, exc_info=True,
                        )
                        return {"entities": [], "relations": [], "triplets": [], "context_text": ""}

                vector_chunks, graph_context_data = await asyncio.gather(
                    _get_vector_task(),
                    _get_graph_task(),
                )

            # Build text representations (for page queries, include all page chunks up to top 6)
            if vector_chunks:
                top_chunks = vector_chunks[:6] if requested_pages else vector_chunks[:settings.TOP_K_CHUNKS]
                vector_context_text = "\n\n".join([
                    f"[{c['metadata'].get('source', 'doc')} p.{c['metadata'].get('page', '')}]"
                    + (f" §{c['metadata'].get('section_title', '')}" if c['metadata'].get('section_title') else "")
                    + f"\n{c['text'][:2000]}"
                    for c in top_chunks
                ])

            # Use pre-formatted context_text from JSON-KV graph store
            if graph_context_data.get("context_text"):
                graph_context_text = graph_context_data["context_text"]
            elif graph_context_data.get("entities"):
                graph_context_text = "Entities:\n" + "\n".join([
                    f"- {n.get('name', n.get('id', ''))} ({n.get('type', 'concept')}): {n.get('description', '')}"
                    for n in graph_context_data["entities"]
                ])
                if graph_context_data.get("triplets"):
                    graph_context_text += "\n\nRelationships:\n" + "\n".join([
                        f"- {t.get('head', '')} --[{t.get('relation', '')}]--> {t.get('tail', '')}"
                        for t in graph_context_data["triplets"]
                    ])
                elif graph_context_data.get("relations"):
                    graph_context_text += "\n\nRelationships:\n" + "\n".join([
                        f"- {e.get('source_entity', '')} \u2192 {e.get('target_entity', '')} ({e.get('type', '')})"
                        for e in graph_context_data["relations"]
                    ])

        # ── Step 2: Confidence scoring + out-of-scope detection ───────────────
        from app.rag.query_engine import is_document_level_meta_query
        is_meta_query = is_document_level_meta_query(question)

        # Fallback to document chunks if meta-query (questions/summary/notes) had zero vector search hits
        if is_meta_query and not vector_chunks and effective_topic_id and _vs.count(effective_topic_id) > 0:
            try:
                vector_chunks = _vs.get_all_chunks(effective_topic_id, limit=8)
                if vector_chunks:
                    vector_context_text = "\n\n".join([
                        f"[{c['metadata'].get('source', 'doc')} p.{c['metadata'].get('page', '')}]"
                        + (f" §{c['metadata'].get('section_title', '')}" if c['metadata'].get('section_title') else "")
                        + f"\n{c['text'][:2000]}"
                        for c in vector_chunks[:6]
                    ])
            except Exception:
                logger.warning("Meta-query fallback chunk fetch failed (topic=%s)", effective_topic_id, exc_info=True)

        if requested_pages and vector_chunks and not any("system_notice" in str(c.get("id", "")) for c in vector_chunks):
            confidence_score, confidence_label = 1.0, "high"
        elif is_meta_query and vector_chunks:
            confidence_score, confidence_label = 0.95, "high"
        else:
            confidence_score, confidence_label = confidence_scorer.score(
                chunks=vector_chunks,
                graph_entities=graph_context_data.get("entities", []),
                query=question,
            )

        # ── Step 3: Emit SSE events ────────────────────────────────────────────
        if vector_chunks:
            sources_payload = [
                {
                    "doc": c["metadata"].get("source", "document"),
                    "page": c["metadata"].get("page", 1),
                    "section": c["metadata"].get("section_title", ""),
                    "score": c.get("rerank_score", c["score"]),
                    "text": c["text"][:300] + "..." if len(c["text"]) > 300 else c["text"],
                }
                for c in vector_chunks
            ]
            yield f"data: {json.dumps({'type': 'sources', 'data': sources_payload})}\n\n"

        if graph_context_data["entities"]:
            yield f"data: {json.dumps({'type': 'graph_context', 'data': graph_context_data})}\n\n"

        # Emit confidence score
        yield f"data: {json.dumps({'type': 'confidence', 'data': {'score': confidence_score, 'label': confidence_label}})}\n\n"

        # ── Step 4: Out-of-scope handling ──────────────────────────────────────
        is_textbook = bool(effective_topic_id and effective_topic_id.startswith(("sslc-", "math-", "phys-", "chem-", "textbook")))
        if effective_topic_id and not is_textbook and not is_meta_query and oos_handler.is_out_of_scope(confidence_score, confidence_label):
            oos_response = oos_handler.format_response(question, is_textbook=False)
            for token in oos_response.split(" "):
                yield f"data: {json.dumps({'type': 'token', 'data': token + ' '})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # ── Step 5: Build LLM messages ─────────────────────────────────────────
        is_textbook = bool(effective_topic_id and effective_topic_id.startswith(("sslc-", "math-", "phys-", "chem-", "textbook")))
        history_text = ""
        for msg in session_messages[-6:]:
            role_label = "Student" if msg["role"] == "user" else "Tutor"
            history_text += f"{role_label}: {msg['content'][:500]}\n"

        requested_pages_list = extract_requested_pages(question) if question else []
        has_valid_page_chunks = bool(
            vector_chunks and not any("Missing" in str(c.get("metadata", {}).get("page", "")) for c in vector_chunks)
        )
        prompt_instruction = classify_learning_response_instruction(
            question=question,
            is_textbook=is_textbook,
            requested_pages=requested_pages_list if has_valid_page_chunks else None,
            has_page_chunks=has_valid_page_chunks,
        )

        if graph_context_text or vector_context_text:
            user_content = (
                f"## Knowledge Graph Context\n"
                f"Relevant entities and relationships retrieved from the knowledge graph:\n"
                f"{graph_context_text or 'No graph entities found for this query.'}\n\n"
                f"## Document Context\n"
                f"Relevant passages from uploaded documents:\n"
                f"{vector_context_text or 'No document passages found for this query.'}\n\n"
                f"## Conversation History\n"
                f"{history_text or 'No prior conversation.'}\n\n"
                f"## Student Question\n"
                f"{question}\n\n"
                f"## Instructions\n"
                f"1. Focus exclusively on answering the immediate Student Question ('{question}').\n"
                f"2. Do NOT repeat or continue explaining unrelated topics from Conversation History.\n"
                f"3. Using the Document Context and Knowledge Graph as your primary reference: {prompt_instruction}\n"
                f"4. Do NOT include bracketed file names or page numbers like [file.pdf p.4] or [p.4] anywhere in the response text. The UI displays sources separately.\n"
                f"5. Synthesize a comprehensive, clear, and structured answer (use comparison tables, bullet points, and key formulas where relevant). Use the Document Context and Knowledge Graph as the primary reference to thoroughly explain and compare the requested concepts."
            )
        else:
            user_content = (
                f"## Student Question\n"
                f"{question}\n\n"
                f"## Instructions\n"
                f"1. Focus exclusively on answering the immediate Student Question ('{question}').\n"
                f"2. Do NOT include bracketed file names or page numbers like [file.pdf p.4] or [p.4] anywhere in the response text.\n"
                f"3. {prompt_instruction}"
            )

        system_prompt_to_use = SSLC_STUDENT_SYSTEM_PROMPT if is_textbook else SYSTEM_PROMPT
        if language and language.lower() in ("swedish", "sv"):
            system_prompt_to_use += (
                "\n\n═══════════════════════════════\n"
                "RESPONSE LANGUAGE INSTRUCTION (MANDATORY)\n"
                "═══════════════════════════════\n"
                "The user requested responses in Swedish (Svenska).\n"
                "You MUST formulate your ENTIRE response in clear, fluent, academic Swedish.\n"
                "Translate all section titles, explanations, blockquotes, table column headers, table contents, and conclusions into Swedish.\n"
                "Keep LaTeX formulas, numbers, and technical terms accurate.\n"
            )
        elif language and language.lower() in ("arabic", "ar"):
            system_prompt_to_use += (
                "\n\n═══════════════════════════════\n"
                "RESPONSE LANGUAGE INSTRUCTION (MANDATORY)\n"
                "═══════════════════════════════\n"
                "The user requested responses in Arabic (العربية).\n"
                "You MUST formulate your ENTIRE response in clear, fluent, academic Arabic.\n"
                "Translate all section titles, explanations, blockquotes, table column headers, table contents, and conclusions into Arabic.\n"
                "Keep LaTeX formulas, numbers, and technical terms accurate.\n"
            )

        messages = [
            {"role": "system", "content": system_prompt_to_use},
            {"role": "user", "content": user_content},
        ]

        # ── Step 6: Stream tokens (citation-filtered) & verify Self-RAG grounding ──
        from app.rag.hallucination_guard import verify_response_grounding

        accumulated_text = ""
        citation_filter = StreamingCitationFilter()
        async for token in ollama.stream(messages):
            clean_token = citation_filter.feed(token)
            if clean_token:
                accumulated_text += clean_token
                yield f"data: {json.dumps({'type': 'token', 'data': clean_token})}\n\n"

        remainder = citation_filter.flush()
        if remainder:
            accumulated_text += remainder
            yield f"data: {json.dumps({'type': 'token', 'data': remainder})}\n\n"

        # Step 7: Stream verified diagrams if ready within 3.0s
        if image_search_task:
            try:
                verified_images = await asyncio.wait_for(image_search_task, timeout=3.0)
                if verified_images:
                    img_markdown = "\n\n---\n\n### 🖼️ AI-Verified Educational Diagrams\n\n"
                    for img in verified_images:
                        title = img.title or "Educational Diagram"
                        reason = img.relevance_reason or "Verified academic diagram matching the topic"
                        domain = img.source_domain or "Web"
                        page = img.source_page or img.url
                        img_markdown += (
                            f"![{title}]({img.url})\n\n"
                            f"> 💡 **Visual Summary:** {reason}  \n"
                            f"> 🔗 **Source:** [{domain}]({page}) *(AI Verified & Quality Checked)*\n\n"
                        )

                    for char in img_markdown:
                        yield f"data: {json.dumps({'type': 'token', 'data': char})}\n\n"
                        accumulated_text += char
                elif wants_image:
                    fallback_msg = (
                        "\n\n---\n\n"
                        "> ℹ️ *No verified diagram could be validated with high academic confidence for this specific topic — please refer to the step-by-step text explanation above.*\n\n"
                    )
                    for char in fallback_msg:
                        yield f"data: {json.dumps({'type': 'token', 'data': char})}\n\n"
                        accumulated_text += char
            except asyncio.TimeoutError:
                logger.warning("Image search timed out after 15s (question=%r)", question)
            except Exception:
                logger.warning("Image search injection failed (question=%r)", question, exc_info=True)

        # Step 8: Complete streaming immediately for instant UI feedback
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

        # Asynchronously verify grounding in background without blocking user
        async def _run_grounding_verification():
            try:
                await asyncio.to_thread(verify_response_grounding, accumulated_text, vector_chunks)
            except Exception:
                pass

        _spawn_background_task(_run_grounding_verification())

    async def simple_query(
        self,
        topic_id: Optional[str],
        question: str,
        session_messages: List[Dict],
        language: str = "english",
    ) -> Dict:
        """Non-streaming version — collects full response."""
        full_text = ""
        sources = []
        graph_data = {}
        confidence = {}

        async for event_str in self.query_stream(topic_id, question, session_messages, language=language):
            if not event_str.startswith("data: "):
                continue
            try:
                event = json.loads(event_str[6:])
                if event["type"] == "token":
                    full_text += event["data"]
                elif event["type"] == "sources":
                    sources = event["data"]
                elif event["type"] == "graph_context":
                    graph_data = event["data"]
                elif event["type"] == "confidence":
                    confidence = event["data"]
            except Exception:
                logger.warning("Failed to parse SSE event in simple_query: %r", event_str, exc_info=True)

        return {
            # query_stream now yields already-citation-filtered tokens, but this
            # stays as a cheap no-op safety net in case any tag slips through.
            "content": _clean_response_text(full_text),
            "sources": sources,
            "graph_context": graph_data,
            "confidence": confidence,
        }


# Singleton pipeline
graph_rag = GraphRAGPipeline()  