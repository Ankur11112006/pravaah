"""Stamp the documents from out/numbers.json, so no figure can go stale.

A number written by hand into a document is a copy, and a copy drifts the
moment the code changes. This replaces that copy with a marker the document
carries and this script fills:

    markdown   <!--N:people_wet-->59,327<!--/N-->
    html       <span data-n="people_wet">59,327</span>

Run verify.py first (it writes out/numbers.json), then this. With --check it
changes nothing and exits non-zero if any document is out of date, which is
what a reviewer should run before believing a figure.
"""
import io, json, os, re, sys

DOCS = ["README.md", "ARCHITECTURE.md", "REPORT.md", "DEFENCE.md",
        "PRAVAAH-COMPLETE.md", "PRAVAAH-SIMPLE.md",
        "out/pravaah_overview.html", "../PS3-ppt-content.md"]
FMT = {"census_rel_error_pct": "+.1f",   # a signed percentage reads as a verdict
       "fwdet_median_m": ".2f",
       "shelter_roof_ha": ".1f",
       "modelled_median_depth_m": ".2f",
       "fwdet_below_30cm_pct": ".1f"}


def fmt(key, val):
    spec = FMT.get(key)
    if spec:
        return format(val, spec)
    if isinstance(val, float) and not val.is_integer():
        return f"{val:,.3f}".rstrip("0").rstrip(".")
    return f"{int(val):,}"


def main(check=False):
    src = "out/numbers.json"
    if not os.path.exists(src):
        sys.exit(f"{src} is missing. Run verify.py first, it writes that file.")
    doc = json.load(open(src, encoding="utf-8"))
    nums, prov = doc["numbers"], doc["provenance"]

    # The inner group must not itself contain another marker delimiter. Without
    # that, an UNCLOSED opening marker (one written in prose as an example of the
    # syntax) swallows everything up to the next real closing tag and replaces a
    # whole section of the document with a single number. That happened, to this
    # document set, and it is why the guard below exists too.
    md = re.compile(r"(<!--N:([A-Za-z0-9_]+)-->)((?:(?!<!--).)*?)(<!--/N-->)", re.S)
    html = re.compile(r'(<span data-n="([A-Za-z0-9_]+)"[^>]*>)((?:(?!</?span).)*?)'
                      r'(</span>)', re.S)
    MAX_SPAN = 120        # a stamped value is a number, never a paragraph
    stale, stamped, unknown = [], 0, set()

    for path in DOCS:
        if not os.path.exists(path):
            continue
        s0 = io.open(path, encoding="utf-8").read()
        s = s0

        def sub(m):
            nonlocal stamped
            key, old = m.group(2), m.group(3)
            if len(old) > MAX_SPAN or (chr(10) * 2) in old:
                print(f"  REFUSED  {path}: the span for {key!r} is "
                      f"{len(old)} characters, which is not a number. Left "
                      f"untouched; check for an unclosed marker above it.")
                return m.group(0)
            if key == "generated":
                new = f"{prov['generated_utc']}, code {prov['code_sha256']}"
            elif key in nums:
                new = fmt(key, nums[key])
            else:
                unknown.add(key)
                return m.group(0)
            # The provenance stamp changes on every run by design, so a newer
            # timestamp is not a stale figure. Only claims count as staleness.
            if new != old and key != "generated":
                stale.append(f"{path}: {key} says {old!r}, should be {new!r}")
            stamped += 1
            return m.group(1) + new + m.group(4)

        s = md.sub(sub, s)
        s = html.sub(sub, s)
        if s != s0 and not check:
            io.open(path, "w", encoding="utf-8").write(s)

    if unknown:
        print(f"markers with no matching number: {sorted(unknown)}")
    if check:
        for line in stale:
            print("  STALE  " + line)
        print(f"{stamped} markers checked, {len(stale)} stale")
        return 1 if (stale or unknown) else 0
    print(f"stamped {stamped} markers across {len(DOCS)} documents "
          f"from {len(nums)} recorded figures")
    for line in stale:
        print("  updated  " + line)
    return 1 if unknown else 0


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv))
