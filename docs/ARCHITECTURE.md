# Architecture

Review Radar is a small system with one expensive, unreliable dependency (an LLM) and one irreversible action (posting a public reply). Most of the design follows from keeping the first replaceable and the second deliberate.

## Layout

```
backend/src/review_radar/
  domain/        pure models and logic: triage schema, z-test + Holm, clustering,
                 reply state machine, eval metrics. No IO, no framework imports.
  application/   use cases (ingest, triage, embed, themes, compare, draft, review, post)
                 and the Protocol ports they depend on. Read models for the API.
  adapters/      Postgres (SQLAlchemy async), App Store Connect, Google Play,
                 PydanticAI agents, embedders, reply publishers.
  api/           FastAPI routers, dependency providers and the error envelope.
  container.py   the composition root: the only module that picks concrete adapters.
web/src/
  components/ui  shared primitives (Card, Stat, Badge, Table, EmptyState, Button, charts)
  pages/         one file per dashboard view
  api/           generated OpenAPI types, a typed fetch client and TanStack Query hooks
```

Dependencies point inward: `api` and `adapters` import `application` and `domain`; `domain` imports nothing of ours except itself. Ports are `typing.Protocol`, so adapters and test fakes conform structurally and mypy checks them. The container is built inside the FastAPI lifespan (or a CLI command) and handed down explicitly; nothing reads a global.

The write side goes through a unit of work (one transaction, repositories sharing a session, nothing committed implicitly). The dashboard's reads go through a separate `ReadModel` port that returns response models directly. Routers call it without a use case in between, because a pass-through use case per query would be ceremony with no behaviour in it.

## ADR-001: PydanticAI rather than LangGraph

**Decision.** Each model task is a PydanticAI `Agent` with a typed `output_type` (`Triage`, `ReplyText`, `ThemeTitle`), built per adapter instance with the model injected.

**Why.** Every model call here is a single-step, structured transformation: review in, typed verdict out. The hard parts are validation (a reply must fit 350 characters, a category must be one of eight), retries, and cost accounting, and PydanticAI covers exactly those: the output schema doubles as the tool schema, `output_validator` + `ModelRetry` asks the model to fix an over-long reply instead of truncating it, and each run reports usage that `genai-prices` turns into a cost. `FunctionModel` means demo mode uses the same agents, prompts and validators with only the model swapped. That makes the offline mode an honest test of the pipeline rather than a second code path.

**Rejected: LangGraph.** A graph runtime earns its keep when the control flow is dynamic: branching on model output, loops, human-in-the-loop interrupts inside a run. Here the flow is a fixed pipeline, and the human step happens days later in a web UI, not mid-run. Modelling it as a graph would add a state schema and checkpointer that duplicate what Postgres already stores, and the typed-output story is weaker.

**Rejected: raw provider SDK with JSON mode.** It works for one provider. Switching to another would mean rewriting parsing and retries, and there would be no offline model to test against.

## ADR-002: pgvector in the primary database

**Decision.** Summary embeddings live in a `vector(256)` column on `triages`, with an HNSW cosine index. Theme centroids are stored as vectors too.

**Why.** The corpus is thousands of reviews per app, not billions. Keeping vectors next to the rows they describe means one transaction covers "triage saved, embedding cleared", similarity queries can join and filter on store, version and category in SQL, and there is one database to back up. 256 dimensions is enough for short summaries; OpenAI's `text-embedding-3` models take a `dimensions` argument, so real and demo embeddings share one schema.

**Rejected: a dedicated vector store (Pinecone, Qdrant).** It adds a second source of truth that has to be kept consistent with Postgres, and it buys scale this workload doesn't need.

**Rejected: in-memory only.** Clustering itself runs in memory (numpy, O(n^2)), but persisted vectors are what make "similar reviews" instant and let the roadmap assign new reviews to existing themes without re-embedding.

**Clustering.** Average-linkage agglomerative clustering with a cosine distance cut-off (0.35), minimum theme size 4. I chose it over k-means because the number of themes is the unknown, and a distance threshold is easier to reason about than *k*. It is deterministic, which keeps demo mode and tests reproducible. Its limits: quadratic memory, and one global threshold. Both are fine at this scale and are called out in the roadmap.

## ADR-003: Regression statistics

**Question.** Did release N make some kind of complaint more common than release N-1?

**Unit.** For each segment (every problem category, and every theme whose dominant category is a problem) the statistic is the share of that release's triaged reviews that fall in the segment. Shares, not counts: release sizes differ, and a release that gets twice the reviews shouldn't look twice as broken.

**Test.** A one-sided pooled two-proportion z-test, H1: p(N) > p(N-1).

```
p̂ = (x₁ + x₂) / (n₁ + n₂)
z = (x₂/n₂ − x₁/n₁) / sqrt(p̂(1 − p̂)(1/n₁ + 1/n₂))
p = P(Z > z)
```

It is one-sided because a drop in complaints is good news, not an alert.

**Multiple comparisons.** Each comparison runs about 15 to 20 tests at once. At α = 0.01 without correction, a release would show a false alarm roughly one time in six. Holm-Bonferroni adjusts the p-values to control the family-wise error rate. It is uniformly more powerful than plain Bonferroni and needs no independence assumption, which matters because categories and themes overlap.

**Gates.** A segment is flagged only when all three hold:

1. adjusted p < 0.01 (the rise is unlikely to be noise),
2. rate ratio ≥ 2 (the effect is big enough to act on),
3. at least 5 reviews in the new release (enough to read).

Significance alone fires on tiny effects once volume is large. Ratio alone fires on 1 → 3 reviews. When a count is zero, the ratio uses a +0.5 (Haldane-Anscombe) correction, so "0 to 12" reports a large finite ratio instead of infinity.

**Rejected: chi-square.** For a 2x2 table it is the square of the two-sided z-test, so it adds nothing and loses the direction.

**Rejected: Fisher's exact test.** It is more accurate at very small counts, but the minimum-count gate already excludes the cases where the normal approximation is weakest, and the z statistic is easier to show and explain in the UI. If the gates are ever relaxed, switch to Fisher's exact test.

**Known limitation.** Reviews for a version keep arriving after the next release ships, and early reviewers of a release skew negative. The test compares whatever each release has collected so far. In production I would compare equal windows (for example, the first 7 days of each release).

**Result on the demo data.** 2.3.0 against 2.2.0 flags the theme "App crashes when signing in" (2.2% → 30%, 13.5x, adjusted p < 0.0001) and the Crash category (4.5x, adjusted p 0.0008). Login / auth rises 3.9x but misses the bar (adjusted p 0.063). 2.3.1 flags nothing. The redesigned widget theme in 2.4.0 rises 9.3x on small counts and misses the bar after correction (adjusted p 0.056). That is the correction doing its job: it could be real, and a person looking at the table can see it, but it isn't an alert.

## ADR-004: Approval gating for replies

**Decision.** Replies move through an explicit state machine, and the only way to change a reply is through `domain.replies.apply`, which returns the new reply and the audit entry to write with it.

```
draft ──approve──▶ approved ──post──▶ posted
  │                   │  ▲
  ├──edit──▶ edited ◀─┘  │ (dry run) ──▶ would_post ──post──▶ posted
  │            └──post───┘
  └──reject──▶ rejected ──redraft──▶ draft
```

Guarantees, layered so that no single bug can post an unreviewed reply:

1. **Domain.** `post` is only a valid transition from `approved` or `edited`. Editing counts as approval of the new text, so the recorded approver is always whoever last touched the words that will be posted. Rejecting clears the approval.
2. **Use case.** `PostReply` checks the transition *before* calling the store API, and holds a row lock (`SELECT ... FOR UPDATE`) across the call, so two clicks on "Post" can't double-post.
3. **Database.** A check constraint rejects any row in `posted` or `would_post` without `approved_by`, whatever code wrote it. `reply_audit` is append-only, enforced by a trigger that raises on UPDATE or DELETE.
4. **Configuration.** Real posting needs store keys **and** `POSTING_ENABLED=true`. Configuring read access for ingestion can never post as a side effect. Without both, posting records `would_post` with a note.

**Trade-off.** The store call happens inside the transaction, before the commit. If the commit fails after a successful post, the reply is live but recorded as approved; retrying would post again. Both stores keep a single developer response per review, so a retry updates or is refused rather than stacking a duplicate. That is close enough to idempotent that I prefer it to a two-phase outbox at this scale. The outbox is the upgrade path.

**Actor.** There is no authentication yet, so the actor is a validated name from the client. That is enough for an audit trail in a trusted team setting. Sessions and roles are first on the roadmap.

## Other decisions, briefly

- **Summaries in English.** The triage prompt asks for an English summary whatever the review language. Clustering then groups "se cierra al iniciar sesión" with "crashes when I log in" without multilingual embeddings.
- **Prompt injection.** Review text reaches the model as XML-escaped data inside `<review>` tags, and the instructions say never to follow instructions in it. The output is a closed schema, so a hostile review can at worst produce a wrong label, and replies still need a human.
- **App Store versions.** The App Store Connect customer reviews resource has no app version. Ingestion attributes each review to the newest `appStoreVersion` created before it. That can be early by the length of App Review, which is acceptable for release-level comparison and documented as a gap.
- **Costs.** Every model call (triage, reply, theme title, embedding batch) writes a row to `llm_calls` with tokens, cost and latency. The overview shows the totals.
- **Charts without a chart library.** The dashboard needs a sparkline, a line chart with a hover crosshair and a bar list. Plain SVG covers those in about 200 lines and keeps the bundle small.
