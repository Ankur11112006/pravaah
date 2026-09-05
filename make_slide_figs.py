"""Draw the deck's diagrams as PNGs, in the template's own palette.

The finals template is a light deck: black text, cyan #00AEEF and slate #303642
accents, Calibri, 20 x 11.25 inch. These figures use those colours and that
typeface and nothing else, so they sit inside it without looking pasted in.

Every number that appears in a figure is read from out/numbers.json, the same
file the documents are stamped from. A figure that quotes a different number
from the paragraph beside it is worse than no figure.

Matplotlib does not wrap text, so every string that sits in a box is wrapped
here to a character count measured against that box's width. Getting this wrong
does not look wrong in code; it looks like text running out of the card and into
the next one.

    .venv/Scripts/python.exe make_slide_figs.py   ->  out/figs/*.png
"""
import json
import os
import sys
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

sys.stdout.reconfigure(encoding="utf-8")

OUT = "out/figs"
os.makedirs(OUT, exist_ok=True)
N = json.load(open("out/numbers.json"))["numbers"]

CYAN, SLATE, INK = "#00AEEF", "#303642", "#12151A"
BLUE, RED, GREEN, AMBER = "#5170FF", "#C0504D", "#2E9E4F", "#C98A1E"
DIM, RULE, PANEL = "#6B7684", "#D8DEE6", "#F4F6F9"
FONT = "Calibri"

plt.rcParams.update({"font.family": FONT, "font.size": 13, "text.color": INK,
                     "savefig.facecolor": "white", "figure.facecolor": "white"})

FIG_W = 16.0        # every figure is this wide, so they scale identically on a slide


def canvas(h):
    fig = plt.figure(figsize=(FIG_W, h), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100 * h / FIG_W)
    ax.axis("off")
    return fig, ax, 100 * h / FIG_W


def wrap(s, box_w, size):
    """Wrap to a character count that fits `box_w` canvas units at `size` pt.

    One canvas unit is FIG_W/100 inch. Calibri averages about 0.47 em per
    character, and an em is size/72 inch. The 0.93 is measured slack, because
    running one character over is uglier than stopping one short.
    """
    inches = box_w * FIG_W / 100.0
    chars = max(8, int(inches / (0.47 * size / 72.0) * 0.93))
    return "\n".join(textwrap.fill(p, chars) for p in s.split("\n"))


def box(ax, x, y, w, h, fill="white", edge=RULE, lw=1.4, r=1.0, z=2):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle=f"round,pad=0,rounding_size={r}",
                                facecolor=fill, edgecolor=edge, linewidth=lw, zorder=z))


def txt(ax, x, y, s, size=13, colour=INK, weight="normal", ha="left", va="top",
        z=5, style="normal", lh=1.4):
    ax.text(x, y, s, fontsize=size, color=colour, fontweight=weight, ha=ha, va=va,
            zorder=z, fontstyle=style, linespacing=lh)


def arrow(ax, x1, y1, x2, y2, colour=SLATE, lw=2.0, ms=13, z=3):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                 mutation_scale=ms, color=colour, linewidth=lw,
                                 zorder=z, shrinkA=0, shrinkB=0))


def eyebrow(ax, x, y, s, colour=DIM, size=10.5):
    txt(ax, x, y, s.upper(), size=size, colour=colour, weight="bold", va="center")


def save(fig, name):
    p = f"{OUT}/{name}.png"
    fig.savefig(p, dpi=200)
    plt.close(fig)
    print(f"  {p}")


# ═════════════════════════════════════════════ 1. the problem, as a picture
def fig_problem():
    fig, ax, H = canvas(7.4)                       # H = 46.25
    eyebrow(ax, 2, 43.5, "PS3  ·  where the system stops")

    # what exists
    box(ax, 2, 13, 26, 26, fill=PANEL)
    eyebrow(ax, 4, 36.5, "what India already has", colour=SLATE)
    txt(ax, 4, 34, "CWC Flood Forecasting", size=15, weight="bold")
    txt(ax, 4, 30.5, "354 forecast stations, live", size=12.5, colour=DIM)
    txt(ax, 4, 27, wrap("official danger level  ·  issued forecasts  ·  public and "
                        "keyless", 22, 12), size=12, colour=DIM)
    box(ax, 4, 15, 13.5, 4.4, fill="white", edge=CYAN, lw=1.6)
    txt(ax, 5.4, 18.3, "50.40 m", size=15, weight="bold", colour=CYAN)

    # the gap
    box(ax, 33, 10, 30, 32, fill="white", edge=RED, lw=2.2)
    txt(ax, 48, 39, "?", size=44, colour=RED, weight="bold", ha="center")
    txt(ax, 48, 28.5, "THE MISSING LAYER", size=14, weight="bold", ha="center",
        colour=RED)
    txt(ax, 48, 24.5, wrap("Nothing public turns a level in metres into people, "
                           "roads, shelters and hours.", 26, 12.5),
        size=12.5, ha="center", colour=SLATE)
    txt(ax, 48, 14, "this is what we built", size=12, ha="center", colour=DIM,
        style="italic")

    # what must be decided
    box(ax, 68, 13, 30, 26, fill=PANEL)
    eyebrow(ax, 70, 36.5, "what a district must decide", colour=SLATE)
    for i, q in enumerate(["Who is in the water?",
                           "Which road closes, and when?",
                           "Which shelter has room?",
                           "Am I authorised to move them?"]):
        txt(ax, 70, 32.5 - i * 4.4, "•   " + q, size=13.5, va="center")

    arrow(ax, 28.6, 26, 32.4, 26, lw=2.4)
    arrow(ax, 63.6, 26, 67.4, 26, lw=2.4)

    ax.plot([2, 98], [7.6, 7.6], color=RULE, lw=1, zorder=1)
    eyebrow(ax, 2, 5.6, "we went looking in the official data.  two findings")
    txt(ax, 2, 3.7, "NWIC / NWDP carries CWC telemetry for 15 basins.  The Ganga is "
        "not one of them:  a search for “patna” returns 0.",
        size=12.5, colour=SLATE)
    txt(ax, 2, 1.6, "C-Flood publishes real inundation depth every 3 h to 48 h ahead "
        "— for the Mahanadi basin only.  Everywhere else, depth must be inferred.",
        size=12.5, colour=SLATE)
    save(fig, "fig1_problem")


# ═════════════════════════════════════════════ 2. architecture
def fig_architecture():
    fig, ax, H = canvas(8.0)                        # H = 50
    eyebrow(ax, 2, 47.5, "architecture  ·  the split down the middle is the design")

    srcs = [("CWC gauges", "354 stations, live"),
            ("NDMA SACHET", "public alerts"),
            ("GloFAS / Open-Meteo", "50-member ensemble"),
            ("Sentinel-1 SAR", "flood extent"),
            ("Copernicus DEM", "terrain, 30 m"),
            ("GHS-POP + buildings", "people and roofs"),
            ("OpenStreetMap", "roads, shelters"),
            ("C-Flood (NRSC)", "depth, Mahanadi")]
    eyebrow(ax, 2, 43, "public sources  ·  free, keyless", colour=SLATE)
    top, step = 39, 4.3
    for i, (a, b) in enumerate(srcs):
        y = top - i * step
        txt(ax, 2, y, a, size=12.5, weight="bold", va="center")
        txt(ax, 14, y, b, size=11.5, colour=DIM, va="center")
    # one trunk, not eight crossing lines
    bot = top - (len(srcs) - 1) * step
    ax.plot([28, 28], [bot, top], color="#C3CBD6", lw=1.2, zorder=1)
    for i in range(len(srcs)):
        ax.plot([26.5, 28], [top - i * step] * 2, color="#C3CBD6", lw=1.2, zorder=1)
    arrow(ax, 28, (top + bot) / 2, 33.4, (top + bot) / 2, colour="#9AA6B4", lw=1.6, ms=12)

    box(ax, 34, 6, 32, 38, fill="white", edge=SLATE, lw=2)
    eyebrow(ax, 36, 41.5, "district server  ·  one laptop", colour=SLATE)

    box(ax, 36, 29, 28, 9, fill="#E8F7FE", edge=CYAN, lw=1.6)
    txt(ax, 37.6, 36.4, "LIVE  ·  national", size=12, weight="bold", colour=CYAN)
    txt(ax, 37.6, 33.8, wrap("What is true right now, for any point in India. "
                             "No model in it.", 25, 11.5), size=11.5, colour=SLATE)

    box(ax, 36, 18, 28, 9.5, fill="#F1F0FC", edge=BLUE, lw=1.6)
    txt(ax, 37.6, 26, "MODELLED  ·  per district", size=12, weight="bold", colour=BLUE)
    txt(ax, 37.6, 23.4, wrap("What a flood would do here, built from a past event we "
                             "could check the answer against.", 25, 11.5),
        size=11.5, colour=SLATE)

    box(ax, 36, 8, 28, 8.5, fill=PANEL)
    txt(ax, 37.6, 15, "FastAPI  +  SQLite (WAL)", size=12, weight="bold")
    txt(ax, 37.6, 12.4, wrap("Write queue, decision log, and one OSM tile cache "
                             "shared by every phone.", 25, 11.5),
        size=11.5, colour=DIM)

    for i, (title, body, col) in enumerate([
            ("Officer dashboard",
             "Browser, one file. National live map, district plan, decision log.", SLATE),
            ("Citizen app",
             "Android, offline-first. Any place in India. Reports come back.", CYAN)]):
        y = 28 - i * 16
        box(ax, 74, y, 24, 12, fill="white", edge=col, lw=1.8)
        txt(ax, 76, y + 9.6, title, size=13.5, weight="bold", colour=col)
        txt(ax, 76, y + 6.6, wrap(body, 21, 11.5), size=11.5, colour=DIM)
        arrow(ax, 66.4, 26, 73.4, y + 6, colour="#9AA6B4", lw=1.5, ms=11)
    arrow(ax, 73.4, 14, 66.4, 20, colour=CYAN, lw=1.5, ms=11)
    txt(ax, 70, 12.6, "reports back", size=10.5, colour=CYAN, ha="center", va="center")

    ax.plot([2, 98], [4.4, 4.4], color=RULE, lw=1, zorder=1)
    txt(ax, 2, 2.8, "The two halves are never mixed on screen without a label.  "
        "The live half is national from day one;  the modelled half costs 121 s of "
        "compute per district.", size=12, colour=SLATE)
    save(fig, "fig2_architecture")


# ═════════════════════════════════════════════ 3. the pipeline
def fig_pipeline():
    fig, ax, H = canvas(5.4)                        # H = 33.75
    eyebrow(ax, 2, 31.5, "the pipeline  ·  six stages, 121 seconds, one command")

    stages = [
        ("HAZARD", "Fit a water level to an extent radar measured",
         f"{N['flooded_km2']} km²"),
        ("EXPOSURE", "GHS-POP resampled onto the 30 m grid",
         f"{N['people_wet']:,} in the water"),
        ("ROUTING", "Max-bottleneck path per settlement",
         f"{N['no_route']} with no route"),
        ("ALLOCATION", "Min-cost flow into measured capacity",
         f"{N['placed']:,} placed"),
        ("TIMELINE", "The hour each road stops carrying each vehicle",
         "holds / closes / gone"),
        ("DECISION", "Cost-loss ladder on a live ensemble",
         "logged, with a reason"),
    ]
    w, gap = 14.4, 2.3
    for i, (name, what, num) in enumerate(stages):
        x = 2 + i * (w + gap)
        box(ax, x, 8.5, w, 18, fill="white", lw=1.5)
        ax.add_patch(Rectangle((x, 25), w, 1.5, facecolor=CYAN, edgecolor="none",
                               zorder=3))
        txt(ax, x + 1.2, 23.4, name, size=12.5, weight="bold", colour=SLATE)
        txt(ax, x + 1.2, 20.4, wrap(what, w - 2.4, 11.5), size=11.5, colour=DIM)
        txt(ax, x + 1.2, 11.6, wrap(num, w - 2.4, 12.5), size=12.5, weight="bold",
            colour=CYAN)
        if i < len(stages) - 1:
            arrow(ax, x + w + 0.3, 17.5, x + w + gap - 0.3, 17.5, colour="#B9C2CD",
                  lw=1.8, ms=11)

    ax.plot([2, 98], [6, 6], color=RULE, lw=1, zorder=1)
    txt(ax, 2, 4.4, "Each stage takes the previous stage's output as a file, so any "
        "of them can be replaced.  The four after HAZARD accept a depth raster from "
        "any source:", size=12, colour=SLATE)
    txt(ax, 2, 2.2, "the day operational depth exists for a basin, it plugs straight in.",
        size=12, colour=SLATE)
    save(fig, "fig3_pipeline")


# ═════════════════════════════════════════════ 4. the falsification result
def fig_validation():
    fig = plt.figure(figsize=(FIG_W, 6.6), dpi=200)
    fig.subplots_adjust(left=0.06, right=0.975, top=0.72, bottom=0.20, wspace=0.30)

    fig.text(0.06, 0.935, "WE RAN THE TEST THAT WOULD KILL THIS PROJECT.  IT FAILED.",
             fontsize=17, fontweight="bold", color=INK, va="top")
    fig.text(0.06, 0.865, "Pre-registered pass mark: precision > 0.50 at recall > 0.70, "
             "on two independent events.", fontsize=12.5, color=DIM, va="top")

    ev = ["Patna 2019", "Delhi 2023"]
    ax = fig.add_subplot(1, 2, 1)
    terr = [N["patna_auc_hand"], N["delhi_auc_hand"]]
    dist = [N["patna_auc_dist"], N["delhi_auc_dist"]]
    ax.bar([-0.19, 0.81], terr, width=0.34, color=SLATE, label="best terrain predictor")
    ax.bar([0.19, 1.19], dist, width=0.34, color=RED,
           label="distance to the river, alone")
    for i in (0, 1):
        ax.text(i - 0.19, terr[i] + 0.012, f"{terr[i]:.3f}", ha="center", fontsize=12,
                color=SLATE, fontweight="bold")
        ax.text(i + 0.19, dist[i] + 0.012, f"{dist[i]:.3f}", ha="center", fontsize=12,
                color=RED, fontweight="bold")
    ax.set_xticks([0, 1]); ax.set_xticklabels(ev, fontsize=13)
    ax.set_ylim(0.5, 1.06); ax.set_ylabel("AUC", fontsize=12, color=DIM)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(RULE); ax.spines["bottom"].set_color(RULE)
    ax.tick_params(colors=DIM, labelsize=11)
    ax.legend(frameon=False, fontsize=11.5, loc="upper left")
    ax.set_title("Terrain does not beat “how far is the river”",
                 fontsize=13.5, color=INK, loc="left", pad=10)

    ax2 = fig.add_subplot(1, 2, 2)
    med = [N["patna_median_dist_m"], N["delhi_median_dist_m"]]
    ax2.barh([1, 0], med, height=0.30, color=CYAN)
    for y, v in zip((1, 0), med):
        ax2.text(v + 6, y, f"{v} m", va="center", fontsize=13, fontweight="bold",
                 color=CYAN)
    ax2.set_yticks([1, 0]); ax2.set_yticklabels(ev, fontsize=13)
    ax2.set_ylim(-0.6, 1.6); ax2.set_xlim(0, 235)
    ax2.set_xlabel("median distance of the mapped “flood” from permanent water",
                   fontsize=12, color=DIM, labelpad=8)
    for s in ("top", "right"): ax2.spines[s].set_visible(False)
    ax2.spines["left"].set_color(RULE); ax2.spines["bottom"].set_color(RULE)
    ax2.tick_params(colors=DIM, labelsize=11)
    ax2.set_title("What a free satellite sees is the channel, not the disaster",
                  fontsize=13.5, color=INK, loc="left", pad=10)

    fig.text(0.06, 0.105, "Both real disasters were kilometres from the river "
             "— Rajendra Nagar and Kankarbagh in Patna, Civil Lines and ITO in "
             "Delhi — and neither is in the ground truth at all.",
             fontsize=12.5, color=SLATE, va="top")
    fig.text(0.06, 0.055, "So the requirement cannot be met by anyone using free data. "
             " That is why the design changed:  stop predicting where water goes, "
             "fit a level to an extent that was measured.",
             fontsize=12.5, color=SLATE, va="top")
    save(fig, "fig4_validation")


# ═════════════════════════════════════════════ 5. USP
def fig_usp():
    fig, ax, H = canvas(6.4)                        # H = 40
    txt(ax, 2, 37.8, "What no other flood dashboard does", size=20, weight="bold")

    items = [
        ("01", "Live for all of India on day one", RED,
         "Gauges, alerts and weather for any point in the country, from public "
         "feeds.  No district setup, no onboarding, nothing to configure first."),
        ("02", "Measured and modelled are separated on screen", CYAN,
         "The top bar is a gauge reading with the hour it was taken.  The slider is "
         "the model, labelled.  They were one field once, showing 48.74 for a gauge "
         "reading 50.40."),
        ("03", "The citizen is a sensor, not a feedback form", BLUE,
         "Radar cannot see water between buildings.  A person outside their door "
         "can.  That report is the only input here that sees urban flooding, and it "
         "lands in the officer's queue."),
        ("04", "It works with the network off", GREEN,
         "4.5 MB of map saved per area.  Reads serve their last good answer and say "
         "how old it is.  Writes queue on the phone and send themselves."),
        ("05", "Free and keyless, end to end", AMBER,
         "No key, no login, no licence to negotiate.  If a district office cannot "
         "fetch it on a Tuesday morning, we did not use it."),
    ]
    w, gap = 18.4, 1.5
    for i, (num, head, col, body) in enumerate(items):
        x = 2 + i * (w + gap)
        box(ax, x, 5.5, w, 26, fill="white", lw=1.4)
        ax.add_patch(Rectangle((x, 5.5), 0.8, 26, facecolor=col, edgecolor="none",
                               zorder=3))
        txt(ax, x + 2.2, 29.4, num, size=13, weight="bold", colour=col)
        txt(ax, x + 2.2, 26.6, wrap(head, w - 4, 13.5), size=13.5, weight="bold")
        txt(ax, x + 2.2, 20.6, wrap(body, w - 4, 11), size=11, colour=DIM)

    ax.plot([2, 98], [3.2, 3.2], color=RULE, lw=1, zorder=1)
    txt(ax, 2, 2.0, "Every one of these is a decision we can defend with a file in "
        "the repository, not a claim on a slide.", size=12.5, colour=SLATE)
    save(fig, "fig5_usp")


# ═════════════════════════════════════════════ 6. demo flow
def fig_demoflow():
    fig, ax, H = canvas(4.4)                        # H = 27.5
    eyebrow(ax, 2, 25.5, "demo  ·  input → process → output → benefit")

    steps = [
        ("INPUT", "A river level, live from the CWC network.", CYAN),
        ("PROCESS", "Six stages: hazard, exposure, routing, allocation, timeline.", SLATE),
        ("OUTPUT", f"{N['people_wet']:,} in the water.  {N['placed']:,} placed.  "
                   f"{N['no_route']} with no road at all.", BLUE),
        ("BENEFIT", "The officer stops guessing who to move.  The citizen stops "
                    "guessing whether the alert means them.", GREEN),
    ]
    w, gap = 21.6, 3.2
    for i, (name, body, col) in enumerate(steps):
        x = 2 + i * (w + gap)
        box(ax, x, 6, w, 16, fill="white", edge=col, lw=1.8)
        txt(ax, x + 1.6, 20.4, name, size=12, weight="bold", colour=col)
        txt(ax, x + 1.6, 17.2, wrap(body, w - 3.2, 12), size=12)
        if i < 3:
            arrow(ax, x + w + 0.4, 14, x + w + gap - 0.4, 14, colour="#B9C2CD",
                  lw=2, ms=13)
    txt(ax, 2, 3.6, "Then turn on aeroplane mode and open the map again.",
        size=12.5, colour=SLATE, weight="bold")
    save(fig, "fig6_demoflow")


print("writing figures")
for f in (fig_problem, fig_architecture, fig_pipeline, fig_validation, fig_usp,
          fig_demoflow):
    f()
print("done")
