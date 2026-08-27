"""
One-shot script to delete all textbook chapter namespaces from Pinecone
before running a full VLM re-ingestion.
"""
import sys
from pathlib import Path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.rag.storage import active_vector_store

NAMESPACES_TO_DELETE = [
    # Physics chapters
    "phys-10-1", "phys-10-2", "phys-10-3", "phys-10-4",
    "sslc-physics",
    # Chemistry chapters
    "chem-10-1", "chem-10-2", "chem-10-3", "chem-10-4",
    "sslc-chemistry",
    # Maths chapters
    "math-10-1", "math-10-2", "math-10-3", "math-10-4",
    "math-10-5", "math-10-6", "math-10-7",
    "sslc-math",
]

print("=" * 60)
print("Clearing Pinecone 'textbook' index namespaces...")
print("=" * 60)

for ns in NAMESPACES_TO_DELETE:
    try:
        active_vector_store.delete_topic(ns)
        print(f"  [OK] Deleted namespace: {ns}")
    except Exception as e:
        print(f"  [WARN] Could not delete {ns}: {e}")

print("\n[DONE] All textbook namespaces cleared from Pinecone.")
print("Run: python scripts/ingest_textbooks_vlm.py --subject all --concurrency 5 --dpi 180")

