# 06 - Adults in the Building

**Question:** Schools already employ supportive adults (counselors, psychologists, social
workers, nurses), alongside sworn officers. Are they distributed according to need, and do
schools that add them see less chronic absence? This complements Project 02's finding that
supportive adults and belonging go with engagement, and Project 03's mentoring design.

**Status:** complete (2026-11-14). All data public domain (U.S. Department of Education).

> **Exploratory.** Associations, not causal effects. Verify figures against the original
> sources before external use.

## Key findings

Civil Rights Data Collection, 2017-18 (85,166 regular public schools, 48.4 million students),
with 2015-16 for change over time.

1. **Support staffing is flat while need doubles.** In high schools, counselors per 1,000
   students are about the same in the lowest- and highest-poverty quarters (3.3 vs. 3.2), but
   chronic absence doubles (14% → 29%). Per **100 chronically absent students**, the
   highest-poverty high schools have **1.7 support staff**, against 3.7 in the lowest-poverty
   ones. Each counselor, psychologist, social worker or nurse there has roughly 60
   chronically absent students on top of everyone else.
2. **Officers rise with poverty; support staff don't.** Sworn officers per 1,000 high-school
   students rise from 0.45 to 0.69 (+53%) from the lowest- to the highest-poverty quarter.
3. **Gaps in coverage:** **8.0 million students** attend regular schools with no counselor;
   **1.04 million** attend schools with a sworn officer but no counselor. Only about a third
   of high schools meet the 250:1 student-to-counselor ratio recommended by the American
   School Counselor Association (verify the current recommendation).
4. **A snapshot misleads.** Comparing schools within the same district at one time, schools
   with more counselors, psychologists, social workers or officers have *more* chronic
   absence. Districts send staff where need is highest, so these numbers say nothing about
   what staff accomplish.
5. **Change over time finds no quick payoff from adding staff.** Across 72,918 schools in
   10,337 districts (2015-16 to 2017-18, within district), adding a counselor per 1,000
   students went with **no detectable change in chronic absence** (-0.06 points, CI -0.14 to
   +0.02). Adding officers went with slightly *more* (+0.23, CI +0.01 to +0.45).
   Psychologists and social workers: +0.10 (CI 0.01 to 0.20), plausibly still added in
   response to rising need.

**What it means for mentoring:** general support staff are spread across hundreds of
students each, and adding more of them hasn't measurably reduced chronic absence in the short
run. A personal, consistent adult relationship (mentoring) offers something different. It
should be evaluated directly (Project 03) rather than assumed from staffing data.

## Outputs

| File | What |
|---|---|
| `output/staffing_by_poverty.csv` | Staff per 1,000 students, coverage gaps, 250:1 share, staff per 100 chronically absent students, by poverty quarter (all schools and high schools) |
| `output/summary_counts.csv` | Students without a counselor; with an officer but no counselor |
| `output/within_district_associations.csv` | Snapshot associations (chronic absence, suspension, law-enforcement referrals) |
| `output/change_2016_to_2018.csv` | Change-over-time estimates (stronger design) |
| `output/change_sample_attrition.csv` | How many schools enter the change analysis at each step |
| `output/counselor_gainers_vs_others.csv` | Chronic absence in schools that added ≥0.5 counselors per 1,000 vs. others |
| `output/adults_in_the_building.png` | Figure |

## Rebuild

```bash
python3 -I scripts/fetch_data.py .
python3 -I scripts/01_adults_in_building.py   # ~10 seconds
```

## Method

- **Schools:** regular public schools (CCD school type) with 50+ students; justice facilities
  excluded. Staffing ratios capped at the 99th percentile.
- **Chronic absence:** students absent 15+ school days / enrollment (EDFacts file 814 in
  2017-18; CRDC `TOT_ABSENT` in 2015-16). School poverty: free/reduced-price lunch share (CCD).
- **Snapshot:** district fixed effects (within-district demeaning), weighted by enrollment,
  controls for poverty, log enrollment and school level; SEs clustered by district.
- **Change:** 2015-16 to 2017-18 differences in staffing per 1,000 and chronic absence,
  within district (district-specific trends), controlling for enrollment change; schools
  whose enrollment changed more than 30% excluded (likely boundary changes); weighted by
  average enrollment; SEs clustered by district.
- **Data fixes:** the 2015-16 file stores many school IDs in scientific notation, so keys are
  rebuilt from district + school IDs. In 2015-16 an officer count of -9 means "no officers"
  and is treated as 0.

## Caveats

- Two years is a short window; staff may affect attendance more slowly, or affect other
  outcomes (mental health, college applications) not measured here.
- Staff counts are FTEs assigned to a school, not time spent with students.
- 2017-18 is pre-pandemic. Chronic absence roughly doubled after 2020, so levels today are
  higher.

## License, citation and data terms

- **Code:** MIT (proposed; see `LICENSE`). **Outputs:** CC BY 4.0 (proposed), subject to the source terms below.
- **Cite this project as:** JonathanDoanePhD (2026). *Adults in the Building*. https://github.com/JonathanDoanePhD/adults-in-the-building
- **Data sources and terms** (from `data/sources.csv`; recorded versions and checksums in `data/sources.lock.csv`):

| Source | Terms |
|---|---|
| Civil Rights Data Collection 2017-18 (school level) | U.S. government work (public domain) |
| NCES Common Core of Data 2017-18 free/reduced-price lunch | U.S. government work (public domain) |
| NCES Common Core of Data 2017-18 school directory (level and locale) | U.S. government work (public domain) |
| Civil Rights Data Collection 2015-16 (school level; for change over time) | U.S. government work (public domain) |

Built with AI assistance (Claude). Exploratory research: every statistic needs checking against its original source
before it appears in funder reports, grant applications or public material.

## Before public release

- [ ] Every statistic in this README and in `output/` is checked against its original source.
- [ ] Verify the ASCA 250:1 recommendation citation.
- [ ] The owner confirms the license choice above.
