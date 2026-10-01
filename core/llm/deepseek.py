"""DeepSeek (API tương thích OpenAI) — sinh lời thoại tiếng Việt, có streaming để đo TTFT."""
import json
import time

from core.config import settings


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
        t1 = time.perf_counter()
        return "".join(parts).strip(), int(((ttft or t1) - t0) * 1000), int((t1 - t0) * 1000), usage

    def json(self, prompt, max_tokens=300):
        r = self.c.chat.completions.create(model=settings.deepseek_model, temperature=0,
                                           max_tokens=max_tokens, response_format={"type": "json_object"},
                                           messages=[{"role": "system", "content": "Chỉ trả về JSON hợp lệ."},
                                                     {"role": "user", "content": prompt}])
        return json.loads(r.choices[0].message.content or "{}")
