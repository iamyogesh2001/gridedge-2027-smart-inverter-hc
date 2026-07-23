"""
IEEE PES Grid Edge 2027 — Smart Inverter Hosting Capacity Study
================================================================
Authors : Yogesh Rethinapandian, University of Illinois Chicago
Network : IEEE 33-bus radial distribution test system (Baran & Wu, 1989)
          12.66 kV | 3,715 kW | 2,300 kVAR total load
Standard: IEEE 1547-2018 Category B inverter operating modes
Solver  : pandapower backward-forward sweep (BFS)
Voltage constraint: ANSI C84.1 Range A  Vmax = 1.05 pu

Modes evaluated
---------------
1. Unity PF           — baseline, Q = 0
2. Fixed PF 0.95      — absorb Q continuously, PF = 0.95 leading
3. Volt-Var (VV)      — IEEE 1547-2018 Table 8 Cat-B curve, damped iteration
4. Volt-Watt (VW)     — IEEE 1547-2018 Table 9 Cat-B curve, damped iteration
5. Combined VV+VW     — both loops active, damped iteration

Output
------
simulation/results.npz   — all raw arrays
figures/fig*.pdf + png   — publication-quality figures
"""

import numpy as np
import pandapower as pp
import pandapower.networks as pn
import warnings, pickle, time
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────
PV_BUS    = 17          # worst-case voltage bus (Vmin in base case)
ANSI_VMAX = 1.05        # pu — ANSI C84.1 Range A upper limit
ANSI_VMIN = 0.95        # pu
ALPHA     = 0.30        # damping factor for control iterations
MAX_ITER  = 40          # max control loop iterations
TOL       = 5e-4        # convergence tolerance (pu of rated)

# IEEE 1547-2018 Category B Volt-Var curve (Table 8)
VV_V = np.array([0.92, 0.98, 1.02, 1.08])   # voltage breakpoints (pu)
VV_Q = np.array([1.0,  0.0,  0.0, -1.0])    # Q/Qrated (+inject / -absorb)

# IEEE 1547-2018 Category B Volt-Watt curve (Table 9)
VW_V = np.array([1.05, 1.10])               # voltage breakpoints (pu)
VW_P = np.array([1.0,  0.0])               # P/Prated

# Penetration sweep: 0 → 200% of peak feeder load in 2.5% steps
PEN_STEPS = np.arange(0.0, 2.01, 0.025)

# ─────────────────────────────────────────────
# FEEDER SETUP
# ─────────────────────────────────────────────
def fresh_net():
    """Return a clean IEEE 33-bus network every call (pandapower modifies in place)."""
    return pn.case33bw()

_ref = fresh_net()
pp.runpp(_ref, algorithm="bfsw", numba=False)
TOTAL_KW   = _ref.load.p_mw.sum() * 1000       # 3715.0 kW
BASE_VPROF = _ref.res_bus.vm_pu.to_numpy().copy()
BASE_VMIN  = BASE_VPROF[PV_BUS]               # 0.9131 pu

print(f"IEEE 33-bus  |  Load = {TOTAL_KW:.0f} kW  |  PV bus = {PV_BUS}")
print(f"Base Vmin = {BASE_VMIN:.4f} pu  |  Sweep: {len(PEN_STEPS)} steps  "
      f"(0–{PEN_STEPS[-1]*100:.0f}% in {(PEN_STEPS[1]-PEN_STEPS[0])*100:.1f}% increments)\n")

# ─────────────────────────────────────────────
# CONTROL LOOP ENGINE
# ─────────────────────────────────────────────
def power_flow(pv_kw, mode):
    """
    Run one power-flow scenario with smart-inverter control loop.
    Returns (Vmax, Vmin, Vprofile[33], pw_actual, qv_actual, converged)
    """
    if pv_kw <= 0.0:
        n = fresh_net()
        pp.runpp(n, algorithm="bfsw", numba=False)
        return (n.res_bus.vm_pu.max(), n.res_bus.vm_pu.min(),
                n.res_bus.vm_pu.to_numpy(), 0.0, 0.0, True)

    # Rated reactive capability (Cat-B minimum: PF ≥ 0.90)
    kvar_rated = pv_kw * np.tan(np.arccos(0.90))   # ~0.484 * pv_kw

    # Initial operating point
    pw = pv_kw
    if mode == "fixed_pf":
        qv = -pv_kw * np.tan(np.arccos(0.95))      # absorb Q (negative)
    else:
        qv = 0.0

    iters = 1 if mode in ("unity", "fixed_pf") else MAX_ITER

    n = fresh_net()   # will be overwritten each iteration
    for _ in range(iters):
        n = fresh_net()
        try:
            pp.create_sgen(n, bus=PV_BUS,
                           p_mw=pw / 1000.0,
                           q_mvar=qv / 1000.0)     # positive = inject Q
            pp.runpp(n, algorithm="bfsw", numba=False)
        except Exception:
            return (np.nan, np.nan, np.full(33, np.nan), pw, qv, False)

        v_pv = float(n.res_bus.vm_pu.iloc[PV_BUS])

        if mode == "volt_var":
            qv_new = np.interp(v_pv, VV_V, VV_Q) * kvar_rated
            # negative qv_new = absorbing Q = reducing voltage
            if abs(qv_new - qv) < TOL * kvar_rated:
                qv = qv_new; break
            qv = (1 - ALPHA) * qv + ALPHA * qv_new

        elif mode == "volt_watt":
            pw_new = np.interp(v_pv, VW_V, VW_P, left=1.0, right=0.0) * pv_kw
            if abs(pw_new - pw) < TOL * pv_kw:
                pw = pw_new; break
            pw = (1 - ALPHA) * pw + ALPHA * pw_new
            qv = 0.0

        elif mode == "combined":
            qv_new = np.interp(v_pv, VV_V, VV_Q) * kvar_rated
            pw_new = np.interp(v_pv, VW_V, VW_P, left=1.0, right=0.0) * pv_kw
            dq = abs(qv_new - qv) / max(kvar_rated, 1e-6)
            dp = abs(pw_new - pw) / max(pv_kw, 1e-6)
            if dq < TOL and dp < TOL:
                qv = qv_new; pw = pw_new; break
            qv = (1 - ALPHA) * qv + ALPHA * qv_new
            pw = (1 - ALPHA) * pw + ALPHA * pw_new

        else:
            break   # unity / fixed_pf: single-shot

    vmax = float(n.res_bus.vm_pu.max())
    vmin = float(n.res_bus.vm_pu.min())
    vp   = n.res_bus.vm_pu.to_numpy().copy()
    return vmax, vmin, vp, pw, qv, True

# ─────────────────────────────────────────────
# MAIN SWEEP
# ─────────────────────────────────────────────
MODES = {
    "Unity PF":       "unity",
    "Fixed PF 0.95":  "fixed_pf",
    "Volt-Var":       "volt_var",
    "Volt-Watt":      "volt_watt",
    "Combined VV+VW": "combined",
}

results = {}
t0 = time.time()

for label, mode in MODES.items():
    print(f"  Running: {label} ...", end="", flush=True)
    t1 = time.time()

    vmax_arr, vmin_arr, vprof_arr = [], [], []
    pw_arr, qv_arr, ok_arr = [], [], []

    for pct in PEN_STEPS:
        pv_kw = pct * TOTAL_KW
        vmax, vmin, vp, pw, qv, conv = power_flow(pv_kw, mode)
        vmax_arr.append(vmax)
        vmin_arr.append(vmin)
        vprof_arr.append(vp)
        pw_arr.append(pw)
        qv_arr.append(qv)
        ok_arr.append(conv and not np.isnan(vmax) and vmax <= ANSI_VMAX)

    # Hosting capacity = last penetration that stays within ANSI limit
    valid = [i for i, ok in enumerate(ok_arr) if ok]
    hc_pct = PEN_STEPS[max(valid)] * 100.0 if valid else 0.0

    results[label] = dict(
        mode=mode,
        hc_pct=hc_pct,
        vmax=np.array(vmax_arr),
        vmin=np.array(vmin_arr),
        vprof=np.array(vprof_arr),
        pw=np.array(pw_arr),
        qv=np.array(qv_arr),
        ok=np.array(ok_arr),
    )
    print(f"  HC = {hc_pct:.1f}%  ({time.time()-t1:.1f}s)")

print(f"\nTotal runtime: {time.time()-t0:.1f}s")

# ─────────────────────────────────────────────
# SUMMARY TABLE
# ─────────────────────────────────────────────
base_hc = results["Unity PF"]["hc_pct"]
print("\n" + "="*65)
print(f"{'Mode':<22} {'HC (%)':>8} {'Gain':>8} {'Vmax @200%':>12}")
print("-"*65)
for label, r in results.items():
    vm200_idx = np.argmin(np.abs(PEN_STEPS - 2.0))
    vm200 = r["vmax"][vm200_idx]
    gain  = r["hc_pct"] - base_hc
    vmstr = f"{vm200:.4f}" if not np.isnan(vm200) else "  n/a  "
    print(f"  {label:<20} {r['hc_pct']:>8.1f}% {gain:>+7.1f}%  {vmstr:>12}")
print("="*65)

# ─────────────────────────────────────────────
# SAVE
# ─────────────────────────────────────────────
save_path = "/home/claude/gridedge/simulation/results.pkl"
with open(save_path, "wb") as f:
    pickle.dump({
        "results":   results,
        "PEN_STEPS": PEN_STEPS,
        "TOTAL_KW":  TOTAL_KW,
        "BASE_VPROF":BASE_VPROF,
        "BASE_VMIN": BASE_VMIN,
        "PV_BUS":    PV_BUS,
        "ANSI_VMAX": ANSI_VMAX,
        "ANSI_VMIN": ANSI_VMIN,
        "VV_V": VV_V, "VV_Q": VV_Q,
        "VW_V": VW_V, "VW_P": VW_P,
    }, f)
print(f"\n✓  Results saved → {save_path}")
