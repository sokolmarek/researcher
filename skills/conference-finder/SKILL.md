---
name: conference-finder
description: "Find relevant academic conferences and workshops for paper submission. Triggers: find conference, conference deadline, where to present, CFP, call for papers, upcoming conferences, submit to conference, conference recommendation, workshop deadline, which venue has a submission window still open. Venue discovery only: it finds where the work could be presented and does not write, schedule, or typeset anything."
---

# Conference Finder

Discover and evaluate academic conferences and workshops that match a paper's topic, with deadline tracking and ranking information.

## CRITICAL INTEGRITY RULE
**NEVER fabricate conference details.** Deadlines, acceptance rates, rankings, and dates must come from official CFPs, conference websites, or trusted aggregation sites (WikiCFP, CORE rankings portal). If information is unavailable or potentially outdated, state so explicitly.

## Workflow

1. **Analyze paper profile**: read title, abstract, keywords from `manuscript/config.yaml` or user input to determine field and subfield
2. **Search conference sources** via web search:
   - WikiCFP (wikicfp.com): call for papers aggregator
   - CORE Conference Rankings (portal.core.edu.au): A*/A/B/C rankings
   - Conference websites directly: official deadlines and topics
   - DBLP (dblp.org): past proceedings and conference history
   - Publisher portals (IEEE Xplore, ACM DL, Springer LNCS): series metadata
3. **Filter by constraints**: deadline feasibility, ranking, location, format
4. **Rank conferences** by topic match, prestige, and practical fit
5. **Present results** with all actionable details

## Input Modes

### From Manuscript
When a `manuscript/` folder exists, automatically extract topic, field, and keywords from the current manuscript state.

### From Description
User provides topic description and optionally:
- Target field or discipline
- Minimum ranking (e.g., "A* or A only")
- Deadline window (e.g., "deadlines in the next 3 months")
- Preferred location or region
- Virtual/hybrid preference

## Recommendation Format

Return 5-10 conferences, ranked by overall fit:

```
[1] NeurIPS 2026: Conference on Neural Information Processing Systems
    Dates:          Dec 7-13, 2026 | Vancouver, Canada
    Format:         In-person + virtual
    Submission:     May 15, 2026 (abstracts) | May 22, 2026 (full papers)
    Notification:   Sep 10, 2026
    CORE Ranking:   A*
    Acceptance Rate: ~26% (2025)
    Publisher:      Curran Associates (proceedings on NeurIPS.cc)
    Topics:         Deep learning, optimization, generative models,
                    reinforcement learning, theory, applications
    Scope Match:    HIGH (flagship venue for machine learning research;
                    strong fit for novel learning algorithm papers)
    Related Events: Workshop submission deadline: Sep 25, 2026
    Website:        https://neurips.cc
```

## Scoring Dimensions

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Topic match | 35% | Alignment between paper topic and conference scope |
| Ranking / prestige | 25% | CORE ranking, community reputation, citation impact |
| Deadline feasibility | 15% | Enough time to prepare and submit |
| Acceptance rate | 10% | Realistic chance of acceptance given paper quality |
| Practical factors | 15% | Location, cost, format (virtual option), visa considerations |

## User Filters

Support these filter parameters as hard constraints:

- `--ranking A*,A`: restrict to specific CORE rankings
- `--deadline-before 2026-06-01`: only conferences with submission before date
- `--deadline-after 2026-04-01`: only conferences with submission after date
- `--location europe`: restrict by region or country
- `--virtual`: only conferences with virtual attendance option
- `--field "natural language processing"`: override auto-detected field
- `--publisher IEEE,ACM`: restrict to specific publishers

## Deadline Tracking

When the user expresses interest in specific conferences:
- Add to a tracked list in `manuscript/config.yaml` under `target_conferences`
- Record: name, submission deadline, notification date, camera-ready deadline
- On subsequent invocations, remind the user of upcoming deadlines
- Sort tracked conferences by nearest deadline first

## Workshop and Collocated Event Discovery

For each recommended conference, also search for:
- Collocated workshops accepting papers on the specific subtopic
- Doctoral consortia or mentoring events
- Shared tasks or competitions related to the research area
- Tutorial proposals if the user has a mature line of work

Present workshops with their own deadlines and scope descriptions.

## Conference History Analysis

When evaluating a conference, provide context from past editions:
- Acceptance rate trend (improving or declining selectivity)
- Best paper topics from recent years (to gauge topical fit)
- Proceedings indexed in (Scopus, Web of Science, DBLP, ACM DL)
- Whether the conference has moved venues or changed format recently

## Comparison Mode

For side-by-side evaluation of specific conferences:

```
| Criterion        | Conf A (NeurIPS) | Conf B (ICML) | Conf C (AAAI) |
|------------------|------------------|---------------|---------------|
| CORE Ranking     | A*               | A*            | A*            |
| Deadline         | May 22, 2026     | Jan 30, 2026  | Aug 15, 2026  |
| Notification     | Sep 10, 2026     | May 1, 2026   | Nov 20, 2026  |
| Acceptance Rate  | ~26%             | ~28%          | ~24%          |
| Location         | Vancouver        | Vienna        | Philadelphia  |
| Format           | Hybrid           | In-person     | Hybrid        |
| Topic Fit        | HIGH             | HIGH          | MEDIUM        |
```

## Integration with Other Skills

- **journal-formatting**: apply conference template requirements (page limits, formatting)
- **cover-letter**: adapt for conference submissions (shorter, focused on contribution)
- **literature-search**: papers from recent editions of a conference indicate topical fit
- **journal-finder**: if no suitable conference is found, suggest journal alternatives and vice versa

## References

Use web search to access current CFPs and deadlines. Cross-reference CORE rankings portal for official ranking data. Conference deadlines change annually, so always verify against the official website.
