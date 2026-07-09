"""
In-Trip Disruption agent skeleton

purpose: harness control loop end-to-enf with mock tools and stub reasoning

Checklist for later:
- real LLM reasoning
- real/live tools
- real payments
- persistence/scale 

Design invariants:
- constraint as design
- layer clarity: memory = runtime state (no prompt optimization)
- plan -> execute -> verify loop
"""

from __future__ import annotations
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
import contextlib, time


BASE = datetime(2026, 6, 10)
def t(hh, mm=0): return BASE.replace(hour=hh, minute=mm)
def hm(dt): return dt.strftime("%H:%M")


# =======================================================================
# 1. Memory (runtime stats) - three stores, three retrieval patterns
# =======================================================================

class SemanticMemory:
    def __init__(self):
        self.facts = {
            "traveller_id": "T-001",
            "dietary": "vegetarian",
            "min_connection_buffer_min": 30,
            "max_unapproved_cost_delta": 0,
            "language": "en",
        }

    def get(self, key):
        return self.facts.get(key)


class EpisodicMemory():
    def __init__(self):
        self.episodes = []

    def write(self, e):
        self.episodes.append(e)

class ProceduralMemory:
    def __init__(self):
        self.skills = {}

    def register(self, name, fn):
        self.skills[name] = fn

    def use(self, name, *a, **k):
        return self.skills[name](*a, **k)

# =======================================================================
# 2. DOMAIN MODEL + thin OTel-shaped tracker
# =======================================================================


@dataclass
class Item:
    kind: str; name: str; start: datetime; end: datetime
    ref: str; cost: int = 0; flexible: bool = False

@dataclass
class Trip:
    traveller_id: str
    items: list

@dataclass
class Disruption:
    item: Item
    kind: str
    delay_min: int
    new_end: datetime

@dataclass
class Action:
    desc: str
    tool: str
    financial: bool
    cost_delta: int=0
    apply: callable = None

# thin telemetry recorder. need to swap with OTel later
class Tracer:
    def __init__(self):
        self.spans = []
    @contextlib.contextmanager
    def span(self, name, **attrs):
        rec = {
            "name": name,
                "attrs": dict(attrs),
            }
        t0 = time.perf_counter()
        try:
            yield rec["attrs"]
        finally:
            rec["ms"] = round((time.perf_counter()- t0) * 1000, 2)
            self.spans.append(rec)


    

# =======================================================================
# 3. MOCK TOOLS - reads auto-callable; writes GATED by code
# =======================================================================

class ApprovalError(Exception): ...
def get_flight_status(ref): 
    return { 
        "ref": ref, 
        "delay_min": 180,
    }

def get_travel_time(a, b):
    return 30

def search_alternatives(k):
    slot = t(18, 0) + timedelta(days=1)
    catalog = {
        "activity": {
            "slot": slot,
            "cost": 2000,
        }
    }
    
    return catalog[k]

def rebook(ref, detail, approved=False):
    if not approved:
        raise ApprovalError(f"Rebook {ref} called without approval")
    return {
        "ref": ref,
        "status": "rebooked",
        "detail": detail   
    }

# ===========================================================================
# 4. SKILLS (procedural) — deterministic stubs; seams marked for LLM swap.
# ===========================================================================

def detect_disruption(trip, sem):
    for it in trip.items:
        if it.kind == "flight":
            s = get_flight_status(it.ref)
            if s["delay_min"] > 0:
                return Disruption(it, "delay", s["delay_min"],
                        it.end + timedelta(minutes=s["delay_min"]))
    return None

def diagnose_impact(trip, dz, sem):
    buf = timedelta(minutes=sem.get("min_connection_buffer_min"))
    arrival, affected, ok = dz.new_end, [], []
    for it in trip.items:
        if it.start <= dz.item.end:
            continue
        if it.flexible:
            ok.append((it, "flexible - absorbs delay"))
        elif it.start < arrival + buf: 
                affected.append((it, f"starts {hm(it.start)} < arrival {hm(arrival)} + buffer"))
        else:
            ok.append((it, "still reachable"))
    return {"arrival": arrival, "affected": affected, "ok": ok}


def replan(trip, dz, impact, sem):
    """
    This is the maker that turns the diagnosis into a patched itinerary +
    gated actions

    Returns(actions, proposed):
    actions: bookings we intend to make
    proposed: the full patched itinerary for the checker to verify
    """

    buffer_to_consider = timedelta(minutes=sem.get("min_connection_buffer_min")) # sem is from the semantic memory where we have specified min connection buffer
    arrival = dz.new_end
    affected = {it.name for it, _ in impact["affected"]}
