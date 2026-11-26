"""Adults in the Building: are support staff (counselors, psychologists, social workers, nurses)
distributed fairly, and do schools with more of them have less chronic absence?

Civil Rights Data Collection 2017-18 (the last pre-pandemic year), all public schools, with
NCES Common Core of Data 2017-18 for free/reduced-price lunch eligibility and school level.

Outcomes: chronic absence (students missing 15+ school days / enrollment); out-of-school
suspension (students with 1+ OSS / enrollment); referrals to law enforcement per 100 students.
Main design: compare schools WITHIN THE SAME DISTRICT (district fixed effects), which removes
district-wide policy, funding and reporting differences. Weighted by enrollment; SEs clustered
by district. Associations, not causal effects (schools with more needs may get more staff).

Run: python3 -I scripts/01_adults_in_building.py -> output/
"""
import glob
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)
SCH = glob.glob(str(RAW / "crdc" / "*" / "*Public-Use Files" / "Data" / "SCH"))[0]


def crdc(name, cols, folder="CRDC"):
    f = glob.glob(f"{SCH}/{folder}/CSV/{name}")[0]
    d = pd.read_csv(f, usecols=lambda c: c in cols, dtype={"COMBOKEY": str, "NCESSCH": str, "LEAID": str},
                    encoding="latin-1", low_memory=False)
    num = [c for c in d.columns if c not in ("COMBOKEY", "NCESSCH", "LEAID", "LEA_STATE", "JJ")]
    d[num] = d[num].apply(pd.to_numeric, errors="coerce")
    d[num] = d[num].where(d[num] >= 0)  # negative codes = not applicable / reserved
    return d


sup = crdc("School Support.csv", ["COMBOKEY", "LEAID", "LEA_STATE", "JJ", "SCH_FTETEACH_TOT", "SCH_FTECOUNSELORS",
                                  "SCH_FTESECURITY_LEO", "SCH_FTESECURITY_GUA", "SCH_FTESERVICES_NUR",
                                  "SCH_FTESERVICES_PSY", "SCH_FTESERVICES_SOC"])
enr = crdc("Enrollment.csv", ["COMBOKEY", "TOT_ENR_M", "TOT_ENR_F"])
enr["enrollment"] = enr.TOT_ENR_M + enr.TOT_ENR_F
susp_cols = ["COMBOKEY"] + [f"TOT_DISCWODIS_{k}_{s}" for k in ("SINGOOS", "MULTOOS") for s in "MF"] + \
            [f"TOT_DISCWDIS_{k}_IDEA_{s}" for k in ("SINGOOS", "MULTOOS") for s in "MF"]
susp = crdc("Suspensions.csv", susp_cols)
susp["oss_students"] = susp[susp_cols[1:]].sum(axis=1, min_count=1)
ref_cols = ["COMBOKEY", "TOT_DISCWODIS_REF_M", "TOT_DISCWODIS_REF_F", "TOT_DISCWDIS_REF_IDEA_M", "TOT_DISCWDIS_REF_IDEA_F"]
ref = crdc("Referrals and Arrests.csv", ref_cols)
ref["referrals"] = ref[ref_cols[1:]].sum(axis=1, min_count=1)
ca = crdc("ID 814 SCH - Chronic Absenteeism.csv", ["NCESSCH", "TOTAL_STUDENTS_REPORTED_M", "TOTAL_STUDENTS_REPORTED_F"], folder="EDFacts")
ca["chronic_absent"] = ca.TOTAL_STUDENTS_REPORTED_M + ca.TOTAL_STUDENTS_REPORTED_F
ca = ca.rename(columns={"NCESSCH": "COMBOKEY"})

# CCD: free/reduced lunch + school level
lunch = pd.read_csv(glob.glob(str(RAW / "ccd" / "ccd_sch_033_1718*.csv"))[0], dtype=str, encoding="latin-1",
                    usecols=["NCESSCH", "DATA_GROUP", "LUNCH_PROGRAM", "STUDENT_COUNT"])
frl = (lunch[(lunch.DATA_GROUP == "Free and Reduced-price Lunch Table")
             & lunch.LUNCH_PROGRAM.isin(["Free lunch qualified", "Reduced-price lunch qualified"])]
       .assign(n=lambda x: pd.to_numeric(x.STUDENT_COUNT, errors="coerce"))
       .groupby("NCESSCH").n.sum(min_count=1).rename("frl_count").reset_index())
dirc = pd.read_csv(glob.glob(str(RAW / "ccd" / "ccd_sch_029_1718*.csv"))[0], dtype=str, encoding="latin-1",
                   usecols=lambda c: c in ("NCESSCH", "LEVEL", "SCH_TYPE_TEXT", "SCH_TYPE"))

d = (sup.merge(enr[["COMBOKEY", "enrollment"]], on="COMBOKEY").merge(susp[["COMBOKEY", "oss_students"]], on="COMBOKEY", how="left")
     .merge(ref[["COMBOKEY", "referrals"]], on="COMBOKEY", how="left").merge(ca[["COMBOKEY", "chronic_absent"]], on="COMBOKEY", how="left")
     .merge(frl, left_on="COMBOKEY", right_on="NCESSCH", how="left").merge(dirc, on="NCESSCH", how="left"))
d = d[(d.JJ != "Yes") & (d.enrollment >= 50)].copy()  # exclude justice facilities and tiny schools
d["frl_share"] = (d.frl_count / d.enrollment).clip(upper=1)
d["level"] = d.LEVEL.fillna("Unknown")
per = lambda col, k=1000: d[col] / d.enrollment * k
d["counselors_per_1000"] = per("SCH_FTECOUNSELORS")
d["mental_health_per_1000"] = per("SCH_FTESERVICES_PSY").fillna(0) + per("SCH_FTESERVICES_SOC").fillna(0)
d["nurses_per_1000"] = per("SCH_FTESERVICES_NUR")
d["support_staff_per_1000"] = d[["counselors_per_1000", "mental_health_per_1000", "nurses_per_1000"]].sum(axis=1, min_count=1)
d["officers_per_1000"] = per("SCH_FTESECURITY_LEO")
# Regular schools only (alternative, special-education and CTE schools have very different
# staffing and needs), and cap each staffing ratio at its 99th percentile so data-entry
# extremes (e.g. district staff reported at one small school) can't drive the results.
d = d[d.SCH_TYPE_TEXT == "Regular School"].copy()
for c in ["counselors_per_1000", "mental_health_per_1000", "nurses_per_1000", "support_staff_per_1000", "officers_per_1000"]:
    d[c] = d[c].clip(upper=d[c].quantile(0.99))
d["students_per_counselor"] = d.enrollment / d.SCH_FTECOUNSELORS.where(d.SCH_FTECOUNSELORS > 0)
d["chronic_absence_pct"] = (d.chronic_absent / d.enrollment * 100).clip(upper=100)
d["oss_pct"] = (d.oss_students / d.enrollment * 100).clip(upper=100)
d["referrals_per_100"] = d.referrals / d.enrollment * 100
d["poverty_quartile"] = pd.qcut(d.frl_share, 4, labels=["Lowest-poverty quarter", "Q2", "Q3", "Highest-poverty quarter"])

# ---------------- 1. Staffing equity ----------------
def wavg(g, col):
    s = g[[col, "enrollment"]].dropna()
    return np.average(s[col], weights=s.enrollment) if len(s) else np.nan


eq = []
for lvl in ["All schools", "High"]:
    s = d if lvl == "All schools" else d[d.level == "High"]
    for q, g in s.groupby("poverty_quartile", observed=True):
        eq.append({"schools": "High schools" if lvl == "High" else lvl, "poverty_quartile": q, "n_schools": len(g),
                   "counselors_per_1000": wavg(g, "counselors_per_1000"), "mental_health_per_1000": wavg(g, "mental_health_per_1000"),
                   "nurses_per_1000": wavg(g, "nurses_per_1000"), "officers_per_1000": wavg(g, "officers_per_1000"),
                   "pct_no_counselor": (g.SCH_FTECOUNSELORS == 0).mean() * 100,
                   "pct_officer_but_no_counselor": ((g.SCH_FTESECURITY_LEO > 0) & (g.SCH_FTECOUNSELORS == 0)).mean() * 100,
                   "pct_meeting_250_to_1": (g.students_per_counselor <= 250).mean() * 100,
                   "chronic_absence_pct": wavg(g, "chronic_absence_pct"), "oss_pct": wavg(g, "oss_pct"),
                   # need-adjusted: support staff per 100 chronically absent students
                   "support_staff_per_100_chronically_absent": g.dropna(subset=["chronic_absent"])[["SCH_FTECOUNSELORS", "SCH_FTESERVICES_PSY", "SCH_FTESERVICES_SOC", "SCH_FTESERVICES_NUR"]].sum().sum()
                       / g.chronic_absent.sum() * 100})
eq = pd.DataFrame(eq)
eq.to_csv(OUT / "staffing_by_poverty.csv", index=False, float_format="%.2f")
summary = {"schools": len(d), "students": int(d.enrollment.sum()),
           "students_in_schools_without_counselor": int(d.loc[d.SCH_FTECOUNSELORS == 0, "enrollment"].sum()),
           "students_in_schools_with_officer_no_counselor": int(d.loc[(d.SCH_FTESECURITY_LEO > 0) & (d.SCH_FTECOUNSELORS == 0), "enrollment"].sum()),
           "students_in_schools_with_officer_no_mental_health": int(d.loc[(d.SCH_FTESECURITY_LEO > 0) & (d.mental_health_per_1000 == 0) & (d.SCH_FTECOUNSELORS == 0), "enrollment"].sum())}
pd.Series(summary).to_csv(OUT / "summary_counts.csv", header=["value"])

# ---------------- 2. Within-district associations ----------------
def within_district(y, xs, data):
    s = data.dropna(subset=[y, "frl_share", "enrollment", "LEAID"] + xs).copy()
    s = s[s.groupby("LEAID").LEAID.transform("size") >= 2]  # need 2+ schools to compare within district
    cols = xs + ["frl_share", "log_enr"]
    s["log_enr"] = np.log(s.enrollment)
    lvl = pd.get_dummies(s.level, prefix="lvl", drop_first=True, dtype=float)
    Z = pd.concat([s[cols], lvl], axis=1)
    # demean within district (weighted) = district fixed effects
    w = s.enrollment
    dm = lambda v: v - (v * w).groupby(s.LEAID).transform("sum") / w.groupby(s.LEAID).transform("sum")
    yd = dm(s[y]); Zd = Z.apply(dm)
    keep = Zd.columns[Zd.abs().sum() > 0]
    r = sm.WLS(yd, Zd[keep], weights=w).fit(cov_type="cluster", cov_kwds={"groups": s.LEAID})
    return r, s


rows = []
specs = [("chronic_absence_pct", "Chronic absence (% of students)", ["counselors_per_1000"]),
         ("chronic_absence_pct", "Chronic absence (% of students)", ["counselors_per_1000", "mental_health_per_1000", "nurses_per_1000", "officers_per_1000"]),
         ("oss_pct", "Out-of-school suspension (% of students)", ["counselors_per_1000", "mental_health_per_1000", "nurses_per_1000", "officers_per_1000"]),
         ("referrals_per_100", "Referrals to law enforcement per 100 students", ["counselors_per_1000", "mental_health_per_1000", "nurses_per_1000", "officers_per_1000"])]
for sample, data in [("All schools", d), ("High schools", d[d.level == "High"]), ("High-poverty half", d[d.frl_share >= d.frl_share.median()])]:
    for y, ylab, xs in specs:
        r, s = within_district(y, xs, data)
        for x in xs:
            rows.append({"sample": sample, "outcome": ylab, "model": "+ other staff" if len(xs) > 1 else "counselors only",
                         "term": x, "per_one_more_fte_per_1000": r.params[x], "ci_low": r.conf_int().loc[x, 0],
                         "ci_high": r.conf_int().loc[x, 1], "n_schools": int(r.nobs), "n_districts": s.LEAID.nunique()})
assoc = pd.DataFrame(rows)
assoc.to_csv(OUT / "within_district_associations.csv", index=False, float_format="%.4f")

# ---------------- 3. Change over time: 2015-16 -> 2017-18 (same schools) ----------------
# A stronger test than a snapshot: did schools that GAINED support staff see chronic absence
# fall relative to other schools in the same district? Still observational (staff may be
# added because need is rising), but it removes fixed differences between schools.
f16 = glob.glob(str(RAW / "crdc1516" / "*" / "CRDC 2015-16 School Data.csv"))[0]
c16 = ["LEAID", "SCHID", "JJ", "TOT_ENR_M", "TOT_ENR_F", "TOT_ABSENT_M", "TOT_ABSENT_F", "SCH_FTECOUNSELORS",
       "SCH_FTESECURITY_LEO", "SCH_FTESERVICES_NUR", "SCH_FTESERVICES_PSY", "SCH_FTESERVICES_SOC"]
p16 = pd.read_csv(f16, usecols=c16, dtype={"LEAID": str, "SCHID": str}, encoding="latin-1", low_memory=False)
num16 = c16[2:]
p16[num16] = p16[num16].apply(pd.to_numeric, errors="coerce")
# 2015-16 skips the officer count (-9) when a school reports no sworn officers: that is zero
p16["SCH_FTESECURITY_LEO"] = p16.SCH_FTESECURITY_LEO.replace(-9, 0)
p16[num16] = p16[num16].where(p16[num16] >= 0)
# The 2015-16 file stores COMBOKEY in scientific notation for many states (e.g. "1.2E+11"),
# so rebuild the 12-digit key from the 7-digit district ID and 5-digit school ID.
p16["COMBOKEY"] = p16.LEAID.str.zfill(7) + p16.SCHID.str.zfill(5)
p16["enr16"] = p16.TOT_ENR_M + p16.TOT_ENR_F
p16 = p16[(p16.JJ != "Yes") & (p16.enr16 >= 50)]
p16["chronic16"] = ((p16.TOT_ABSENT_M + p16.TOT_ABSENT_F) / p16.enr16 * 100).clip(upper=100)
p16["couns16"] = p16.SCH_FTECOUNSELORS / p16.enr16 * 1000
p16["mh16"] = (p16.SCH_FTESERVICES_PSY.fillna(0) + p16.SCH_FTESERVICES_SOC.fillna(0)) / p16.enr16 * 1000
p16["nurse16"] = p16.SCH_FTESERVICES_NUR / p16.enr16 * 1000
p16["off16"] = p16.SCH_FTESECURITY_LEO / p16.enr16 * 1000
pan = d.merge(p16[["COMBOKEY", "enr16", "chronic16", "couns16", "mh16", "nurse16", "off16"]], on="COMBOKEY")
attrition = {"schools_2017_18": len(d), "also_in_2015_16": len(pan)}
pan = pan[(pan.enrollment / pan.enr16).between(0.7, 1.3)].copy()  # skip boundary changes / mergers
attrition["stable_enrollment"] = len(pan)
pan["d_chronic"] = pan.chronic_absence_pct - pan.chronic16
for new, old, nm in [("counselors_per_1000", "couns16", "d_couns"), ("mental_health_per_1000", "mh16", "d_mh"),
                     ("nurses_per_1000", "nurse16", "d_nurse"), ("officers_per_1000", "off16", "d_off")]:
    pan[nm] = (pan[new] - pan[old]).clip(*(pan[new] - pan[old]).quantile([0.01, 0.99]))
pan["d_logenr"] = np.log(pan.enrollment) - np.log(pan.enr16)
attrition.update({f"missing_{c}": int(pan[c].isna().sum()) for c in ["d_chronic", "d_couns", "d_mh", "d_nurse", "d_off"]})
pan = pan.dropna(subset=["d_chronic", "d_couns", "d_mh", "d_nurse", "d_off", "LEAID"])
attrition["complete"] = len(pan)
pan = pan[pan.groupby("LEAID").LEAID.transform("size") >= 2]
attrition["in_districts_with_2plus"] = len(pan)
pd.Series(attrition).to_csv(OUT / "change_sample_attrition.csv", header=["schools"])
w = (pan.enrollment + pan.enr16) / 2
dm = lambda v: v - (v * w).groupby(pan.LEAID).transform("sum") / w.groupby(pan.LEAID).transform("sum")
Xp = pan[["d_couns", "d_mh", "d_nurse", "d_off", "d_logenr"]].apply(dm)
rp = sm.WLS(dm(pan.d_chronic), Xp, weights=w).fit(cov_type="cluster", cov_kwds={"groups": pan.LEAID})
change = pd.DataFrame({"term": ["Counselors", "Psychologists + social workers", "Nurses", "Sworn officers", "log enrollment"],
                       "per_one_more_fte_per_1000": rp.params.values, "ci_low": rp.conf_int()[0].values,
                       "ci_high": rp.conf_int()[1].values})
change["n_schools"], change["n_districts"] = int(rp.nobs), pan.LEAID.nunique()
change.to_csv(OUT / "change_2016_to_2018.csv", index=False, float_format="%.4f")
gainers = pan.assign(gained=pan.d_couns >= 0.5)
gain_tab = gainers.groupby("gained").apply(lambda g: pd.Series({
    "schools": len(g), "chronic_2016": np.average(g.chronic16, weights=g.enr16),
    "chronic_2018": np.average(g.chronic_absence_pct, weights=g.enrollment)}), include_groups=False)
gain_tab.to_csv(OUT / "counselor_gainers_vs_others.csv", float_format="%.2f")

# ---------------- Figure ----------------
SURFACE, TEXT, TEXT2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
COL = {"counselors_per_1000": "#2a78d6", "mental_health_per_1000": "#1baf7a", "nurses_per_1000": "#6250d6", "officers_per_1000": "#eb6834"}
NAME = {"counselors_per_1000": "Counselors", "mental_health_per_1000": "Psychologists + social workers",
        "nurses_per_1000": "Nurses", "officers_per_1000": "Sworn law enforcement officers"}
hs = eq[eq.schools == "High schools"].reset_index(drop=True)
fig, axes = plt.subplots(1, 2, figsize=(13, 5.4), dpi=100, gridspec_kw={"width_ratios": [1.2, 1]})
fig.patch.set_facecolor(SURFACE)
ax = axes[0]; ax.set_facecolor(SURFACE)
x = np.arange(4)
for k, col in enumerate(COL):
    ax.bar(x + (k - 1.5) * 0.2, hs[col], width=0.19, color=COL[col], label=NAME[col])
ax.set_xticks(x, ["Lowest\npoverty", "Q2", "Q3", "Highest\npoverty"])
ax.set_ylabel("Full-time staff per 1,000 students", color=TEXT2)
ax.set_title("High schools: support staff vs. officers, by school poverty", loc="left", color=TEXT, fontsize=12)
ax.set_ylim(0, 4.6)
ax.legend(frameon=False, labelcolor=TEXT, fontsize=9.5, ncol=2, loc="upper left")
ax2 = axes[1]; ax2.set_facecolor(SURFACE)
snap = assoc[(assoc["sample"] == "All schools") & assoc.outcome.str.startswith("Chronic") & (assoc.model == "+ other staff")].set_index("term")
chg = change.set_index("term")
order = [("counselors_per_1000", "Counselors"), ("mental_health_per_1000", "Psychologists + social workers"),
         ("nurses_per_1000", "Nurses"), ("officers_per_1000", "Sworn officers")]
for k, (col, nm) in enumerate(order):
    pairs = [(snap.loc[col, "per_one_more_fte_per_1000"], snap.loc[col, "ci_low"], snap.loc[col, "ci_high"], "o",
              "Snapshot 2017-18 (same district)"),
             (chg.loc[nm, "per_one_more_fte_per_1000"], chg.loc[nm, "ci_low"], chg.loc[nm, "ci_high"], "D",
              "Change 2015-16 to 2017-18 (same district)")]
    for j, (est, lo, hi, mk, lab) in enumerate(pairs):
        y = k + (j - 0.5) * 0.3
        c = COL[col] if j else TEXT2
        ax2.errorbar(est, y, xerr=[[est - lo], [hi - est]], fmt=mk, ms=6.5, color=c, ecolor=c, elinewidth=2,
                     mfc=c if j else "none", label=lab if k == 0 else None)
ax2.axvline(0, color=TEXT2, lw=0.8)
ax2.set_yticks(range(4), [nm for _, nm in order])
ax2.invert_yaxis()
ax2.legend(frameon=False, labelcolor=TEXT, fontsize=9, loc="upper right")
ax2.set_xlabel("Chronic absence (pct. points) per +1 staff per 1,000 students", color=TEXT2)
ax2.set_title("Snapshots mislead: staff go where need is", loc="left", color=TEXT, fontsize=12)
for a_ in axes:
    a_.grid(axis="y" if a_ is ax else "x", color=GRID, lw=0.6); a_.set_axisbelow(True)
    for s_ in ["top", "right"]:
        a_.spines[s_].set_visible(False)
    a_.tick_params(colors=TEXT2)
fig.text(0.02, 0.955, "Support staff are spread evenly while need doubles, and adding them has not moved chronic absence",
         fontsize=13.5, weight="bold", color=TEXT)
fig.text(0.02, 0.012, "Civil Rights Data Collection 2015-16 and 2017-18; NCES CCD 2017-18. Weighted by enrollment; district fixed effects; SEs clustered by district. "
         "Associations, not causal effects. Verify before external use.", fontsize=8.5, color=TEXT2)
fig.subplots_adjust(left=0.06, right=0.98, top=0.86, bottom=0.14, wspace=0.32)
fig.savefig(OUT / "adults_in_the_building.png", dpi=150, facecolor=SURFACE)

pd.set_option("display.width", 220)
print(summary)
print(eq.round(2).to_string(index=False))
print(assoc.round(3).to_string(index=False))
print(change.round(3).to_string(index=False))
print(gain_tab.round(2).to_string())
