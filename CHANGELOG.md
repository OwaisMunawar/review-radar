# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-09-30

### Added

- Review ingestion behind a `ReviewSource` protocol: App Store Connect (ES256 JWT), Google Play Developer API (service account) and a fixture source. Upserts are idempotent on `(store, review_id)`.
- Triage agent on PydanticAI with a typed `Triage` output, batching with a concurrency limit, retries, and per-call token and cost accounting in `llm_calls`.
- Summary embeddings in pgvector (HNSW, cosine), average-linkage theme clustering, model-written theme titles, weekly sparklines and trends.
- Release regression detection: a one-sided two-proportion z-test per category and theme, Holm-corrected, gated on effect size and minimum count.
- Reply drafting with store-aware length limits, an approval workflow (approve, edit, reject, reopen, post), dry-run posting and an append-only audit log.
- FastAPI API with one error envelope and stable error codes, locked CORS and validated inputs.
- React dashboard: overview, themes, release comparison, review explorer and reply approvals, in light and dark.
- Offline demo mode: a `FunctionModel` rule model, a hashing embedder and a synthetic 400-review Pocket Planner dataset with an injected 2.3.0 login-crash regression.
- Triage evals on 60 labelled reviews with `pydantic_evals`: accuracy, macro-F1 and a confusion matrix, with a CI threshold.
- Docker Compose quick start, GitHub Actions CI and Dependabot.

[0.1.0]: https://github.com/OwaisMunawar/review-radar/releases/tag/v0.1.0
