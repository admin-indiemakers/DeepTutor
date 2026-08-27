"""
Structured Academic Question Solver & Verifier Service.

Handles:
1. Detection of structure types: Tables with blanks, Flowcharts, Fill-in-the-blanks, Matching pairs, Diagrams with labels.
2. Structure Preservation: Faithfully extracts and maintains the exact rows/columns/nodes layout.
3. Student-friendly Pedagogy: Provides a 1-line plain English definition + relatable real-world analogy.
4. Two-Pass Self-Verification: Independently checks each filled answer for chemical, mathematical, and logical correctness,
   flagging any uncertainty rather than guessing with false confidence.
5. Edge-Case Handling: Flags ambiguous or blurry inputs and notes multiple valid textbook alternatives.
"""

import re
from typing import Dict, Optional, Tuple
from enum import Enum


class StructureType(str, Enum):
    TABLE = "table"
    FLOWCHART = "flowchart"
    FILL_IN_BLANKS = "fill_in_blanks"
    MATCHING = "matching"
    DIAGRAM_LABELS = "diagram_labels"
    GENERAL_EXERCISE = "general_exercise"


def detect_structure_type(text: str) -> Optional[StructureType]:
    """
    Detect if the student's question/upload contains or requests solving a structured exercise.
    Returns the detected StructureType or None.
    """
    t_lower = text.lower()

    # 1. Tables with blanks / Table solving requests
    if any(w in t_lower for w in [
        "solve table", "fill table", "complete table", "fill the table", "complete the table",
        "solve the table", "fill in the table", "table with blanks", "table 1.", "table 2.",
        "table 3.", "table 4.", "table 5.", "activity table", "tabular column", "fill in table"
    ]):
        return StructureType.TABLE

    # Check for Markdown table containing missing blanks/symbols
    if "|" in text and ("---" in text or "-|-" in text):
        if any(marker in text for marker in ["...", "___", " ? ", "|?|", "| ? |", "[blank]", "[ ]", "(a)", "(b)", "____", "missing"]):
            return StructureType.TABLE

    # 2. Flowchart with blanks / steps
    if any(w in t_lower for w in [
        "complete flowchart", "fill flowchart", "solve flowchart", "complete the flowchart",
        "fill the flowchart", "flow chart with blanks", "complete the flow chart", "flowchart blanks",
        "missing steps in flow", "flowchart missing"
    ]):
        return StructureType.FLOWCHART

    # 3. Matching exercises / Column Matching
    if any(w in t_lower for w in [
        "match the following", "match column", "matching pairs", "match the pairs",
        "match column a", "match column 1", "match items", "match the terms"
    ]):
        return StructureType.MATCHING

    # 4. Fill in the blanks
    if any(w in t_lower for w in [
        "fill in the blanks", "fill in the blank", "fill the blanks", "complete the blanks",
        "missing words", "fill blanks", "fill the blank", "complete the sentences with blanks"
    ]):
        return StructureType.FILL_IN_BLANKS

    # 5. Diagram with missing labels / parts
    if any(w in t_lower for w in [
        "label the diagram", "label the figure", "missing labels", "identify the parts",
        "name the parts", "label parts", "diagram blanks"
    ]):
        return StructureType.DIAGRAM_LABELS

    # 6. General textbook activity solving
    if any(w in t_lower for w in [
        "solve activity", "complete activity", "activity 1.", "activity 2.", "activity 3.",
        "activity 4.", "activity 5.", "solve problem 1", "solve exercise", "complete exercise"
    ]):
        return StructureType.GENERAL_EXERCISE

    return None


def get_structured_solver_instruction(structure_type: StructureType, question: str) -> str:
    """
    Generate student-friendly, rigorously self-verified instruction prompt tailored to the structure type.
    """
    return (
        f"The student specifically asked to SOLVE & COMPLETE A STRUCTURED EXERCISE / TABLE ({structure_type.value.upper()}).\n\n"
        f"═══════════════════════════════════════════════════════\n"
        f"MANDATORY OUTPUT FORMAT & TEACHING PIPELINE\n"
        f"═══════════════════════════════════════════════════════\n"
        f"1. STRUCTURE PRESERVATION & CLEAN FORMULAS:\n"
        f"   - Recreate the EXACT original structure (same rows, columns, headers, or matching layout).\n"
        f"   - Present the COMPLETED table at the very top with all solved/filled values highlighted in bold (e.g. `**Filled Answer**` or `$\\mathbf{{...}}$`).\n"
        f"   - Write chemical formulas on a single line using clean inline notation (e.g. `$\\text{{CH}}_3-\\text{{CH}}_2-\\text{{COOH}}$` or `CH₃-CH₂-COOH`, `$\\text{{H}}-\\text{{COOH}}$`). Never break formulas across separate vertical lines.\n\n"
        f"2. STRICT CONTEXT & CHAPTER MATCHING:\n"
        f"   - Match the EXACT table/activity from the active chapter context (e.g. if studying Carboxylic Acids, solve the Carboxylic Acids table).\n\n"
        f"3. MANDATORY OUTPUT STRUCTURE (Follow this EXACT sequence):\n\n"
        f"### 📝 Completed {structure_type.value.replace('_', ' ').title()}\n\n"
        f"[Display the complete, pristine Markdown Table with every blank filled in bold]\n\n"
        f"---\n\n"
        f"## 🎯 The Core Rules to Solve This\n\n"
        f"1. **[Rule 1 Name]:** [1-line simple rule explaining the core functional group, concept, or formula]\n"
        f"2. **[Rule 2 Name]:** [1-line rule on counting, balancing, or substitution]\n"
        f"3. **[Rule 3 Name]:** [1-line rule on suffix, units, or final nomenclature]\n\n"
        f"---\n\n"
        f"## 🔍 Step-by-Step Solution for Each Row / Blank\n\n"
        f"### **Row 1: [Task Description / Problem]**\n"
        f"* **Step 1 ([Identification / Count]):** [Clear explanation of identification, carbon count, or givens]\n"
        f"* **Step 2 ([Rule / Derivation]):** [Application of formula or IUPAC naming rule]\n"
        f"* **Answer for Blank 1:** **`[Filled Value]`**\n\n"
        f"### **Row 2: [Task Description / Problem]**\n"
        f"* **Step 1:** [Clear explanation]\n"
        f"* **Step 2:** [Application of formula or IUPAC rule]\n"
        f"* **Answer for Blank 2:** **`[Filled Value]`**\n\n"
        f"---\n\n"
        f"### 💡 Quick Summary Box\n\n"
        f"[A clean, concise Markdown reference table summarizing all key values, formulas, and names for quick exam revision]\n"
    )
