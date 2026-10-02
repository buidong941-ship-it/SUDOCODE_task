"""Orchestrator / Router: quyết định lượt này là việc gì (intent) + các cờ rủi ro. Ba backend cùng một giao diện:

- `jev`   : TypeSafe Jev (System One) — trả nhãn có kiểu + xác suất/độ tin cậy, không sinh văn bản. Mặc định.
- `llm`   : DeepSeek trả JSON (dự phòng khi không có Jev, và để so sánh Jev vs LLM trong báo cáo).
- `rules` : từ khóa, không gọi mạng — chỉ để kiểm thử pipeline / CI, KHÔNG dùng để báo cáo số liệu.

route() trả: {"intent", "confidence", "probabilities", "flags": {tên: xác suất}, "backend", "ms", "fallback"}
"""
import json
import re
import time

from core import log as cclog
from core.config import settings
from core.pii import Redactor
from harness.textnorm import fold

INTENTS = {
    "product_inquiry": "Khách hỏi tư vấn sản phẩm phù hợp, tính năng, so sánh mẫu, hoặc nói nhu cầu (diện tích phòng, ngân sách, có trẻ nhỏ).",
    "price_promo": "Khách hỏi giá, khuyến mãi, còn hàng không, phí ship, thời gian giao của một sản phẩm.",
    "policy_question": "Khách hỏi chính sách chung: đổi trả, bảo hành, vận chuyển, thanh toán, điều khoản khuyến mãi.",
    "place_order": "Khách đồng ý mua / bảo lên đơn / chốt đặt hàng / cung cấp địa chỉ để giao.",
    "order_change": "Khách đã mua và muốn đổi size, đổi màu, đổi sản phẩm, trả hàng hoặc sửa địa chỉ của đơn đã đặt.",
    "order_status": "Khách hỏi đơn hàng đã đặt đang ở đâu, bao giờ tới, mã đơn.",
    "callback": "Khách chưa quyết, hẹn gọi lại sau, cần hỏi người nhà, hoặc đang bận.",
    "negotiate": "Khách mặc cả, đòi giảm thêm, so giá bên khác, hỏi giá nhập hoặc giá vốn.",
    "out_of_scope": "Câu hỏi y tế/sức khỏe, pháp lý, hoặc yêu cầu gặp người thật / khiếu nại nghiêm trọng — cần chuyển nhân viên.",
    "meta": "Khách hỏi đang nói chuyện với người hay máy, hoặc yêu cầu xóa dữ liệu cá nhân.",
    "greeting_or_other": "Chào hỏi, nhắc lại cuộc gọi trước, cảm ơn, kết thúc, hoặc nội dung khác.",
}
FLAGS = {
    "agrees_to_buy": ("Khách đồng ý mua hoặc yêu cầu lên đơn ngay trong câu này.", "Khách chưa đồng ý mua."),
    "defers_decision": ("Khách trì hoãn: cần hỏi người nhà, cân nhắc thêm, hẹn gọi lại.", "Khách không trì hoãn."),
    "asks_if_bot": ("Khách hỏi đang nói chuyện với người thật hay máy/AI.", "Khách không hỏi điều đó."),
    "wants_data_deleted": ("Khách yêu cầu xóa dữ liệu/thông tin cá nhân của mình.", "Không có yêu cầu xóa dữ liệu."),
    "medical_question": ("Câu hỏi liên quan sức khỏe, thuốc, bệnh, an toàn y tế.", "Không liên quan y tế."),
    "asks_internal_cost": ("Khách hỏi giá nhập, giá vốn, lợi nhuận, nhà cung cấp.", "Không hỏi thông tin nội bộ."),
    "mentions_competitor": ("Khách nhắc giá hoặc cửa hàng của bên khác.", "Không nhắc bên khác."),
}


log = cclog.get("router")


class Router:
    def __init__(self, backend=None):
        self.backend = backend or settings.router_backend
        self._client = None

    def route(self, text, context):
        t0 = time.perf_counter()
        fallback = None
        try:
            if self.backend == "jev":
                out = self._jev(text, context)
            elif self.backend == "llm":
                out = self._llm(text, context)
            else:
                out = _rules(text)
        except Exception as e:                       # router lỗi → luật từ khóa, ghi lại để báo cáo
            fallback = f"{type(e).__name__}: {str(e)[:160]}"
            log.warning("router %s lỗi → dùng luật từ khóa: %s", self.backend, fallback)
            log.debug("router traceback", exc_info=True)
            out = _rules(text)
        if self.backend != "rules" and fallback is None and out["confidence"] < settings.router_min_confidence:
            rule = _rules(text)
            if rule["confidence"] >= 0.8:            # mô hình không chắc nhưng có tín hiệu từ khóa rõ → dùng luật
                fallback = f"low_confidence {out['intent']}:{out['confidence']:.2f}"
                log.warning("router %s không chắc (%s) → dùng luật: %s", self.backend, fallback, rule["intent"])
                out = {**rule, "flags": {**out["flags"], **{k: v for k, v in rule["flags"].items() if v >= 0.9}}}
        out.update(backend=self.backend, ms=int((time.perf_counter() - t0) * 1000), fallback=fallback)
        log.debug("router %s %dms intent=%s probs=%s usage=%s", self.backend, out["ms"], out["intent"],
                  out.get("probabilities"), out.get("usage"))
        return out

    # ------------------------------------------------------------------ Jev (TypeSafe System One)
    def _jev(self, text, context):
        from typesafe_sdk import Choice, Noul, TypeSafeClient
        if self._client is None:
            if not settings.typesafe_api_key:
                raise RuntimeError("TYPESAFE_API_KEY chưa đặt")
            self._client = TypeSafeClient(api_key=settings.typesafe_api_key, timeout=settings.jev_timeout_s,
                                          model=settings.jev_model, base_url=settings.jev_base_url)
        questions = {"intent": Choice(instructions="Ý định chính của câu khách vừa nói trong cuộc gọi bán hàng là gì?",
                                      criteria=INTENTS)}
        for name, (yes, no) in FLAGS.items():
            questions[name] = Noul(instructions=yes, criteria={"true": yes, "false": no})
        state = Redactor().redact({"customer_said": text, "recent_dialogue": context.get("recent", [])[-4:],
                                   "known_context": context.get("summary", "")})          # SĐT/địa chỉ không ra ngoài
        r = self._client.system_one(state=state, questions=questions, model=settings.jev_model)
        ch = r.choices["intent"]
        return {"intent": ch.choice, "confidence": float(ch.confidence), "probabilities": dict(ch.probabilities),
                "flags": {k: float(v.noul) for k, v in r.nouls.items()},
                "usage": {"input_tokens": r.usage.input_tokens, "output_tokens": r.usage.output_tokens}}

    # ------------------------------------------------------------------ LLM (DeepSeek JSON)
    def _llm(self, text, context):
        from core.llm.deepseek import DeepSeek
        text, context = Redactor().redact([text, {"recent": context.get("recent", [])}])   # SĐT/địa chỉ không ra ngoài
        prompt = ("Phân loại câu khách trong cuộc gọi bán hàng. Trả JSON {\"intent\": <một nhãn>, \"confidence\": 0..1, "
                  "\"flags\": {<cờ>: 0..1}}.\nNhãn intent:\n" + "\n".join(f"- {k}: {v}" for k, v in INTENTS.items())
                  + "\nCờ:\n" + "\n".join(f"- {k}: {v[0]}" for k, v in FLAGS.items())
                  + f"\n\nNgữ cảnh: {json.dumps(context.get('recent', [])[-4:], ensure_ascii=False)}\nCâu khách: {text}")
        d = DeepSeek().json(prompt)
        intent = d.get("intent") if d.get("intent") in INTENTS else "greeting_or_other"
        return {"intent": intent, "confidence": float(d.get("confidence", 0.5)), "probabilities": {},
                "flags": {k: float(d.get("flags", {}).get(k, 0)) for k in FLAGS}}


# ---------------------------------------------------------------------- luật từ khóa (kiểm thử / dự phòng)
_RULES = [
    ("meta", r"(nguoi that|nguoi hay may|robot|tro ly ao|may tra loi|xoa (du lieu|thong tin)|xoa het)"),
    ("out_of_scope", r"(khang sinh|thuoc (gi|nay|kia|tri)|uong thuoc|benh|bac si|tieu duong|cho con bu|mang thai|gap nguoi (phu trach|that|quan ly)|nguoi phu trach|khieu nai)"),
    ("policy_question", r"(phi doi|chinh sach|doi tra (trong|may|bao)|bao hanh (the nao|bao lau|may)|tra gop|dieu khoan|quy dinh)"),
    ("order_change", r"(doi len|doi sang|muon doi|lam thu tuc doi|doi (cho|giup)|chat qua|hoi chat|rong qua|hoi rong|tra hang|hoan tien|doi dia chi don)"),
    ("order_status", r"(don (hang )?(cua|den|toi)|bao gio (toi|den|giao)|ma don|trang thai don|van don|dang o dau)"),
    ("place_order", r"(len don|chot|dat (hang|luon)|lay (cai|mau|luon|size)|(chi|anh|em|co|chu|minh|ok|thoi) lay|mua luon|ok (em )?len|giao (cho|ve) cho cu|giao cho cu)"),
    ("negotiate", r"(giam (them|gia)|bot (cho|di)|ben kia|ben khac|shopee|lazada|re hon|gia nhap|gia von|gia goc)"),
    ("callback", r"(goi lai|hoi (chong|vo|ong xa|ba xa|nguoi nha|con)|can nhac|suy nghi|dang ban|de (chi|anh|co|em) (hoi|xem|tinh))"),
    ("price_promo", r"(gia|bao nhieu|khuyen mai|km|giam|uu dai|con hang|het hang|ship|phi|bao lau|may ngay)"),
    ("product_inquiry", r"(may|mau|loai|phong|met vuong|m2|ngan sach|tre|be|size|tu van|phu hop|nen mua)"),
]
_FLAG_RULES = {
    "agrees_to_buy": r"(len don|chot|dat luon|mua luon|lay (cai|mau|luon|size)|(chi|anh|em|co|chu|minh|ok|thoi) lay)",
    "defers_decision": r"(de (chi|anh|co|em|minh) (hoi|tinh|xem|nghi)|hoi (chong|vo|ong xa|ba xa|nguoi nha)|can nhac|suy nghi|dang ban|bao lai|goi lai (cho|sau|em))",
    "asks_if_bot": r"(nguoi that|nguoi hay may|robot|tro ly ao|may tra loi)",
    "wants_data_deleted": r"(xoa (du lieu|thong tin|het|so))",
    "medical_question": r"(khang sinh|uong thuoc|thuoc (gi|nay|tri)|benh|bac si|tieu duong|cho con bu|mang thai|di ung)",
    "asks_internal_cost": r"(gia nhap|gia von|gia goc|nha cung cap|lai bao nhieu)",
    "mentions_competitor": r"(ben kia|ben khac|shopee|lazada|tiki|cho khac|cua hang khac)",
}


def _b(rx):
    return re.compile(r"\b(?:" + rx + r")\b")


_RULES = [(n, _b(rx)) for n, rx in _RULES]
_FLAG_RULES = {k: _b(rx) for k, rx in _FLAG_RULES.items()}


def _rules(text):
    f = fold(text)
    intent, conf = "greeting_or_other", 0.5
    for name, rx in _RULES:
        if re.search(rx, f):
            intent, conf = name, 0.85
            break
    flags = {k: (0.95 if re.search(rx, f) else 0.05) for k, rx in _FLAG_RULES.items()}
    return {"intent": intent, "confidence": conf, "probabilities": {}, "flags": flags}
