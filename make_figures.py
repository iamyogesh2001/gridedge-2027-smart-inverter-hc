"""
Publication-quality figures for IEEE PES Grid Edge 2027 paper.
Large text, clean layout, no overlap, IEEE-compatible color palette.
Outputs: fig1_voltage_rise.png, fig2_hc_comparison.png, fig3_voltage_profile.png
"""
import pickle, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import MultipleLocator

# ── Load simulation data
with open("/home/claude/gridedge/simulation/partial.pkl","rb") as f:
    data = pickle.load(f)
partial    = data["partial"]
BASE_VPROF = data["BASE_VPROF"]
PV_BUS     = data["PV_BUS"]
ANSI_VMAX  = 1.05
ANSI_VMIN  = 0.95
TOTAL_KW   = data["TOTAL_KW"]
STEPS_LONG = data["STEPS"]             # Unity + Fixed: 31 steps (0-150%)
STEPS_SHORT = np.arange(0,1.01,0.05)  # VV / VW / Combined: 21 steps (0-100%)

# ── Style
plt.rcParams.update({
    "font.family":      "DejaVu Serif",
    "font.size":        13,
    "axes.titlesize":   14,
    "axes.labelsize":   13,
    "xtick.labelsize":  12,
    "ytick.labelsize":  12,
    "legend.fontsize":  11.5,
    "lines.linewidth":  2.2,
    "lines.markersize": 6,
    "axes.grid":        True,
    "grid.alpha":       0.30,
    "grid.linestyle":   "--",
    "figure.dpi":       150,
})

# Color palette — colorblind-friendly, IEEE-safe
COLORS = {
    "Unity PF":       "#D62728",   # red
    "Fixed PF 0.95":  "#1F77B4",   # blue
    "Volt-Var":       "#2CA02C",   # green
    "Volt-Watt":      "#FF7F0E",   # orange
    "Combined VV+VW": "#9467BD",   # purple
}
MARKERS = {
    "Unity PF":       "o",
    "Fixed PF 0.95":  "s",
    "Volt-Var":       "^",
    "Volt-Watt":      "D",
    "Combined VV+VW": "P",
}

# Steps per mode
MODE_STEPS = {
    "Unity PF":       STEPS_LONG,
    "Fixed PF 0.95":  STEPS_LONG,
    "Volt-Var":       STEPS_SHORT,
    "Volt-Watt":      STEPS_SHORT,
    "Combined VV+VW": STEPS_SHORT,
}

# ═══════════════════════════════════════════
# FIGURE 1 — Voltage Rise vs PV Penetration
# ═══════════════════════════════════════════
fig1, ax1 = plt.subplots(figsize=(9, 5.5))

for label, r in partial.items():
    steps = MODE_STEPS[label]
    vm    = r["vmax"]
    n     = min(len(steps), len(vm))
    ax1.plot(steps[:n]*100, vm[:n],
             color=COLORS[label], marker=MARKERS[label],
             markevery=4, label=label, zorder=3)

# ANSI limit
ax1.axhline(ANSI_VMAX, color="black", ls="--", lw=1.8,
            label="ANSI C84.1 Vmax (1.05 pu)", zorder=4)

# Violation shading
ax1.axhspan(ANSI_VMAX, 1.24, color="#FFCCCC", alpha=0.35, zorder=1)
ax1.text(97, 1.215, "Violation zone", color="#990000",
         fontsize=11, ha="right", style="italic", zorder=5)

# HC markers — vertical dotted lines at each HC point
hc_vals = {lbl: r["hc"] for lbl, r in partial.items()}
for label, hc in hc_vals.items():
    ax1.axvline(hc, color=COLORS[label], ls=":", lw=1.2, alpha=0.6, zorder=2)

ax1.set_xlim(0, 105)
ax1.set_ylim(0.995, 1.24)
ax1.xaxis.set_major_locator(MultipleLocator(10))
ax1.yaxis.set_major_locator(MultipleLocator(0.025))
ax1.set_xlabel("PV Penetration  (% of feeder peak load)", labelpad=8)
ax1.set_ylabel("Maximum System Voltage  (pu)", labelpad=8)
ax1.set_title("Maximum Bus Voltage vs. PV Penetration\nIEEE 33-Bus Feeder  |  PV Injection at Bus 17",
              pad=12, fontweight="bold")
ax1.legend(loc="upper left", framealpha=0.92, edgecolor="#AAAAAA")

fig1.tight_layout()
fig1.savefig("/home/claude/gridedge/figures/fig1_voltage_rise.png",
             dpi=200, bbox_inches="tight")
print("✓  fig1_voltage_rise.png")

# ═══════════════════════════════════════════
# FIGURE 2 — Hosting Capacity Bar Chart
# ═══════════════════════════════════════════
fig2, ax2 = plt.subplots(figsize=(9, 5.5))

labels = list(partial.keys())
hcs    = [partial[l]["hc"] for l in labels]
colors = [COLORS[l] for l in labels]
base   = hcs[0]   # Unity PF

bars = ax2.bar(range(len(labels)), hcs, color=colors,
               edgecolor="black", linewidth=0.8, width=0.6, zorder=3)

# Baseline dotted line
ax2.axhline(base, color=COLORS["Unity PF"], ls=":", lw=1.6,
            alpha=0.7, zorder=2, label=f"Unity PF baseline ({base:.0f}%)")

# Value labels + gain annotations
for i, (bar, val, lbl) in enumerate(zip(bars, hcs, labels)):
    # HC value on top of bar
    ax2.text(bar.get_x() + bar.get_width()/2, val + 1.2,
             f"{val:.0f}%", ha="center", va="bottom",
             fontsize=13, fontweight="bold", color="black")
    # Gain annotation above that
    gain = val - base
    if gain > 0:
        ax2.text(bar.get_x() + bar.get_width()/2, val + 6.5,
                 f"+{gain:.0f} pp", ha="center", va="bottom",
                 fontsize=11, color="#006600", fontweight="bold")
    elif gain < 0:
        ax2.text(bar.get_x() + bar.get_width()/2, val + 6.5,
                 f"{gain:.0f} pp", ha="center", va="bottom",
                 fontsize=11, color="#990000", fontweight="bold")

ax2.set_xticks(range(len(labels)))
ax2.set_xticklabels(labels, rotation=22, ha="right", fontsize=12)
ax2.set_ylabel("PV Hosting Capacity  (% of feeder peak load)", labelpad=8)
ax2.set_title("PV Hosting Capacity by IEEE 1547-2018 Inverter Mode\n"
              "IEEE 33-Bus Feeder  |  ANSI C84.1 Voltage Constraint (Vmax ≤ 1.05 pu)",
              pad=12, fontweight="bold")
ax2.set_ylim(0, 125)
ax2.yaxis.set_major_locator(MultipleLocator(20))
ax2.legend(loc="upper left", framealpha=0.92, edgecolor="#AAAAAA")

# Add "pp = percentage points" footnote
ax2.text(0.99, 0.02, "pp = percentage points gain vs. Unity PF baseline",
         transform=ax2.transAxes, fontsize=9.5, ha="right",
         color="gray", style="italic")

fig2.tight_layout()
fig2.savefig("/home/claude/gridedge/figures/fig2_hc_comparison.png",
             dpi=200, bbox_inches="tight")
print("✓  fig2_hc_comparison.png")

# ═══════════════════════════════════════════
# FIGURE 3 — Voltage Profile Along Feeder Trunk
# ═══════════════════════════════════════════
# At 75% PV penetration — the most informative operating point
# (Unity and VW are near violation; Fixed and VV are suppressed)

fig3, ax3 = plt.subplots(figsize=(9, 5.5))

PEN_TARGET = 0.75    # 75% penetration
TRUNK      = list(range(18))   # buses 0–17 (main trunk)

# Base case (no PV)
ax3.plot(TRUNK, BASE_VPROF[:18], color="black", ls="--", lw=1.8,
         marker="o", ms=4, markevery=2, label="Base (no PV)", zorder=5)

for label, r in partial.items():
    steps = MODE_STEPS[label]
    idx   = int(np.argmin(np.abs(steps - PEN_TARGET)))
    if idx < len(r["vprof"]) and r["vprof"][idx] is not None:
        vp = r["vprof"][idx]
        if not np.all(np.isnan(vp)):
            ax3.plot(TRUNK, vp[:18],
                     color=COLORS[label], marker=MARKERS[label],
                     markevery=3, label=label, zorder=3)

# ANSI band
ax3.axhline(ANSI_VMAX, color="black", ls="--", lw=1.4,
            label="ANSI C84.1 limits", zorder=4)
ax3.axhline(ANSI_VMIN, color="black", ls=":",  lw=1.2, zorder=4)
ax3.axhspan(ANSI_VMAX, 1.10, color="#FFCCCC", alpha=0.30, zorder=1)
ax3.axhspan(0.88, ANSI_VMIN, color="#CCE5FF", alpha=0.20, zorder=1)

# PV injection annotation
ax3.annotate("PV injection\n(Bus 17)", xy=(17, 1.089),
             xytext=(14.5, 1.095), fontsize=10,
             arrowprops=dict(arrowstyle="->", color="black", lw=1.2),
             ha="center", zorder=6)

ax3.set_xlim(0, 17)
ax3.set_ylim(0.90, 1.11)
ax3.xaxis.set_major_locator(MultipleLocator(2))
ax3.yaxis.set_major_locator(MultipleLocator(0.02))
ax3.set_xlabel("Bus Number  (feeder trunk, bus 0 = substation)", labelpad=8)
ax3.set_ylabel("Bus Voltage  (pu)", labelpad=8)
ax3.set_title("Voltage Profile Along Feeder Trunk @ 75% PV Penetration\n"
              "IEEE 33-Bus  |  PV at Bus 17  |  Five IEEE 1547-2018 Inverter Modes",
              pad=12, fontweight="bold")
ax3.legend(loc="lower left", framealpha=0.92, edgecolor="#AAAAAA")

fig3.tight_layout()
fig3.savefig("/home/claude/gridedge/figures/fig3_voltage_profile.png",
             dpi=200, bbox_inches="tight")
print("✓  fig3_voltage_profile.png")

print("\nAll figures saved.")
