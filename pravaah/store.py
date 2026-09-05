"""Everything the system needs to remember.

SQLite, because the alternative is asking a district to run a database server.
One file, no daemon, ships with Python, and it survives a power cut better than
anything that needs a service to be up.

Three tables, and each exists because a real gap was found:
  reports   citizens can tell the system what it cannot see. This is the only
            route by which urban pluvial flooding, which no satellite and no
            gauge detects, ever reaches the plan.
  help      "I cannot leave" is a different request from "there is water here",
            and it needs a different queue and a different answer.
  decisions the design always said every officer approval and override is
            logged with a reason. Until now that log lived in a browser tab.
"""
import hashlib, hmac, json, os, secrets, sqlite3, time
import datetime as dt

DB = os.environ.get("PRAVAAH_DB", "data/pravaah.sqlite")
PHOTOS = "data/photos"
CONTACT_KEY = os.environ.get("PRAVAAH_CONTACT_KEY_FILE", "data/.contact_key")


def _contact_key():
    """A secret this district keeps, used to scramble phone numbers.

    A plain hash of a phone number is not protection. There are about a billion
    of them in India, so anybody holding the database can hash every possible
    number in seconds and read the column straight back. With a secret mixed in
    they cannot, unless they also steal this file, and this file is the one
    thing that must never be copied along with the database.
    """
    # On a hosted box there is no persistent disk to keep a file on, and a key
    # regenerated on every restart stops recognising the repeat callers it
    # exists to recognise. An env var survives the restart; a file is still the
    # right answer on a district laptop, so the file wins when it is there.
    env = os.environ.get("PRAVAAH_CONTACT_KEY")
    if env:
        return env.strip().encode()
    if os.path.exists(CONTACT_KEY):
        return open(CONTACT_KEY, "rb").read().strip()
    os.makedirs(os.path.dirname(CONTACT_KEY) or ".", exist_ok=True)
    k = secrets.token_bytes(32)
    with open(CONTACT_KEY, "wb") as f:
        f.write(k)
    return k


def contact_hash(contact):
    """A phone number as a value that recognises a repeat caller and nothing else.

    Truncated to 16 hex characters: enough that two callers colliding is a
    curiosity rather than a problem, short enough that it is obviously not a
    number anybody could dial.
    """
    if not contact:
        return None
    return hmac.new(_contact_key(), str(contact).strip().encode(),
                    hashlib.sha256).hexdigest()[:16]

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS reports (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  ts         TEXT NOT NULL,
  event      TEXT NOT NULL,
  place      TEXT,
  lat        REAL, lon REAL,
  kind       TEXT NOT NULL,
  depth_cm   INTEGER,
  note       TEXT,
  photo      TEXT,
  road       TEXT,
  status     TEXT NOT NULL DEFAULT 'new',
  resolved_at TEXT,
  resolved_by TEXT
);
CREATE INDEX IF NOT EXISTS ix_reports_event ON reports(event, status);
CREATE INDEX IF NOT EXISTS ix_reports_ts    ON reports(ts);

CREATE TABLE IF NOT EXISTS help (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  ts         TEXT NOT NULL,
  event      TEXT NOT NULL,
  place      TEXT,
  lat        REAL, lon REAL,
  people     INTEGER NOT NULL DEFAULT 1,
  mobility   TEXT,
  contact    TEXT,
  note       TEXT,
  status     TEXT NOT NULL DEFAULT 'waiting',
  assigned   TEXT,
  eta        TEXT,
  closed_at  TEXT
);
CREATE INDEX IF NOT EXISTS ix_help_event ON help(event, status);

CREATE TABLE IF NOT EXISTS decisions (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  ts          TEXT NOT NULL,
  event       TEXT NOT NULL,
  action      TEXT NOT NULL,
  decision    TEXT NOT NULL,
  probability REAL,
  threshold   REAL,
  reason      TEXT,
  officer     TEXT
);
CREATE INDEX IF NOT EXISTS ix_dec_event ON decisions(event, ts);
"""

KINDS = ("water_depth", "road_blocked", "shelter_full", "need_rescue",
         "infrastructure", "other")
MOBILITY = ("walking", "needs_help", "cannot_move", "stretcher")
DECISIONS = ("approved", "overridden")
REASONS = {
    "1": "resources unavailable",
    "2": "local knowledge contradicts the model",
    "3": "already actioned",
    "4": "cost estimate wrong",
    "5": "other",
}


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def connect():
    os.makedirs(os.path.dirname(DB) or ".", exist_ok=True)
    os.makedirs(PHOTOS, exist_ok=True)
    c = sqlite3.connect(DB, timeout=15)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def _rows(cur):
    return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------- reports
def add_report(event, kind, place=None, lat=None, lon=None, depth_cm=None,
               note=None, photo=None, road=None):
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    if depth_cm is not None and not (0 <= int(depth_cm) <= 1000):
        raise ValueError("depth_cm must be between 0 and 1000")
    with connect() as c:
        cur = c.execute(
            "INSERT INTO reports(ts,event,place,lat,lon,kind,depth_cm,note,photo,road)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (now(), event, place, lat, lon, kind,
             None if depth_cm is None else int(depth_cm), note, photo, road))
        return cur.lastrowid


def reports(event=None, status=None, kind=None, limit=200):
    q, a = "SELECT * FROM reports WHERE 1=1", []
    for col, val in (("event", event), ("status", status), ("kind", kind)):
        if val:
            q += f" AND {col}=?"; a.append(val)
    q += " ORDER BY id DESC LIMIT ?"; a.append(int(limit))
    with connect() as c:
        return _rows(c.execute(q, a))


def resolve_report(rid, by="officer"):
    with connect() as c:
        cur = c.execute("UPDATE reports SET status='resolved', resolved_at=?,"
                        " resolved_by=? WHERE id=? AND status!='resolved'",
                        (now(), by, int(rid)))
        return cur.rowcount


def save_photo(rid, data, suffix=".jpg"):
    """Photos go to disk, not into the database. A district's SQLite file has to
    stay small enough to copy onto a pen drive."""
    if len(data) > 8_000_000:
        raise ValueError("photo larger than 8 MB")
    name = f"{rid:08d}_{hashlib.sha1(data).hexdigest()[:8]}{suffix}"
    path = os.path.join(PHOTOS, name)
    with open(path, "wb") as f:
        f.write(data)
    with connect() as c:
        c.execute("UPDATE reports SET photo=? WHERE id=?", (name, int(rid)))
    return name


# ---------------------------------------------------------------- help
def add_help(event, place=None, lat=None, lon=None, people=1, mobility=None,
             contact=None, note=None):
    if mobility and mobility not in MOBILITY:
        raise ValueError(f"mobility must be one of {MOBILITY}")
    if not (1 <= int(people) <= 500):
        raise ValueError("people must be between 1 and 500")
    # A phone number is stored scrambled with this district's own secret. The
    # system needs to recognise a repeat caller; it does not need to hold a list
    # of flood victims' numbers, and a plain hash of a ten-digit number is a
    # list of flood victims' numbers to anybody willing to spend a minute on it.
    ch = contact_hash(contact)
    with connect() as c:
        cur = c.execute(
            "INSERT INTO help(ts,event,place,lat,lon,people,mobility,contact,note)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (now(), event, place, lat, lon, int(people), mobility, ch, note))
        return cur.lastrowid


def help_queue(event=None, status=None, limit=200):
    q, a = "SELECT * FROM help WHERE 1=1", []
    for col, val in (("event", event), ("status", status)):
        if val:
            q += f" AND {col}=?"; a.append(val)
    # the least mobile first, then the largest group, then oldest
    q += (" ORDER BY CASE mobility WHEN 'stretcher' THEN 0 WHEN 'cannot_move'"
          " THEN 1 WHEN 'needs_help' THEN 2 ELSE 3 END, people DESC, id ASC LIMIT ?")
    a.append(int(limit))
    with connect() as c:
        return _rows(c.execute(q, a))


def assign_help(hid, team, eta=None):
    with connect() as c:
        cur = c.execute("UPDATE help SET status='assigned', assigned=?, eta=?"
                        " WHERE id=? AND status='waiting'", (team, eta, int(hid)))
        return cur.rowcount


def close_help(hid):
    with connect() as c:
        cur = c.execute("UPDATE help SET status='closed', closed_at=? WHERE id=?",
                        (now(), int(hid)))
        return cur.rowcount


# ---------------------------------------------------------------- decisions
def add_decision(event, action, decision, probability=None, threshold=None,
                 reason=None, officer=None):
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {DECISIONS}")
    if decision == "overridden" and not reason:
        raise ValueError("an override must carry a reason")
    with connect() as c:
        cur = c.execute(
            "INSERT INTO decisions(ts,event,action,decision,probability,threshold,"
            "reason,officer) VALUES(?,?,?,?,?,?,?,?)",
            (now(), event, action, decision, probability, threshold,
             REASONS.get(str(reason), reason), officer))
        return cur.lastrowid


def decisions(event=None, limit=200):
    q, a = "SELECT * FROM decisions WHERE 1=1", []
    if event:
        q += " AND event=?"; a.append(event)
    q += " ORDER BY id DESC LIMIT ?"; a.append(int(limit))
    with connect() as c:
        return _rows(c.execute(q, a))


def summary(event=None):
    with connect() as c:
        def one(sql, *a):
            return c.execute(sql, a).fetchone()[0]
        w = " WHERE event=?" if event else ""
        a = (event,) if event else ()
        return dict(
            reports_new=one(f"SELECT COUNT(*) FROM reports{w or ' WHERE 1=1'}"
                            f" AND status='new'", *a),
            reports_total=one(f"SELECT COUNT(*) FROM reports{w}", *a),
            help_waiting=one(f"SELECT COALESCE(SUM(people),0) FROM help"
                             f"{w or ' WHERE 1=1'} AND status='waiting'", *a),
            help_open=one(f"SELECT COUNT(*) FROM help{w or ' WHERE 1=1'}"
                          f" AND status!='closed'", *a),
            decisions=one(f"SELECT COUNT(*) FROM decisions{w}", *a),
        )
