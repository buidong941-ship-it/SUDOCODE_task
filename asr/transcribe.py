#!/usr/bin/env python3
"""ASR local → asr/hypotheses.json (định dạng BTC) + bảng WER / CER / Entity Accuracy.

    # audio thật (đặt file D01.wav, D02.mp3 … vào asr/audio/; tên file = id hội thoại trong ground_truth.json)
    python asr/transcribe.py --audio-dir asr/audio --model small                       # faster-whisper, CPU được
    python asr/transcribe.py --audio-dir asr/audio --backend phowhisper --model vinai/PhoWhisper-small

    # kiểm thử hậu xử lý khi chưa có audio: lấy chính lời ground truth làm "đầu ra ASR"
    python asr/transcribe.py --from-ground-truth                  # dạng chữ → WER phải = 0, đo trần Entity Accuracy
    python asr/transcribe.py --from-ground-truth --as-digits      # giả lập ASR viết chữ số → kiểm to_spoken()

Pipeline: ASR (từ điển tên sản phẩm làm initial_prompt) → `itn()` (chữ → số: tiền, SĐT, ngày, mã đơn) → trích thực thể
→ `to_spoken()` đưa transcript về dạng chữ như ground truth để tính WER/CER (BTC: "nêu rõ chọn dạng nào" → dạng chữ).
Không có diarization (M2) nên không xuất `turns`.
"""
import argparse
import glob
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

from itn import entities, itn, to_spoken  # noqa: E402

AUDIO_EXT = (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm")
MONEY_KEYS = {"price_vnd", "budget_vnd", "competitor_price_vnd", "min_free_ship_vnd", "bulky_fee_vnd", "exchange_fee_vnd"}


def product_prompt():
    """Từ điển tên sản phẩm/thương hiệu cho Whisper (initial_prompt) — giảm lỗi kiểu "Xiao Mi", "e pia"."""
    from harness.tools import mt
    names = sorted({p["name"] for p in mt.PRODUCTS})
    return "Cuộc gọi tư vấn bán hàng. Sản phẩm: " + ", ".join(names)[:600] + ". Size, ship, COD, khuyến mãi."


def run_faster_whisper(paths, model_name, device, compute_type):
    from faster_whisper import WhisperModel
    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    prompt = product_prompt()
    for p in paths:
        t0 = time.time()
        segs, info = model.transcribe(p, language="vi", beam_size=5, vad_filter=True, initial_prompt=prompt)
        segs = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segs]
        yield p, segs, {"audio_s": round(info.duration, 1), "asr_s": round(time.time() - t0, 1)}


def run_phowhisper(paths, model_name, device):
    from transformers import pipeline
    asr = pipeline("automatic-speech-recognition", model=model_name, device=0 if device == "cuda" else -1)
    for p in paths:
        t0 = time.time()
        r = asr(p, chunk_length_s=30, return_timestamps=True, generate_kwargs={"language": "vi"})
        segs = [{"start": c["timestamp"][0], "end": c["timestamp"][1], "text": c["text"].strip()} for c in r.get("chunks", [])] \
            or [{"start": 0.0, "end": None, "text": r["text"].strip()}]
        yield p, segs, {"asr_s": round(time.time() - t0, 1)}


def from_ground_truth(gt, as_digits):
    for d in gt["dialogues"]:
        segs = [{"start": None, "end": None, "text": itn(t["text"]) if as_digits else t["text"]} for t in d["turns"]]
        yield d["id"], segs, {}


def build(segs, ref_date):
    raw = " ".join(s["text"] for s in segs)
    return {"text": to_spoken(raw), "text_itn": itn(raw), "entities": entities([s["text"] for s in segs], ref_date),
            "segments": segs}


def entity_breakdown(gt, hyp):
    """Độ chính xác thực thể tách riêng tiền / SĐT / còn lại (đề yêu cầu báo riêng số tiền và SĐT)."""
    acc = {"money": [0, 0], "phone": [0, 0], "other": [0, 0]}
    wrong = []
    for d in gt["dialogues"]:
        h = (hyp.get(d["id"]) or {}).get("entities", {})
        for k, v in d.get("entities", {}).items():
            g = "money" if k in MONEY_KEYS else "phone" if k == "phone" else "other"
            ok = str(h.get(k)) == str(v)
            acc[g][0] += ok; acc[g][1] += 1
            if not ok:
                wrong.append(f"{d['id']}.{k}: đúng={v!r} nhận={h.get(k)!r}")
    return {g: (round(100 * a / n, 1) if n else None, n) for g, (a, n) in acc.items()}, wrong


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audio-dir", default=os.path.join(HERE, "audio"))
    ap.add_argument("--ground-truth", default=os.path.join(HERE, "ground_truth.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "hypotheses.json"))
    ap.add_argument("--backend", choices=["faster-whisper", "phowhisper"], default="faster-whisper")
    ap.add_argument("--model", default="small", help="faster-whisper: tiny|base|small|medium|large-v3; phowhisper: vinai/PhoWhisper-*")
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    ap.add_argument("--compute-type", default="int8", help="faster-whisper: int8 (CPU) | float16 (GPU)")
    ap.add_argument("--from-ground-truth", action="store_true", help="không cần audio: dùng lời ground truth làm đầu ra ASR")
    ap.add_argument("--as-digits", action="store_true", help="với --from-ground-truth: giả lập ASR viết số bằng chữ số")
    a = ap.parse_args()

    gt = json.load(open(a.ground_truth, encoding="utf-8")) if os.path.exists(a.ground_truth) else None
    ref_date = (gt or {}).get("reference_date", time.strftime("%Y-%m-%d"))
    if a.from_ground_truth:
        source = from_ground_truth(gt, a.as_digits)
    else:
        paths = sorted(p for p in glob.glob(os.path.join(a.audio_dir, "*")) if p.lower().endswith(AUDIO_EXT))
        if not paths:
            sys.exit(f"không thấy file audio trong {a.audio_dir} (đuôi {', '.join(AUDIO_EXT)})")
        device = a.device
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"
        source = run_faster_whisper(paths, a.model, device, a.compute_type) if a.backend == "faster-whisper" \
            else run_phowhisper(paths, a.model, device)

    hyp, timing = {}, {}
    for key, segs, info in source:
        did = os.path.splitext(os.path.basename(key))[0]
        hyp[did] = build(segs, ref_date)
        timing[did] = info
        if info:
            print(f"{did}: {info}", file=sys.stderr)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(hyp, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(hyp)} hội thoại → {a.out}")
    if not gt:
        return
    # chấm bằng chính hàm của BTC (eval/reference_eval.py: wer_cer đọc ground_truth.json + hypotheses.json cùng thư mục)
    sys.path.insert(0, os.path.join(ROOT, "eval"))
    from reference_eval import wer_cer
    tmp = tempfile.mkdtemp()
    shutil.copy(a.ground_truth, os.path.join(tmp, "ground_truth.json")); shutil.copy(a.out, os.path.join(tmp, "hypotheses.json"))
    r = wer_cer(tmp)
    by, wrong = entity_breakdown(gt, hyp)
    print(f"WER {r['WER']}%  CER {r['CER']}%  Entity Accuracy {r['entity_accuracy']}% ({r['n_entities']} thực thể, "
          f"{r['n_dialogues']} hội thoại)  — sạch {r['wer_clean']} / nhiễu {r['wer_noisy']}")
    print("  theo loại: " + ", ".join(f"{g} {v}% (n={n})" for g, (v, n) in by.items() if n))
    for w in wrong:
        print("  sai:", w)
    if any(t.get("audio_s") for t in timing.values()):
        tot_a = sum(t.get("audio_s", 0) for t in timing.values()); tot_t = sum(t.get("asr_s", 0) for t in timing.values())
        print(f"  {tot_a:.0f}s audio xử lý trong {tot_t:.0f}s (RTF {tot_t / max(tot_a, 1):.2f})")


if __name__ == "__main__":
    main()
