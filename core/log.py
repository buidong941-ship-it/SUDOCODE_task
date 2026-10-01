"""Log chạy harness — dùng `logging` chuẩn, tất cả logger nằm dưới tên "cc" (cc.run, cc.router, cc.llm).

- Màn hình (stderr): mặc định chỉ WARNING trở lên (router fallback, guardrail, lỗi API, traceback);
  `--verbose` thêm khối từng lượt (INFO).
- File `<out>.log`: mức `--log-level` / LOG_LEVEL (mặc định INFO). Mỗi tiến trình gom log của từng kịch bản
  vào bộ nhớ (`capture`) rồi tiến trình chính ghi lần lượt theo scenario_id → file không bị trộn khi `--workers > 1`.
- Mỗi dòng mang nhãn `[scenario call tN]` (đặt bằng `set_context`) để biết dòng log thuộc lượt nào.
- Không bao giờ log khóa API: chỉ log tên model, thời gian, token, mã lỗi.
"""
import logging
import sys
from contextlib import contextmanager

LOGGER = "cc"
FMT = "%(asctime)s %(levelname)-7s %(name)-9s %(tag)s %(message)s"
_tag = ""
# thư viện HTTP, chỉ bật mức INFO: "HTTP Request: POST … 200 OK" (httpx/httpx2), "Retrying request…" (openai),
# "POST … <- 200 in 210ms (request …)" (typesafe_sdk, đã che header bí mật). Không bật DEBUG của chúng (có header/body).
HTTP_LIBS = ("httpx", "httpx2", "openai", "typesafe_sdk")


def set_context(tag=""):
    global _tag
    _tag = f"[{tag}]" if tag else ""


class _TagFilter(logging.Filter):
    def filter(self, record):
        record.tag = _tag
        return True


class _ListHandler(logging.Handler):
    def __init__(self, level):
        super().__init__(level)
        self.lines = []

    def emit(self, record):
        try:
            self.lines.append(self.format(record))
        except Exception:
            self.handleError(record)


def get(name):
    return logging.getLogger(f"{LOGGER}.{name}")


def setup(file_level="INFO", verbose=False):
    """Gọi một lần ở mỗi tiến trình (idempotent). Trả mức log cho file."""
    root = logging.getLogger(LOGGER)
    level = logging.DEBUG if verbose else getattr(logging, str(file_level).upper(), logging.INFO)
    root.setLevel(min(level, logging.INFO if verbose else logging.WARNING))
    if not getattr(root, "_cc_ready", False):
        con = logging.StreamHandler(sys.stderr)
        con.setFormatter(logging.Formatter(FMT, "%H:%M:%S"))
        con.addFilter(_TagFilter())
        root.addHandler(con)
        root.propagate = False
        root._cc_ready = True
        root._cc_console = con
    root._cc_console.setLevel(logging.INFO if verbose else logging.WARNING)
    for lib in HTTP_LIBS:
        logging.getLogger(lib).setLevel(logging.INFO if level <= logging.DEBUG else logging.WARNING)
    return level


@contextmanager
def capture(level):
    """Gom mọi log (cc + thư viện HTTP) ở mức `level` trong khối with → list dòng."""
    h = _ListHandler(level)
    h.setFormatter(logging.Formatter(FMT, "%H:%M:%S"))
    h.addFilter(_TagFilter())
    root = logging.getLogger(LOGGER)
    root.setLevel(min(root.level, level))
    libs = [logging.getLogger(n) for n in HTTP_LIBS]
    for lg in [root] + libs:
        lg.addHandler(h)
    try:
        yield h.lines
    finally:
        for lg in [root] + libs:
            lg.removeHandler(h)
