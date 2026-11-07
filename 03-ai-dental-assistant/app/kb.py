"""Knowledge base: Markdown files split into sections and searched with BM25.

No embeddings or extra API calls are needed, so search is free, instant and works offline.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

STOP = set("""a an and are as at be but by can do does for from has have how i if in is it its me my of on or our
so that the their them there they this to was we what when where which who why will with you your about
am any could would should please tell""".split())

SYNONYMS = {  # light query expansion for common patient wording
    "cost": ["price", "fee", "£"], "price": ["cost", "fee"], "how much": ["price", "£"],
    "open": ["opening", "hours"], "hours": ["opening"], "time": ["hours"],
    "where": ["address", "tube"], "location": ["address"], "park": ["parking"],
    "pain": ["emergency", "toothache"], "hurt": ["pain", "emergency"], "toothache": ["emergency", "pain"],
    "braces": ["aligners", "orthodontics"], "straighten": ["aligners"], "invisalign": ["aligners"],
    "kids": ["children", "child"], "son": ["children"], "daughter": ["children"], "baby": ["children"],
    "scared": ["nervous"], "anxious": ["nervous"], "afraid": ["nervous"],
    "pay": ["payment", "finance"], "instalments": ["finance"], "monthly": ["finance", "plan"],
    "nhs": ["private"], "book": ["booking", "appointment"], "cancel": ["cancellations"],
    "whiten": ["whitening"], "white": ["whitening"], "clean": ["hygiene", "scale"],
}


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9£]+", text.lower())
    out = []
    for w in words:
        if w in STOP:
            continue
        if len(w) > 4 and w.endswith("s"):
            w = w[:-1]
        out.append(w)
    return out


@dataclass
class Chunk:
    source: str      # file name
    title: str       # "Treatments and prices › Cosmetic"
    text: str

    @property
    def ref(self) -> str:
        return f"{self.source} › {self.title.split(' › ')[-1]}"


class KnowledgeBase:
    def __init__(self, folder: str | Path):
        self.folder = Path(folder)
        self.chunks: list[Chunk] = []
        self._tf: list[Counter] = []
        self._df: Counter = Counter()
        self._avg = 1.0
        self.reload()

    def reload(self) -> int:
        self.chunks = []
        for path in sorted(self.folder.glob("*.md")) + sorted(self.folder.glob("*.txt")):
            self.chunks.extend(split_markdown(path.read_text(encoding="utf-8"), path.name))
        self._tf = [Counter(tokenize(c.title + " " + c.text)) for c in self.chunks]
        self._df = Counter(t for tf in self._tf for t in tf)
        self._avg = sum(sum(tf.values()) for tf in self._tf) / max(1, len(self._tf))
        return len(self.chunks)

    def search(self, query: str, k: int = 4) -> list[Chunk]:
        q = tokenize(query)
        low = query.lower()
        for key, extra in SYNONYMS.items():
            if key in low:
                q += tokenize(" ".join(extra))
        if not q:
            return []
        n = len(self.chunks)
        scores = []
        for i, tf in enumerate(self._tf):
            length = sum(tf.values())
            s = 0.0
            for term in set(q):
                f = tf.get(term, 0)
                if not f:
                    continue
                idf = math.log(1 + (n - self._df[term] + 0.5) / (self._df[term] + 0.5))
                s += idf * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * length / self._avg))
            if s > 0:
                scores.append((s, i))
        scores.sort(reverse=True)
        return [self.chunks[i] for _, i in scores[:k]]


def split_markdown(text: str, source: str) -> list[Chunk]:
    """One chunk per '## ' section, prefixed with the document title."""
    doc_title = source
    m = re.search(r"^#\s+(.+)$", text, re.M)
    if m:
        doc_title = m.group(1).strip()
    parts = re.split(r"^##\s+", text, flags=re.M)
    chunks = []
    intro = re.sub(r"^#\s+.+$", "", parts[0], flags=re.M).strip()
    if intro:
        chunks.append(Chunk(source, doc_title, intro))
    for part in parts[1:]:
        heading, _, body = part.partition("\n")
        body = body.strip()
        if body:
            chunks.append(Chunk(source, f"{doc_title} › {heading.strip()}", body))
    return chunks
