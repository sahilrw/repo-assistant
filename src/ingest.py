"""Clone a GitHub repo, split its files into chunks, and store them in the vector store.

Each chunk keeps {path, start_line} metadata so answers can cite exact files.
"""

import os
import subprocess
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src import store

ALLOWED_EXTENSIONS = {
    ".py", ".js", ".ts", ".md", ".txt", ".go",
    ".java", ".rs", ".json", ".yaml", ".yml", ".c", ".cpp", ".h"
}

MAX_CHUNKS = 3000

def ingest_steps(repo_url: str):
    repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
    dest_dir = Path("repos") / repo_name

    yield f"$ ingest {repo_name}"
    yield "> resolving repository …"

    if not dest_dir.exists():
        os.makedirs("repos", exist_ok=True)
        yield "> cloning (shallow) …"
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(dest_dir)],
            check=True,
        )
        yield "+ repo.clone depth=1 ok"
    else:
        yield "+ repo.cache hit ok"

    yield "> scanning files …"
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)

    ids, texts, metadatas = [], [], []
    chunk_counter = 0

    for root, dirs, files in os.walk(dest_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]

        for file in files:
            file_path = Path(root) / file
            if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
                continue

            relative_path = str(file_path.relative_to(dest_dir))

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue

            if not content.strip():
                continue

            chunks = splitter.split_text(content)

            current_search_idx = 0
            for i, chunk_text in enumerate(chunks):
                start_offset = content.find(chunk_text, current_search_idx)
                if start_offset == -1:
                    start_offset = current_search_idx

                start_line = content[:start_offset].count("\n") + 1
                end_line = start_line + chunk_text.count("\n")
                current_search_idx = start_offset + len(chunk_text)

                ids.append(f"{relative_path}:{i}")
                texts.append(chunk_text)
                metadatas.append({"path": relative_path, "start_line": start_line, "end_line": end_line})
                chunk_counter += 1

    if chunk_counter > MAX_CHUNKS:
        ids = ids[:MAX_CHUNKS]
        texts = texts[:MAX_CHUNKS]
        metadatas = metadatas[:MAX_CHUNKS]
        yield f"+ files.split chunks={chunk_counter} (capped {MAX_CHUNKS}) ok"
        chunk_counter = MAX_CHUNKS
    else:
        yield f"+ files.split chunks={chunk_counter} ok"

    store.reset()

    if texts:
        for done, total in store.add_stream(ids, texts, metadatas):
            yield f"> embedding {done}/{total} …"
        yield f"+ index.upsert vectors={chunk_counter} ok"

    yield f"✓ ready · {chunk_counter} chunks · ask away"
    return chunk_counter

def ingest(repo_url: str) -> int:
    gen = ingest_steps(repo_url)
    count = 0
    try:
        while True:
            next(gen)
    except StopIteration as e:
        count = e.value if e.value is not None else 0
    return count
