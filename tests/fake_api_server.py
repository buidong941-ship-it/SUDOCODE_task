#!/usr/bin/env python3
"""Server giả lập API Jev (POST /v1/systemone) và DeepSeek (POST /chat/completions, SSE) để kiểm thử tích hợp khi không có mạng/khóa.

Server KIỂM TRA ĐỊNH DẠNG request (đúng như SDK/OpenAI gửi) rồi trả response đúng schema:
- Jev: answers = {name: {type: choice, choice, confidence, probabilities} | {type: noul, noul}}, model, usage.
- DeepSeek: stream "data: {...choices[0].delta.content...}" + usage, hoặc JSON mode.
Nội dung trả lời lấy từ luật/câu mẫu offline — chỉ để kiểm tra đường ống, KHÔNG phải chất lượng model.

    python tests/fake_api_server.py 8765
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.llm.generator import render_offline  # noqa: E402
from core.llm.router import _rules  # noqa: E402

SEEN = {"systemone": 0, "chat": 0}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path == "/stats":
            return self._json(200, SEEN)
        self._json(404, {})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or len(auth) < 12:
            return self._json(401, {"detail": "missing bearer key"})
        if self.path.rstrip("/").endswith("/v1/systemone"):
            return self.systemone(body)
        if self.path.rstrip("/").endswith("/chat/completions"):
            return self.chat(body)
        self._json(404, {"detail": "unknown path " + self.path})

    def systemone(self, body):
        errs = [k for k in ("model", "state", "questions") if k not in body]
        qs = body.get("questions") or {}
        for name, q in qs.items():
            if q.get("type") not in ("choice", "noul", "score"):
                errs.append(f"{name}.type")
            if q["type"] == "choice" and not isinstance(q.get("criteria"), dict):
                errs.append(f"{name}.criteria")
        if errs:
            return self._json(422, {"detail": [{"loc": ["body", e], "msg": "invalid"} for e in errs]})
        SEEN["systemone"] += 1
        said = (body["state"] or {}).get("customer_said", "") if isinstance(body["state"], dict) else str(body["state"])
        r = _rules(said)
        answers = {}
        for name, q in qs.items():
            if q["type"] == "choice":
                labels = list(q["criteria"])
                pick = r["intent"] if r["intent"] in labels else labels[0]
                probs = {l: (0.82 if l == pick else 0.18 / max(1, len(labels) - 1)) for l in labels}
                answers[name] = {"type": "choice", "choice": pick, "confidence": 0.82, "probabilities": probs}
            elif q["type"] == "noul":
                answers[name] = {"type": "noul", "noul": r["flags"].get(name, 0.1)}
        self._json(200, {"model": body["model"], "usage": {"input_tokens": 120, "output_tokens": len(answers)}, "answers": answers})

    def chat(self, body):
        if not body.get("model") or not isinstance(body.get("messages"), list):
            return self._json(422, {"error": "model/messages"})
        SEEN["chat"] += 1
        user = body["messages"][-1]["content"]
        if (body.get("response_format") or {}).get("type") == "json_object":
            content = json.dumps({"intent": "greeting_or_other", "confidence": 0.5, "flags": {}})
            return self._json(200, {"id": "x", "object": "chat.completion", "created": 0, "model": body["model"],
                                    "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})
        try:
            plan = json.loads(user.split("\n", 1)[1].rsplit("\n\nViết câu trả lời", 1)[0])
            text = render_offline(plan)
        except Exception:
            text = "Dạ vâng ạ."
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        for i in range(0, len(text), 12):
            ch = {"id": "x", "object": "chat.completion.chunk", "created": 0, "model": body["model"],
                  "choices": [{"index": 0, "delta": {"content": text[i:i + 12]}, "finish_reason": None}]}
            self.wfile.write(f"data: {json.dumps(ch, ensure_ascii=False)}\n\n".encode())
        end = {"id": "x", "object": "chat.completion.chunk", "created": 0, "model": body["model"], "choices": [],
               "usage": {"prompt_tokens": 300, "completion_tokens": len(text) // 3, "total_tokens": 300 + len(text) // 3}}
        self.wfile.write(f"data: {json.dumps(end)}\n\ndata: [DONE]\n\n".encode())


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
