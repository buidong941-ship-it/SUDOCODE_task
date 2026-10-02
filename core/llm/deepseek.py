"""DeepSeek (API tương thích OpenAI) — sinh lời thoại tiếng Việt, có streaming để đo TTFT."""
import json
import time

from core import log as cclog
from core.config import settings

log = cclog.get("llm")


class DeepSeek:
    _client = None

    def __init__(self):
        if DeepSeek._client is None:
            from openai import OpenAI
            if not settings.deepseek_api_key:
                raise RuntimeError("DEEPSEEK_API_KEY chưa đặt")
            DeepSeek._client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url,
                                      timeout=settings.llm_timeout_s, max_retries=1)
        self.c = DeepSeek._client

    def chat(self, messages, max_tokens=None, temperature=None):
        """Trả (text, ttft_ms, total_ms, usage). Streaming: TTFT = token đầu tiên."""
        t0 = time.perf_counter(); ttft = None; parts = []; usage = None
        log.debug("deepseek.chat model=%s prompt=%s", settings.deepseek_model,
                  json.dumps(messages, ensure_ascii=False)[:2000])
        try:
            stream = self.c.chat.completions.create(model=settings.deepseek_model, messages=messages, stream=True,
                                                    temperature=settings.llm_temperature if temperature is None else temperature,
                                                    max_tokens=max_tokens or settings.llm_max_tokens,
                                                    stream_options={"include_usage": True})
            for chunk in stream:
                if getattr(chunk, "usage", None):
                    usage = {"prompt_tokens": chunk.usage.prompt_tokens, "completion_tokens": chunk.usage.completion_tokens}
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content or ""
                if delta and ttft is None:
                    ttft = time.perf_counter()
                parts.append(delta)
        except Exception as e:
            log.error("deepseek.chat lỗi sau %dms: %s", (time.perf_counter() - t0) * 1000, _api_error(e))
            raise
        t1 = time.perf_counter()
        log.debug("deepseek.chat %dms ttft=%dms usage=%s", (t1 - t0) * 1000, ((ttft or t1) - t0) * 1000, usage)
        return "".join(parts).strip(), int(((ttft or t1) - t0) * 1000), int((t1 - t0) * 1000), usage

    def json(self, prompt, max_tokens=300):
        t0 = time.perf_counter()
        try:
            r = self.c.chat.completions.create(model=settings.deepseek_model, temperature=0,
                                               max_tokens=max_tokens, response_format={"type": "json_object"},
                                               messages=[{"role": "system", "content": "Chỉ trả về JSON hợp lệ."},
                                                         {"role": "user", "content": prompt}])
            out = r.choices[0].message.content or "{}"
            log.debug("deepseek.json %dms → %s", (time.perf_counter() - t0) * 1000, out[:500])
            return json.loads(out)
        except Exception as e:
            log.error("deepseek.json lỗi sau %dms: %s", (time.perf_counter() - t0) * 1000, _api_error(e))
            raise


def _api_error(e):
    """Tên lỗi + HTTP status + thông điệp ngắn (không kèm header/khóa)."""
    status = getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", None)
    return f"{type(e).__name__}" + (f" HTTP {status}" if status else "") + f": {str(e)[:300]}"
