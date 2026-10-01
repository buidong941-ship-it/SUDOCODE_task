"""Tra cứu chính sách (tạm thời: so khớp từ khóa trên chunk [XX-nn] của policy/).

Bước RAG vector (bge-m3 + pgvector/Chroma) sẽ thay hàm search() với cùng giao diện. Đã áp sẵn 2 luật an toàn:
- loại tài liệu HẾT HIỆU LỰC (chỉ dùng khi hỏi về đơn cũ — xử lý sau) và tài liệu nhiễu (nội quy nhân viên);
- tài liệu NỘI BỘ (`restricted`) không bao giờ trả cho LLM sinh lời.
"""
import glob
import math
import os
import re
from collections import Counter

from core.config import settings
from harness.textnorm import fold

EXCLUDE = ("HET-HIEU-LUC", "NOI-BO", "noi-quy-nhan-vien")
STOP = set("a anh chi em minh co khong la cua cho va thi o nhe a da duoc bao nhieu the nao gi nao ben vay roi".split())


def _chunks():
    out = []
    for f in sorted(glob.glob(os.path.join(settings.btc_dir, "policy", "*.md"))):
        doc = os.path.basename(f)
        txt = open(f, encoding="utf-8").read()
        for m in re.finditer(r"^## \[([A-Z]+(?:-OLD)?-\d+)\]\s*(.*?)\n(.*?)(?=^## \[|\Z)", txt, re.S | re.M):
            out.append({"chunk_id": m.group(1), "doc": doc, "title": m.group(2).strip(), "text": m.group(3).strip(),
                        "restricted": "NOI-BO" in doc, "excluded": any(x in doc for x in EXCLUDE)})
    return out


CHUNKS = _chunks()


def _toks(s):
    return [w for w in re.findall(r"[a-z0-9]+", fold(s)) if w not in STOP and len(w) > 1]


_DF = Counter(w for c in CHUNKS for w in set(_toks(c["title"] + " " + c["text"])))


def search(query, k=3, include_restricted=False):
    q = _toks(query)
    scored = []
    for c in CHUNKS:
        if c["excluded"] and not (include_restricted and c["restricted"]):
            continue
        toks = Counter(_toks(c["title"] + " " + c["title"] + " " + c["text"]))
        score = sum(toks[w] / (1 + toks[w]) * math.log(1 + len(CHUNKS) / (1 + _DF[w])) for w in set(q) if w in toks)
        if score > 0:
            scored.append((score, c))
    scored.sort(key=lambda x: -x[0])
    return [dict(c, score=round(s, 3)) for s, c in scored[:k]]
