# Triage Report


**10 run(s) analyzed. 3 incident pattern(s) detected. Top 3 worth your attention this morning.**

Sources: `events.ndjson`

---

## #1 - [planner] twoagent.planner / coordination_failure / no-divergence

**Category:** Coordination Failure

| Metric | Value |
|--------|-------|
| Severity Score | 10.00 / 15.00 |
| Frequency | 2 event(s) across 2 run(s) |
| Appeared in | 2/10 runs |
| Trend | resolved |
| Recovery Rate | [#####-----] 50% |
| Recovery Latency | median recovery latency: 1 turn |
| Tail Risk | 1 failure unrecovered after 10 turns |
| Confidence | medium (2 occurrences) |
| Final Score | **7.60** |

**Why this matters:**

Agent planner hit a **Coordination Failure** on `twoagent.planner` 2 time(s) across 2 runs. Appeared in 2/10 runs; the pattern appears to have resolved in recent runs. About 50% of occurrences were followed by a successful action within 3 turns (median latency 1 turn), suggesting partial self-correction. However, 1 failure remained unrecovered after 10 turns - a tail-risk signal. With a final score of 7.60, this pattern ranks high because its classification carries significant weight in the scoring model.

**Suggested next action:** Review inter-agent messaging cadence and add position-sync checkpoints before high-stakes joint actions.

---

## #2 - [worker] twoagent.worker / information_lag / no-divergence

**Category:** Information Lag

| Metric | Value |
|--------|-------|
| Severity Score | 5.00 / 15.00 |
| Frequency | 5 event(s) across 3 run(s) |
| Appeared in | 3/10 runs |
| Trend | stable |
| Recovery Rate | [######----] 60% |
| Recovery Latency | median recovery latency: 1 turn |
| Tail Risk | 2 failures unrecovered after 10 turns |
| Confidence | high (5 occurrences) |
| Final Score | **7.00** |

**Why this matters:**

Agent worker hit a **Information Lag** on `twoagent.worker` 5 time(s) across 3 runs. Appeared in 3/10 runs; trend is stable. About 60% of occurrences were followed by a successful action within 3 turns (median latency 1 turn), suggesting partial self-correction. However, 2 failures remained unrecovered after 10 turns - a tail-risk signal. With a final score of 7.00, this pattern ranks high because its classification carries significant weight in the scoring model.

**Suggested next action:** Increase belief-state refresh frequency or add an explicit re-observe step after N turns without a sync message.

---

## #3 - [worker] twoagent.worker / agent_error / no-divergence

**Category:** Agent Error

| Metric | Value |
|--------|-------|
| Severity Score | 7.00 / 15.00 |
| Frequency | 2 event(s) across 2 run(s) |
| Appeared in | 2/10 runs |
| Trend | new |
| Recovery Rate | [#####-----] 50% |
| Recovery Latency | median recovery latency: 1 turn |
| Tail Risk | 1 failure unrecovered after 10 turns |
| Confidence | medium (2 occurrences) |
| Final Score | **5.80** |

**Why this matters:**

Agent worker hit a **Agent Error** on `twoagent.worker` 2 time(s) across 2 runs. Appeared in 2/10 runs; this is a newly-emerging pattern. About 50% of occurrences were followed by a successful action within 3 turns (median latency 1 turn), suggesting partial self-correction. However, 1 failure remained unrecovered after 10 turns - a tail-risk signal. With a final score of 5.80, this pattern ranks high because its classification carries significant weight in the scoring model.

**Suggested next action:** Inspect the agent's reasoning trace at the failing turns; check if the action selection logic handles boundary states.

---

