"""Exercise every backend endpoint against a throwaway database.

Not a mock: it starts the real app, writes real rows, uploads a real image and
reads them back. If this passes, the backend works.
"""
import io, os, sys, tempfile
sys.stdout.reconfigure(encoding="utf-8")

# a scratch database, so running the tests never touches the district's data
TMP = tempfile.mkdtemp(prefix="pravaah_test_")
os.environ["PRAVAAH_DB"] = os.path.join(TMP, "test.sqlite")
sys.path.insert(0, ".")

from fastapi.testclient import TestClient
from pravaah import store
store.PHOTOS = os.path.join(TMP, "photos")
import api
api.store.PHOTOS = store.PHOTOS
c = TestClient(api.app)

ok = fail = 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1; print(f"  pass  {name}")
    else:
        fail += 1; print(f"  FAIL  {name}  {extra}")


PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
       b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
       b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

print("READ ENDPOINTS")
r = c.get("/api/health")
check("health 200", r.status_code == 200, r.text[:120])
check("health lists events", set(r.json()["events"]) >= {"patna", "delhi"})

r = c.get("/api/events")
check("events listed", r.status_code == 200 and len(r.json()) >= 2)

r = c.get("/api/reference")
check("reference has kinds", "water_depth" in r.json()["report_kinds"])

r = c.get("/api/national")
if r.status_code == 200:
    j = r.json()
    check("national counts add up",
          j["counts"]["total"] == sum(j["counts"][k] for k in
              ("above_danger", "above_warning", "normal", "not_reporting")),
          str(j["counts"]))
    check("above-danger endpoint", c.get("/api/national/above-danger").status_code == 200)
else:
    check("national absent is a clean 404", r.status_code == 404, r.text[:80])

r = c.get("/api/events/patna/plan")
check("plan 200", r.status_code == 200, r.text[:120])
if r.status_code == 200:
    p = r.json()
    check("plan arithmetic closes on people_planned",
          p["placed"] + p["beyond_reach"] + p["no_route"] == p["people_planned"],
          f'{p["placed"]}+{p["beyond_reach"]}+{p["no_route"]} != {p["people_planned"]}')
    check("the two totals are named apart and differ by the unplanned remainder",
          p["people_wet"] is None
          or p["people_wet"] - p["people_planned"] == p["not_planned"],
          f'{p["people_wet"]} - {p["people_planned"]} != {p["not_planned"]}')

r = c.get("/api/events/patna/units")
check("units listed", r.status_code == 200 and len(r.json()) > 0)
place = r.json()[0]["place"] if r.status_code == 200 and r.json() else None

if place:
    r = c.get(f"/api/events/patna/units/{place}")
    check("one unit resolves", r.status_code == 200 and "roads_near" in r.json())
    check("unit lookup is case-insensitive",
          c.get(f"/api/events/patna/units/{place.lower()}").status_code == 200)

r = c.get("/api/events/patna/shelters")
check("shelters carry capacity basis", r.status_code == 200 and "3.5" in r.json()["basis"])

print("\nERROR HANDLING")
check("unknown event is 404", c.get("/api/events/nowhere/plan").status_code == 404)
check("unknown unit is 404",
      c.get("/api/events/patna/units/Atlantis").status_code == 404)

print("\nWRITE: citizen reports")
r = c.post("/api/reports", data=dict(event="patna", kind="water_depth",
                                     place="Biddupur", lat=25.6, lon=85.2,
                                     depth_cm=45, note="knee deep at the gate"))
check("report accepted", r.status_code == 201, r.text[:140])
rid = r.json()["id"] if r.status_code == 201 else None

check("bad kind refused",
      c.post("/api/reports", data=dict(event="patna", kind="banana")).status_code == 422)
check("absurd depth refused",
      c.post("/api/reports", data=dict(event="patna", kind="water_depth",
                                       depth_cm=99999)).status_code == 422)
check("report on unknown event refused",
      c.post("/api/reports", data=dict(event="nowhere", kind="other")).status_code == 404)

r = c.post("/api/reports", files={"photo": ("x.png", PNG, "image/png")},
           data=dict(event="patna", kind="road_blocked", place="Fatuha"))
check("report with photo accepted", r.status_code == 201, r.text[:140])
pid = r.json()["id"] if r.status_code == 201 else None
check("photo stored", r.status_code == 201 and r.json()["photo"])
if pid:
    check("photo served back", c.get(f"/api/reports/{pid}/photo").status_code == 200)

check("wrong file type refused",
      c.post("/api/reports", files={"photo": ("x.exe", b"MZ", "application/x-msdownload")},
             data=dict(event="patna", kind="other")).status_code == 415)

r = c.get("/api/reports", params=dict(event="patna"))
check("reports listed", r.status_code == 200 and len(r.json()) >= 2)
check("filter by kind works",
      len(c.get("/api/reports", params=dict(kind="road_blocked")).json()) >= 1)

if rid:
    check("resolve works", c.post(f"/api/reports/{rid}/resolve").status_code == 200)
    check("resolving twice is a 404", c.post(f"/api/reports/{rid}/resolve").status_code == 404)
    check("resolved leaves the new queue",
          all(x["id"] != rid for x in c.get("/api/reports", params=dict(status="new")).json()))

print("\nWRITE: help requests")
ids = []
for people, mob in ((2, "walking"), (1, "stretcher"), (6, "needs_help")):
    r = c.post("/api/help", data=dict(event="patna", place="Biddupur",
                                      people=people, mobility=mob,
                                      contact="9876543210"))
    check(f"help accepted ({mob})", r.status_code == 201, r.text[:120])
    if r.status_code == 201:
        ids.append(r.json()["id"])

check("bad mobility refused",
      c.post("/api/help", data=dict(event="patna", mobility="teleport")).status_code == 422)
check("absurd group size refused",
      c.post("/api/help", data=dict(event="patna", people=9999)).status_code == 422)

q = c.get("/api/help", params=dict(event="patna")).json()
check("queue puts the least mobile first",
      q and q[0]["mobility"] == "stretcher", str([x["mobility"] for x in q]))
check("phone number is not stored in the clear",
      all("9876543210" not in str(x.get("contact")) for x in q))

if ids:
    check("assign works",
          c.post(f"/api/help/{ids[0]}/assign", data=dict(team="Boat 3",
                 eta="20:30")).status_code == 200)
    check("assigning twice is a 404",
          c.post(f"/api/help/{ids[0]}/assign", data=dict(team="Boat 4")).status_code == 404)
    check("close works", c.post(f"/api/help/{ids[0]}/close").status_code == 200)

print("\nWRITE: officer decisions")
r = c.post("/api/decisions", data=dict(event="patna", action="Open shelters",
                                       decision="approved", probability=0.22,
                                       threshold=0.02, officer="DM Patna"))
check("approval logged", r.status_code == 201, r.text[:120])
check("override without a reason refused",
      c.post("/api/decisions", data=dict(event="patna", action="Evacuate",
                                         decision="overridden")).status_code == 422)
r = c.post("/api/decisions", data=dict(event="patna", action="Evacuate",
                                       decision="overridden", reason="1"))
check("override with a reason accepted", r.status_code == 201)
d = c.get("/api/decisions", params=dict(event="patna")).json()
check("reason code expanded to text",
      any(x["reason"] == "resources unavailable" for x in d), str(d[:1]))
check("bad decision word refused",
      c.post("/api/decisions", data=dict(event="patna", action="x",
                                         decision="maybe")).status_code == 422)

print("\nPERSISTENCE")
s = c.get("/api/health").json()["store"]
check("health reflects what was written",
      s["reports_total"] >= 2 and s["decisions"] >= 2, str(s))

print()
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
