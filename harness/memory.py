"""Bộ nhớ dài hạn (episodic + profile + báo giá) — SQLAlchemy Core, chạy trên SQLite (mặc định) hoặc PostgreSQL.

Mọi bảng có cột `ns` (namespace = <run_id>:<config>:<scenario_id>) để nhiều kịch bản / nhiều lần chạy dùng chung một DB
trên server mà không nhiễm chéo. Fact không bao giờ bị ghi đè: khách đổi ý → fact cũ `superseded`, trỏ sang fact mới.
"""
import json
import os
from datetime import date, timedelta

from sqlalchemy import (Column, Float, Integer, MetaData, String, Table, Text, and_, create_engine, insert, select,
                        update, delete)

from core.config import settings

meta = MetaData()

customers = Table("customers", meta,
                  Column("ns", String(160), primary_key=True), Column("customer_id", String(32), primary_key=True),
                  Column("name", String(80)), Column("honorific", String(16)), Column("phone", String(16)),
                  Column("status", String(24), default="active"))
identities = Table("identities", meta,
                   Column("ns", String(160), primary_key=True), Column("kind", String(16), primary_key=True),
                   Column("value", String(64), primary_key=True), Column("customer_id", String(32), primary_key=True))
sessions = Table("sessions", meta,
                 Column("ns", String(160), primary_key=True), Column("session_id", String(80), primary_key=True),
                 Column("customer_id", String(32)), Column("channel", String(24)), Column("started_on", String(10)),
                 Column("outcome", String(24)), Column("summary", Text), Column("blockers_json", Text),
                 Column("next_action", Text), Column("source", String(16), default="harness"))
turns = Table("turns", meta,
              Column("ns", String(160), primary_key=True), Column("session_id", String(80), primary_key=True),
              Column("turn", Integer, primary_key=True), Column("customer_text", Text), Column("agent_text", Text),
              Column("state_json", Text))
facts = Table("facts", meta,
              Column("fact_id", Integer, primary_key=True, autoincrement=True), Column("ns", String(160), index=True),
              Column("customer_id", String(32), index=True), Column("slot", String(48)), Column("value_json", Text),
              Column("confidence", Float), Column("source", String(64)), Column("session_id", String(80)),
              Column("valid_from", String(10)), Column("expires_on", String(10)), Column("superseded_by", Integer),
              Column("status", String(16), default="current"))
quotes = Table("quotes", meta,
               Column("quote_id", Integer, primary_key=True, autoincrement=True), Column("ns", String(160), index=True),
               Column("customer_id", String(32)), Column("session_id", String(80)), Column("sku", String(48)),
               Column("role", String(16)), Column("list_price_vnd", Integer), Column("final_price_vnd", Integer),
               Column("promo_code", String(32)), Column("promo_end", String(10)), Column("quoted_on", String(10)))

# TTL theo slot (ngày) — docs/ARCHITECTURE.md mục 3.1
TTL_DAYS = {"room_area_m2": 365, "has_children": 365, "household_size": 365, "budget_vnd": 90, "size": 180, "color": 180,
            "address": 180, "payment": 180, "product_advised": 60, "price_quoted_vnd": 30, "blocker": 30,
            "competitor_price_vnd": 30, "objection": 30, "callback_requested": 14}
_engine = None


def engine():
    global _engine
    if _engine is None:
        url = settings.database_url
        if url.startswith("sqlite:///"):
            os.makedirs(os.path.dirname(url[len("sqlite:///"):]) or ".", exist_ok=True)
        kw = {"connect_args": {"timeout": 30}} if url.startswith("sqlite") else {"pool_pre_ping": True}
        _engine = create_engine(url, future=True, **kw)
        meta.create_all(_engine)
    return _engine


class Memory:
    """Truy cập bộ nhớ trong một namespace. `read_enabled=False` = baseline (không nạp phiên trước, vẫn ghi)."""

    def __init__(self, ns, read_enabled=True):
        self.ns, self.read_enabled = ns, read_enabled
        self.e = engine()

    def wipe(self):
        with self.e.begin() as c:
            for t in (customers, identities, sessions, turns, facts, quotes):
                c.execute(delete(t).where(t.c.ns == self.ns))

    # ------------------------------------------------------------------ danh tính
    def upsert_customer(self, customer_id, name=None, honorific=None, phone=None, identities_=()):
        with self.e.begin() as c:
            row = c.execute(select(customers).where(and_(customers.c.ns == self.ns, customers.c.customer_id == customer_id))).first()
            if row is None:
                c.execute(insert(customers).values(ns=self.ns, customer_id=customer_id, name=name, honorific=honorific, phone=phone, status="active"))
            for kind, value in identities_:
                if value and not c.execute(select(identities).where(and_(identities.c.ns == self.ns, identities.c.kind == kind,
                                                                         identities.c.value == value, identities.c.customer_id == customer_id))).first():
                    c.execute(insert(identities).values(ns=self.ns, kind=kind, value=value, customer_id=customer_id))

    def lookup(self, kind, value):
        with self.e.connect() as c:
            return [r.customer_id for r in c.execute(select(identities.c.customer_id).where(
                and_(identities.c.ns == self.ns, identities.c.kind == kind, identities.c.value == value)))]

    def set_status(self, customer_id, status):
        with self.e.begin() as c:
            c.execute(update(customers).where(and_(customers.c.ns == self.ns, customers.c.customer_id == customer_id)).values(status=status))

    # ------------------------------------------------------------------ episodic
    def add_session(self, session_id, customer_id, channel, started_on, outcome=None, summary=None, blockers=(), next_action=None, source="harness"):
        with self.e.begin() as c:
            c.execute(delete(sessions).where(and_(sessions.c.ns == self.ns, sessions.c.session_id == session_id)))
            c.execute(insert(sessions).values(ns=self.ns, session_id=session_id, customer_id=customer_id, channel=channel,
                                              started_on=started_on, outcome=outcome, summary=summary,
                                              blockers_json=json.dumps(list(blockers), ensure_ascii=False), next_action=next_action, source=source))

    def past_sessions(self, customer_id, before_session=None):
        if not self.read_enabled:
            return []
        with self.e.connect() as c:
            rows = c.execute(select(sessions).where(and_(sessions.c.ns == self.ns, sessions.c.customer_id == customer_id))
                             .order_by(sessions.c.started_on)).mappings().all()
        return [dict(r) for r in rows if r["session_id"] != before_session]

    def log_turn(self, session_id, turn, customer_text, agent_text, state):
        with self.e.begin() as c:
            c.execute(insert(turns).values(ns=self.ns, session_id=session_id, turn=turn, customer_text=customer_text,
                                           agent_text=agent_text, state_json=json.dumps(state, ensure_ascii=False, default=str)))

    # ------------------------------------------------------------------ profile facts
    def current_facts(self, customer_id, today=None, include_expired=False):
        """{slot: {"value", "source", "fact_id", "expires_on", "expired"}} — chỉ fact `current`."""
        if not self.read_enabled:
            return {}
        with self.e.connect() as c:
            rows = c.execute(select(facts).where(and_(facts.c.ns == self.ns, facts.c.customer_id == customer_id,
                                                      facts.c.status == "current"))).mappings().all()
        out = {}
        for r in rows:
            expired = bool(today and r["expires_on"] and r["expires_on"] < today)
            if expired and not include_expired:
                continue
            out[r["slot"]] = {"value": json.loads(r["value_json"]), "source": r["source"], "fact_id": r["fact_id"],
                              "expires_on": r["expires_on"], "expired": expired, "session_id": r["session_id"]}
        return out

    def write_fact(self, customer_id, slot, value, source, session_id, today, confidence=1.0, valid_from=None):
        """set / supersede. Trả memory_write dict cho trace, hoặc None nếu không đổi gì."""
        with self.e.begin() as c:
            old = c.execute(select(facts).where(and_(facts.c.ns == self.ns, facts.c.customer_id == customer_id,
                                                     facts.c.slot == slot, facts.c.status == "current"))).mappings().first()
            if old is not None and json.loads(old["value_json"]) == value:
                return None
            valid_from = valid_from or today
            exp = (date.fromisoformat(valid_from) + timedelta(days=TTL_DAYS.get(slot, 90))).isoformat()
            fid = c.execute(insert(facts).values(ns=self.ns, customer_id=customer_id, slot=slot,
                                                 value_json=json.dumps(value, ensure_ascii=False), confidence=confidence,
                                                 source=source, session_id=session_id, valid_from=valid_from, expires_on=exp,
                                                 status="current")).inserted_primary_key[0]
            op = "set"
            if old is not None:
                c.execute(update(facts).where(facts.c.fact_id == old["fact_id"]).values(status="superseded", superseded_by=fid))
                op = "supersede"
        w = {"key": slot, "value": value, "op": op, "source": source, "customer_id": customer_id}
        if old is not None:
            w["previous"] = json.loads(old["value_json"])
        return w

    def status(self, customer_id):
        with self.e.connect() as c:
            r = c.execute(select(customers.c.status).where(and_(customers.c.ns == self.ns, customers.c.customer_id == customer_id))).first()
        return r[0] if r else None

    def forget_customer(self, customer_id):
        """Yêu cầu xóa dữ liệu: xóa fact, báo giá, phiên, lượt thoại; đánh dấu hồ sơ (giữ dấu vết yêu cầu xóa)."""
        with self.e.begin() as c:
            c.execute(delete(sessions).where(and_(sessions.c.ns == self.ns, sessions.c.customer_id == customer_id)))
            c.execute(delete(facts).where(and_(facts.c.ns == self.ns, facts.c.customer_id == customer_id)))
            c.execute(delete(quotes).where(and_(quotes.c.ns == self.ns, quotes.c.customer_id == customer_id)))
            c.execute(update(customers).where(and_(customers.c.ns == self.ns, customers.c.customer_id == customer_id)).values(status="deletion_requested"))

    # ------------------------------------------------------------------ báo giá
    def add_quote(self, customer_id, session_id, sku, role, list_price, final_price, promo_code, promo_end, quoted_on):
        with self.e.begin() as c:
            c.execute(insert(quotes).values(ns=self.ns, customer_id=customer_id, session_id=session_id, sku=sku, role=role,
                                            list_price_vnd=list_price, final_price_vnd=final_price, promo_code=promo_code,
                                            promo_end=promo_end, quoted_on=quoted_on))

    def past_quotes(self, customer_id):
        if not self.read_enabled:
            return []
        with self.e.connect() as c:
            return [dict(r) for r in c.execute(select(quotes).where(and_(quotes.c.ns == self.ns, quotes.c.customer_id == customer_id))
                                               .order_by(quotes.c.quote_id)).mappings().all()]

    def merge_customer(self, src, dst):
        """Identity resolution: hồ sơ tạm (vd khách chat Facebook chưa có trong CRM) được xác định là khách `dst` → gộp."""
        if src == dst:
            return
        with self.e.begin() as c:
            for t in (facts, quotes, sessions):
                c.execute(update(t).where(and_(t.c.ns == self.ns, t.c.customer_id == src)).values(customer_id=dst))
            for r in c.execute(select(identities).where(and_(identities.c.ns == self.ns, identities.c.customer_id == src))).all():
                if not c.execute(select(identities).where(and_(identities.c.ns == self.ns, identities.c.kind == r.kind,
                                                               identities.c.value == r.value, identities.c.customer_id == dst))).first():
                    c.execute(insert(identities).values(ns=self.ns, kind=r.kind, value=r.value, customer_id=dst))
            c.execute(delete(identities).where(and_(identities.c.ns == self.ns, identities.c.customer_id == src)))
            c.execute(update(customers).where(and_(customers.c.ns == self.ns, customers.c.customer_id == src)).values(status="merged"))
        # 2 fact `current` cùng slot sau khi gộp → giữ cái mới nhất
        with self.e.begin() as c:
            rows = c.execute(select(facts).where(and_(facts.c.ns == self.ns, facts.c.customer_id == dst, facts.c.status == "current"))
                             .order_by(facts.c.fact_id)).mappings().all()
            last = {}
            for r in rows:
                if r["slot"] in last:
                    c.execute(update(facts).where(facts.c.fact_id == last[r["slot"]]).values(status="superseded", superseded_by=r["fact_id"]))
                last[r["slot"]] = r["fact_id"]
