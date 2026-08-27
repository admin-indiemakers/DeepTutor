import sys
from pathlib import Path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import asyncio
from app.rag.storage import active_vector_store
from app.rag.pipeline.embedder import embedding_pipeline

async def test_retrieval():
    print("=" * 60)
    print("TEST 1: Retrieving Fig. 2.5 (a) in phys-10-2 (Lenses)")
    print("=" * 60)
    emb_fig = await embedding_pipeline.embed_batch(["explain Fig. 2.5 (a) convex and concave lens formation"])
    res_fig = active_vector_store.search("phys-10-2", emb_fig[0], top_k=2)
    for i, r in enumerate(res_fig):
        print(f"Match {i+1} [Score: {r['score']}]:")
        print(r['text'][:350] + "...\n")

    print("=" * 60)
    print("TEST 2: Retrieving Table 1.2 in chem-10-2 (Carboxylic Acids)")
    print("=" * 60)
    emb_tab = await embedding_pipeline.embed_batch(["solve Table 1.2 carboxylic acids IUPAC name"])
    res_tab = active_vector_store.search("chem-10-2", emb_tab[0], top_k=2)
    for i, r in enumerate(res_tab):
        print(f"Match {i+1} [Score: {r['score']}]:")
        print(r['text'][:350] + "...\n")

if __name__ == "__main__":
    asyncio.run(test_retrieval())
