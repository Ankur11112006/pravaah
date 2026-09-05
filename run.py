"""The whole system for one event, in order, on one command.

    .venv/Scripts/python.exe run.py patna

Each stage is a real script you can run on its own; this only sequences them and
stops at the first failure rather than carrying a broken input downstream.
"""
import os, subprocess, sys, time
sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, ".")
EV = sys.argv[1] if len(sys.argv) > 1 else "patna"
RUN_DATE = sys.argv[2] if len(sys.argv) > 2 else None      # C-Flood run to use

# The depth frame the downstream stages plan on. Patna and Delhi have one named
# peak each; a C-Flood event has a frame every three hours, so take the wettest
# published by the run rather than hardcoding an hour that may not exist.
PEAK = {"patna": "2019-09-30", "delhi": "2023-07-16"}.get(EV)
DEPTH = f"out/depth/{EV}_{PEAK}.tif" if PEAK else None


def wettest_frame():
    import numpy as _np
    f = f"out/{EV}_frames.npy"
    if not os.path.exists(f):
        sys.exit(f"{f} is missing; run build_hazard.py {EV} first so there are "
                 f"frames to choose from.")
    rows = _np.load(f, allow_pickle=True)
    best = max(rows, key=lambda r: float(r[3]))
    print(f"  planning on the wettest of {len(rows)} frames: "
          f"{best[0]} {int(best[1]):02d}:00, {float(best[3]):.0f} km2 wet")
    return str(best[2])

if DEPTH is None:
    # a C-Flood event: the hazard stage has to run before we can pick a frame
    r0 = subprocess.run([sys.executable, "build_hazard.py", EV]
                        + ([RUN_DATE] if RUN_DATE else []),
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace")
    print(chr(10).join(r0.stdout.splitlines()))
    if r0.returncode:
        print(r0.stderr[-1200:]); sys.exit(1)
    DEPTH = wettest_frame()
    HAZARD_DONE = True
else:
    HAZARD_DONE = False

STAGES = [
    ("HAZARD    river discharge to a water level, calibrated on satellite extent",
     ["build_hazard.py", EV]),
    ("NETWORK   road graph carrying terrain, and when each road changes mode",
     ["build_timeline.py", EV]),
    ("EXPOSURE  who and how many are standing in the water",
     ["exposure.py", EV, DEPTH]),
    ("ROUTES    who can still reach a shelter, and who depends on a bridge",
     ["build_plan.py", EV] + ([DEPTH] if DEPTH else [])),
    ("ALLOCATE  min-cost flow to shelters of measured capacity",
     ["allocate.py", EV, DEPTH]),
    ("ALERT     cost-loss trigger, CAP 1.2 XML and SMS",
     ["alert.py", EV, DEPTH]),
]

NOISE = ("UserWarning", "warnings.warn", "c = b.geometry", "self.errors")
t0 = time.time()
MODE = __import__("pravaah.config", fromlist=["x"]).EVENTS[EV].hazard
for stage in STAGES:
    title, cmd = stage[0], stage[1]
    if HAZARD_DONE and cmd[0] == "build_hazard.py":
        continue                      # already run above, to pick the frame
    if len(stage) > 2 and stage[2] != MODE:
        print("\n" + "=" * 78)
        print(title)
        print("=" * 78)
        print(f"  SKIPPED: needs hazard mode '{stage[2]}', this event is '{MODE}'.")
        continue
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)
    r = subprocess.run([sys.executable] + cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    print("\n".join(l for l in r.stdout.splitlines()
                    if not any(n in l for n in NOISE)))
    if r.returncode:
        print("FAILED:", " ".join(cmd))
        print(r.stderr[-1200:])
        sys.exit(1)

print("\n" + "=" * 78)
print(f"{EV} complete in {time.time() - t0:.0f}s")
print("now rebuild the pages:  python build_map_data.py && python build_dashboard.py "
      f"{EV} && python build_standalone.py")
