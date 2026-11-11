#!/usr/bin/env python3
"""
Generates a 16:10 publication-grade infographic on the NC-03 / NC-01 October 2025
SB 249 "Dummymander" backfire and Raymond Smith Jr.'s +293 vote lead over Rep. Greg Murphy.

Outputs:
  - assets/chart_nc03_dummymander_2026.png
"""
import json
import shutil
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Polygon as MplPolygon
import matplotlib.patheffects as pe
import numpy as np

BASE_DIR = Path("/home/mike10010100/git/elections-2026")
OUT_PATH = BASE_DIR / "assets" / "chart_nc03_dummymander_2026.png"


def decode_topojson_counties(topo_path: Path, state_fips_prefix: str = "37"):
    with open(topo_path, encoding="utf-8") as f:
        topo = json.load(f)
    scale = topo["transform"]["scale"]
    translate = topo["transform"]["translate"]
    raw_arcs = topo["arcs"]

    decoded_arcs = []
    for arc in raw_arcs:
        x, y = 0, 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * scale[0] + translate[0], -(y * scale[1] + translate[1])))
        decoded_arcs.append(pts)

    def stitch_ring(arc_indices):
        ring = []
        for idx in arc_indices:
            seg = decoded_arcs[idx] if idx >= 0 else decoded_arcs[~idx][::-1]
            ring.extend(seg[1:] if ring else seg)
        return ring

    counties = {}
    for geom in topo["objects"]["counties"]["geometries"]:
        gid = str(geom.get("id", ""))
        if not gid.startswith(state_fips_prefix):
            continue
        polys = []
        if geom["type"] == "Polygon":
            polys.append(stitch_ring(geom["arcs"][0]))
        elif geom["type"] == "MultiPolygon":
            for poly_arcs in geom["arcs"]:
                polys.append(stitch_ring(poly_arcs[0]))
        counties[gid] = {
            "name": (geom.get("properties") or {}).get("name", ""),
            "polys": polys,
        }
    return counties


def poly_centroid(polys):
    best_ring = max(polys, key=len)
    a = cx = cy = 0.0
    for i in range(len(best_ring) - 1):
        x0, y0 = best_ring[i]
        x1, y1 = best_ring[i + 1]
        cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(a) > 1e-9:
        a *= 0.5
        return (cx / (6.0 * a), cy / (6.0 * a))
    xs = [p[0] for p in best_ring]
    ys = [p[1] for p in best_ring]
    return (float(np.mean(xs)), float(np.mean(ys)))


def build_chart():
    with open(BASE_DIR / "site_data" / "overview.json", encoding="utf-8") as f:
        ov = json.load(f)
    nc_house = sorted(
        [r for r in ov["house_races"] if r["state"] == "NC"],
        key=lambda r: int(r.get("seat_number") or 0),
    )

    def load_dist_counties(seat_num: int, dem_id: str, gop_id: str):
        p = BASE_DIR / "data" / "nyt_2026" / "house_districts" / f"results-north-carolina-us-house-{seat_num}.json"
        doc = json.load(open(p, encoding="utf-8"))["races"][0]
        out = {}
        for u in doc["reporting_units"]:
            if u.get("level") == "county":
                fips = u["fips_state"] + u["fips_county"]
                vc = {c["nyt_id"]: c["votes"]["total"] for c in u["candidates"]}
                dv, gv = vc.get(dem_id, 0), vc.get(gop_id, 0)
                tv = u["total_votes"]
                out[fips] = {
                    "name": u["name"],
                    "dem": dv,
                    "gop": gv,
                    "tot": tv,
                    "net": dv - gv,
                    "pct": (dv - gv) / tv * 100.0 if tv else 0.0,
                }
        return out

    nc01_cos = load_dist_counties(1, "davis-d", "buckhout-l")
    nc03_cos = load_dist_counties(3, "smith-r", "murphy-g")

    added_to_nc03 = {"37191", "37195", "37107", "37079"}         # Wayne, Wilson, Lenoir, Greene
    kept_in_nc03 = {"37147", "37133", "37061", "37163", "37103"}  # Pitt, Onslow, Duplin, Sampson, Jones
    moved_out_to_nc01 = {"37031", "37013", "37049", "37137", "37055", "37095"}  # 6 coastal counties

    added_net = sum(nc03_cos[f]["net"] for f in added_to_nc03)        # +2,532
    kept_net = sum(nc03_cos[f]["net"] for f in kept_in_nc03)          # -2,239
    total_nc03_net = added_net + kept_net                              # +293
    moved_out_6cos_net = sum(nc01_cos[f]["net"] for f in moved_out_to_nc01)  # -18,023

    nc_polys = decode_topojson_counties(BASE_DIR / "site_data" / "counties-albers-10m.json", "37")

    BG = "#f6f5f0"
    PANEL_BG = "#ffffff"
    TEXT = "#18181b"
    SUBTEXT = "#4b5563"
    MUTED = "#71717a"
    GRID = "#e4e4e7"
    DEM_DARK = "#134e9b"
    DEM_MID = "#2563eb"
    GOP_DARK = "#991b1b"
    GOP_MID = "#dc2626"

    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]
    plt.rcParams["text.parse_math"] = False

    fig = plt.figure(figsize=(16.5, 10.3), dpi=200, facecolor=BG)

    # Explicit non-overlapping axes boxes [left, bottom, width, height]
    ax_map = fig.add_axes([0.025, 0.065, 0.435, 0.765], facecolor="#e8f1f8")
    ax_b = fig.add_axes([0.595, 0.565, 0.380, 0.252], facecolor=PANEL_BG)
    ax_c = fig.add_axes([0.595, 0.075, 0.380, 0.380], facecolor=PANEL_BG)

    # --- Header ---
    fig.text(
        0.025, 0.953,
        "Anatomy of a 'Dummymander': How NC's 2025 Redraw Put Safe GOP NC-03 on the Brink",
        fontsize=19.8, fontweight="bold", color=TEXT,
    )
    fig.text(
        0.025, 0.915,
        f"In Oct. 2025 (SB 249), NC Republicans moved 6 coastal GOP counties (R+{abs(moved_out_6cos_net):,} net votes) out of Greg Murphy's NC-03 to target Dem Rep. Don Davis in NC-01,",
        fontsize=11.5, color=SUBTEXT,
    )
    fig.text(
        0.025, 0.884,
        f"pulling 4 NC-01 counties into NC-03 instead. Davis won NC-01 anyway (+10,789v), and Dem Raymond Smith Jr. now leads Murphy by +{total_nc03_net} votes (118,488 to 118,195).",
        fontsize=11.5, fontweight="bold", color=DEM_DARK,
    )

    # =========================================================================
    # PANEL A: Eastern NC County Map
    # =========================================================================
    ax_map.set_title(
        "A. Eastern NC County Swap (SB 249 · 2026 House Margins)",
        fontsize=12.2, fontweight="bold", color=TEXT, loc="left", pad=9,
    )

    def margin_color(pct):
        if pct >= 20:
            return "#1d4ed8"
        if pct >= 8:
            return "#3b82f6"
        if pct >= 0:
            return "#93c5fd"
        if pct >= -5:
            return "#fecaca"
        if pct >= -18:
            return "#f87171"
        return "#b91c1c"

    focus_fips = set(nc01_cos.keys()) | set(nc03_cos.keys())
    all_x, all_y = [], []
    for fips in focus_fips:
        if fips in nc_polys:
            for ring in nc_polys[fips]["polys"]:
                all_x.extend(p[0] for p in ring)
                all_y.extend(p[1] for p in ring)

    xmin, xmax = min(all_x) - 7, max(all_x) + 6
    ymin, ymax = min(all_y) - 20, max(all_y) + 16

    for fips, cdata in nc_polys.items():
        is_nc03 = fips in (added_to_nc03 | kept_in_nc03)
        is_nc01 = fips in nc01_cos and not is_nc03

        if is_nc03:
            fc = margin_color(nc03_cos[fips]["pct"])
            ec, lw, z, alpha = "#111827", 1.9, 4, 0.96
        elif is_nc01:
            fc = margin_color(nc01_cos[fips]["pct"])
            if fips in moved_out_to_nc01:
                ec, lw, z, alpha = "#7f1d1d", 1.5, 3, 0.88
            else:
                ec, lw, z, alpha = "#64748b", 0.75, 2, 0.62
        else:
            fc, ec, lw, z, alpha = "#e7e6e1", "#cbc9c2", 0.6, 1, 1.0

        for ring in cdata["polys"]:
            poly = MplPolygon(
                ring, closed=True, facecolor=fc, edgecolor=ec,
                linewidth=lw, alpha=alpha, zorder=z,
            )
            ax_map.add_patch(poly)
            if fips in added_to_nc03:
                border_hi = MplPolygon(
                    ring, closed=True, facecolor="none", edgecolor="#f59e0b",
                    linewidth=2.8, linestyle="-", zorder=6,
                )
                ax_map.add_patch(border_hi)
            elif fips in moved_out_to_nc01:
                border_dash = MplPolygon(
                    ring, closed=True, facecolor="none", edgecolor="#7f1d1d",
                    linewidth=1.5, linestyle="--", zorder=5,
                )
                ax_map.add_patch(border_dash)

    stroke = [pe.withStroke(linewidth=2.6, foreground="white")]
    label_specs = {
        "37195": ("Wilson*\nD+3,955", (-1, 1)),
        "37191": ("Wayne*\nR+962", (-1, -1)),
        "37107": ("Lenoir*\nD+135", (0, 0)),
        "37079": ("Greene*\nR+596", (0, 1)),
        "37147": ("Pitt\nD+10,704", (1, 1)),
        "37133": ("Onslow\nR+8,981", (0, -2)),
        "37061": ("Duplin\nR+2,912", (0, 0)),
        "37163": ("Sampson\nR+265", (1.2, 0.5)),
        "37103": ("Jones\nR+785", (1, -1)),
        "37031": ("Carteret\nR+10,286", (3, -4)),
        "37049": ("Craven\nR+2,279", (1, 1)),
        "37013": ("Beaufort\nR+3,614", (1, 0)),
        "37055": ("Dare\nR+695", (-4, 2)),
        "37137": ("Pamlico\nR+1,119", (5, -2)),
        "37095": ("Hyde\nR+30", (0, 0)),
        "37127": ("Nash\nD+5,898", (-4, 3)),
        "37065": ("Edgecombe\nD+7,100", (1.5, 0.5)),
        "37083": ("Halifax\nD+5,785", (0, 2)),
    }
    for fips, (lbl, (dx, dy)) in label_specs.items():
        if fips not in nc_polys:
            continue
        cx, cy = poly_centroid(nc_polys[fips]["polys"])
        is_focus = fips in (added_to_nc03 | kept_in_nc03)
        ax_map.text(
            cx + dx, cy + dy, lbl,
            ha="center", va="center",
            fontsize=8.0 if is_focus else 7.1,
            fontweight="bold",
            color="#0f172a" if is_focus else "#334155",
            path_effects=stroke, zorder=10,
        )

    ax_map.text(
        0.025, 0.978,
        "*ADDED TO NC-03 FROM NC-01 (Gold Border):\n"
        "Wilson, Lenoir, Greene & Wayne (Smith's home co.)\n"
        f"2026 Net Vote: Smith (D) +{added_net:,} votes!",
        transform=ax_map.transAxes, va="top", ha="left",
        fontsize=8.4, fontweight="bold", color="#92400e",
        bbox=dict(boxstyle="round,pad=0.38", facecolor="#fffbeb", edgecolor="#f59e0b", lw=1.8),
        zorder=15,
    )

    ax_map.text(
        0.978, 0.022,
        "MOVED OUT OF NC-03 -> NC-01 (Dashed Red):\n"
        "Carteret, Beaufort, Craven, Pamlico, Dare, Hyde\n"
        f"Shipped R+{abs(moved_out_6cos_net):,} net GOP votes to NC-01...\n"
        "yet Don Davis (D) STILL won NC-01 by +10,789!",
        transform=ax_map.transAxes, va="bottom", ha="right",
        fontsize=8.2, fontweight="bold", color="#7f1d1d",
        bbox=dict(boxstyle="round,pad=0.38", facecolor="#fef2f2", edgecolor="#dc2626", lw=1.5),
        zorder=15,
    )

    leg_patches = [
        mpatches.Patch(facecolor="#3b82f6", edgecolor="#18181b", label="Dem County Win"),
        mpatches.Patch(facecolor="#f87171", edgecolor="#18181b", label="GOP County Win"),
        mpatches.Patch(facecolor="white", edgecolor="#f59e0b", lw=2.2, label="*Added to NC-03"),
        mpatches.Patch(facecolor="white", edgecolor="#18181b", lw=1.8, label="Kept in NC-03"),
    ]
    ax_map.legend(
        handles=leg_patches, loc="lower left", bbox_to_anchor=(0.02, 0.02),
        fontsize=7.6, framealpha=0.95, facecolor="white", edgecolor="#cbd5e1",
    )

    ax_map.set_xlim(xmin, xmax)
    ax_map.set_ylim(ymin, ymax)
    ax_map.set_aspect("equal")
    ax_map.set_xticks([])
    ax_map.set_yticks([])
    for sp in ax_map.spines.values():
        sp.set_edgecolor("#cbd5e1")
        sp.set_linewidth(1.1)

    # =========================================================================
    # PANEL B: Exact NC-03 Vote Math (+2,532 - 2,239 = +293)
    # =========================================================================
    ax_b.set_title(
        "B. Inside NC-03's 293-Vote Lead: Kept Core vs. Added Counties",
        fontsize=11.5, fontweight="bold", color=TEXT, loc="left", pad=19,
    )
    ax_b.text(
        0.0, 1.02,
        "Election Night: Murphy +233v  ->  Post-Provisionals: Smith +293v (+526v swing; recount zone)",
        transform=ax_b.transAxes, ha="left", va="bottom",
        fontsize=7.9, fontweight="bold", color=DEM_DARK,
    )

    bars = [
        ("5 Kept NC-03 Counties\n(Onslow, Pitt, Duplin,\nJones, Sampson)", kept_net, GOP_MID,
         f"Murphy +{abs(kept_net):,} votes\n(Murphy won his old core!)"),
        ("4 Counties Pulled from NC-01\n(Wilson, Lenoir,\nGreene, Wayne*)", added_net, DEM_MID,
         f"Smith +{added_net:,} votes\n(Wilson +3,955 D wiped out GOP lead)"),
        ("NET 2026 NC-03 TOTAL\n(99% in · Pre-Canvass)", total_nc03_net, DEM_DARK,
         f"Smith +{total_nc03_net:,} votes (+0.12%)\n118,488 (49.43%) vs. 118,195 (49.31%)"),
    ]
    y_b = np.arange(len(bars))[::-1]
    ax_b.axvline(0, color=TEXT, lw=1.3, zorder=3)

    for y, (lbl, val, col, note) in zip(y_b, bars):
        ax_b.barh(y, val, height=0.58, color=col, alpha=0.92, edgecolor=TEXT, lw=0.9, zorder=4)
        if val >= 0:
            ax_b.text(val + 140, y, note, va="center", ha="left", fontsize=8.8, fontweight="bold", color=col)
        else:
            ax_b.text(140, y, note, va="center", ha="left", fontsize=8.8, fontweight="bold", color=GOP_DARK)

    ax_b.set_yticks(y_b)
    ax_b.set_yticklabels([b[0] for b in bars], fontsize=8.9, fontweight="bold", color=TEXT)
    ax_b.set_xlim(-2900, 7600)
    ax_b.set_ylim(-0.55, 2.55)
    ax_b.xaxis.grid(True, linestyle=":", color=GRID, zorder=0)
    ax_b.spines["top"].set_visible(False)
    ax_b.spines["right"].set_visible(False)
    ax_b.set_xlabel("Net Two-Party Vote Margin in NC-03 (GOP <-  0  -> DEM)", fontsize=9.2, fontweight="bold", color=SUBTEXT)

    # =========================================================================
    # PANEL C: NC's "11R - 3D" Gerrymander vs. 2026 Reality
    # =========================================================================
    ax_c.set_title(
        "C. Statewide Backfire: NC's 11 Trump-Won Seats in 2026",
        fontsize=11.5, fontweight="bold", color=TEXT, loc="left", pad=19,
    )
    ax_c.text(
        0.0, 1.02,
        "11R-3D Map Scoreboard: 9 Dem Called (incl. 3 safe D) + 2 Dem Leading (NC-03, 05) = Up to 11D-3R",
        transform=ax_c.transAxes, ha="left", va="bottom",
        fontsize=7.8, fontweight="bold", color=DEM_DARK,
    )

    gop_drawn = [r for r in nc_house if (r.get("pres_2024_margin") or 0) < 0]
    gop_drawn.sort(key=lambda r: (r.get("dem_gop_margin") or 0), reverse=True)

    y_c = np.arange(len(gop_drawn))[::-1]
    ax_c.axvline(0, color=TEXT, lw=1.2, zorder=3)

    for y, r in zip(y_c, gop_drawn):
        seat_num = int(r["seat_number"])
        p24 = r["pres_2024_margin"]
        m26 = r["dem_gop_margin"]
        called = r["called"]
        dem_c = next((c for c in r["candidates"] if c["party"] == "DEM"), {})
        gop_c = next((c for c in r["candidates"] if c["party"] == "GOP"), {})
        v_diff = (dem_c.get("votes") or 0) - (gop_c.get("votes") or 0)

        ax_c.plot([p24, m26], [y, y], color="#94a3b8", lw=1.8, ls="-", zorder=2)
        ax_c.scatter([p24], [y], color="#64748b", s=44, marker="o", zorder=4)

        if m26 > 0 and called:
            col, marker, status = DEM_DARK, "o", f"DEM WIN ({m26:+.1f}%)"
        elif m26 > 0 and not called:
            col, marker, status = "#0284c7", "D", f"DEM LEAD (+{v_diff:,}v)"
        elif m26 < 0 and called:
            col, marker, status = GOP_DARK, "o", f"GOP WIN (R+{abs(m26):.1f}%)"
        else:
            col, marker, status = "#dc2626", "s", f"GOP LEAD (R+{abs(v_diff):,}v)"

        sz = 92 if seat_num in (1, 3, 5) else 62
        ax_c.scatter([m26], [y], color=col, s=sz, marker=marker, edgecolor="white", lw=1.0, zorder=5)

        dem_last = dem_c.get("last_name") or dem_c.get("name", "")
        gop_last = gop_c.get("last_name") or gop_c.get("name", "")
        tag = f"{dem_last} vs. {gop_last}: {status}"
        fw = "bold" if (m26 > 0 or seat_num in (1, 3, 5)) else "normal"
        ax_c.text(max(m26, 0) + 0.9, y, tag, va="center", ha="left", fontsize=8.3, fontweight=fw, color=col)

    nc03_idx = next(i for i, r in enumerate(gop_drawn) if int(r["seat_number"]) == 3)
    nc03_y = y_c[nc03_idx]
    ax_c.axhspan(nc03_y - 0.44, nc03_y + 0.44, color="#fef3c7", alpha=0.72, zorder=1)

    ax_c.set_yticks(y_c)
    ax_c.set_yticklabels(
        [f"NC-{int(r['seat_number']):02d} (Trump +{abs(r['pres_2024_margin']):.1f})" for r in gop_drawn],
        fontsize=8.6, fontweight="bold", color=TEXT,
    )
    ax_c.set_xlim(-21.5, 38.5)
    ax_c.set_ylim(-0.65, len(gop_drawn) - 0.35)
    ax_c.xaxis.grid(True, linestyle=":", color=GRID, zorder=0)
    ax_c.spines["top"].set_visible(False)
    ax_c.spines["right"].set_visible(False)
    ax_c.set_xlabel("District Margin % (Grey Dot = 2024 Trump Baseline  ->  Colored Marker = 2026 House)", fontsize=9.1, fontweight="bold", color=SUBTEXT)

    fig.text(
        0.025, 0.017,
        "Sources: NC State Board of Elections & Live NYT 2026 Returns (as of Nov. 10, 2026; county canvass Fri. Nov. 13) | NC Session Law 2025-95 (SB 249) | github.com/mike10010100/elections-2026",
        fontsize=8.5, color=MUTED,
    )

    fig.savefig(OUT_PATH, dpi=200, facecolor=BG)
    plt.close(fig)

    ffmpeg_bin = shutil.which("ffmpeg") or "/home/linuxbrew/.linuxbrew/bin/ffmpeg"
    if Path(ffmpeg_bin).exists():
        pal = OUT_PATH.with_name(".nc03_pal.png")
        opt = OUT_PATH.with_name(".nc03_opt.png")
        subprocess.run([ffmpeg_bin, "-y", "-i", str(OUT_PATH), "-vf", "palettegen=max_colors=256", str(pal)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run([ffmpeg_bin, "-y", "-i", str(OUT_PATH), "-i", str(pal), "-lavfi", "paletteuse=dither=sierra2_4a", str(opt)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if opt.exists() and opt.stat().st_size > 0:
            opt.replace(OUT_PATH)
        if pal.exists():
            pal.unlink()

    print(f"Saved {OUT_PATH} ({OUT_PATH.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    build_chart()
