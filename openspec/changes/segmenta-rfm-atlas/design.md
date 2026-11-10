# Design

## Context

See proposal.md for motivation and specs/rfm-modeling/spec.md, specs/rfm-segmentation-web/spec.md, and specs/rfm-project-documentation/spec.md for behavioral contracts. The repository currently contains the OpenSpec skeleton but no implementation or prior notebook, so the design treats this as a new Python project and does not assume dataset files, measured model quality, or an existing application interface.

## Goals / Non-Goals

**Goals:**

- Use one trained preprocessing-plus-K-Means artifact for both notebook evaluation and web inference.
- Keep Flask presentation in server-rendered HTML/CSS and keep training, web, validation, tests, inference, and persistence logic in Python classes and methods.
- Deploy the Flask application behind a WSGI server on an HTTP-accessible hosting environment.
- Make the Atlas write boundary small, auditable, and insert-only.
- Make training and inference metadata sufficient to validate feature order and training ranges.

**Non-Goals:**

- Add user accounts, customer identity, personal data, or a history/reporting interface.
- Provide Atlas reads, updates, deletes, or a general database repository abstraction with those capabilities.
- Promise a particular cluster quality, number of clusters, dataset size, or evaluation score before training has been run.
- Add browser-side JavaScript or move model/domain logic into templates.

## Decisions

1. **Use the official UCI workbook and record its provenance.** A Python dataset-loader class downloads the UCI dataset 352 ZIP from `https://archive.ics.uci.edu/static/public/352/online+retail.zip` when no local workbook exists, extracts `Online Retail.xlsx`, and verifies exactly 541,909 transaction rows before training. In Colab, failed downloads lead to a manual upload of the same named workbook and the same row-count/schema checks. The loader records source, dataset ID, row count, and SHA-256 in the training manifest. Unit tests may use small in-memory fixtures, but the training notebook never fits or exports unless loader validation succeeds.

2. **Select k by measured silhouette and preserve selection evidence.** Evaluate k from 2 through 10 (bounded by the number of customer rows), computing inertia and silhouette for each candidate on the real customer-level RFM data. Select the candidate with the highest silhouette, breaking ties with the smallest k, then fit the final scaler-plus-K-Means pipeline with that k. A fixed k was considered but rejected because it would not preserve evidence for cluster selection.

3. **Serialize model and segment profiles together.** The one joblib artifact stores the fitted preprocessing-plus-K-Means pipeline, ordered features, raw training ranges, package version, selected parameters and candidate metrics, dataset provenance, plus each K-Means label, customer count, and centroid transformed back to original RFM units. This keeps inference and displayed interpretation tied to the exact fitted model. The app continues to load the artifact without training.

4. **Derive and document conventional customer-level RFM inputs.** Training aggregates source transactions to one row per customer: recency in days relative to a documented analysis reference date, frequency as a documented count of distinct transactions, and monetary spend as a documented sum of transaction value. Cleaning rules, currency/returns handling, and reference-date selection must be explicit in the notebook and technical document.

5. **Reject out-of-training-range values by default.** The inference service compares each value with the ranges recorded by the training artifact and rejects an observation before inference or persistence when any value is outside the range. A documented warning mode may be enabled explicitly; in that mode the warning is shown and inference proceeds. Rejection is the default because it avoids presenting extrapolated cluster assignments as ordinary in-range results while keeping the requested warning option available.

6. **Use server-side class-based Flask views and domain services.** A class-based view handles GET/POST and renders HTML; separate Python classes handle input validation, model loading/prediction, and persistence. Python test suites also use test classes and methods. Templates display submitted values, errors, warnings, and the segment. HTML form constraints may improve usability, but Python validation remains authoritative. Browser code is limited to HTML/CSS; no JavaScript is used.

7. **Constrain Atlas to one append operation per accepted classification.** A narrowly scoped Python persistence class accepts a validated RFM record and its predicted segment and invokes `insert_one` once. It exposes no query, update, or delete methods. The stored document contains only the three RFM values and segment. On insertion failure, the web flow reports that recording failed and does not claim the classification was persisted. No personal identifiers or credentials enter the document or repository; `MONGO_URI` and other secrets are supplied only through environment variables or the hosting provider's secret manager.

8. **Test boundaries with Python functional tests and doubles.** Tests cover dataset validation/download fallback, RFM preparation, cluster selection, artifact metadata and round-trip loading, valid/invalid form submissions, range warning/rejection, prediction, insertion count and payload, and database failures. Test fixtures are explicitly separate from the notebook's final UCI-only training path. A fake persistence client allows deterministic checks without requiring Atlas. Tests assert the persistence interface has no read/update/delete operations.

9. **Document with implementation-aligned diagrams.** The technical document includes a C4 context/container view and a UML class view, both rendered as source diagrams in the repository. They are updated alongside component/class changes and describe only shipped components. README contains setup and operation instructions; metrics are shown only after actual notebook execution.

## Risks / Trade-offs

- [RFM meanings can vary by dataset and academic convention] → State transaction cleaning, distinct-invoice frequency, monetary aggregation, and reference-date rule; verify them against the supplied Online Retail dataset during implementation.
- [K-Means is sensitive to scaling and skewed RFM distributions] → Keep transformations inside the saved pipeline, report calculated evaluation evidence, and document chosen model parameters without promising a preferred score.
- [A clustering model has no inherently ordered segment labels] → Preserve estimator label values as opaque segment identifiers and avoid claiming labels imply ranking unless a documented post-fit interpretation is added.
- [A valid prediction may be unavailable when Atlas insertion fails] → Show a clear persistence failure and do not report the request as fully recorded.
- [Runtime and training library versions can differ] → Record dependency versions and validate artifact compatibility at load time with an actionable startup error.
- [UCI download may be unavailable in Colab] → Offer manual upload of the official workbook, require the exact transaction count/schema before training, and record acquisition method and content hash.

## Migration Plan

This is a greenfield addition, so no existing deployment or data migration is required. Implementation will add the training notebook and reusable Python package, produce the model artifact from user-provided data, configure external runtime settings, run the web app and functional tests, then deploy the Flask application behind WSGI and verify its HTTP endpoint. Rollback consists of stopping the new app and removing its deployment; no existing data is modified. Atlas documents written during demonstrations are append-only and are not automatically cleaned up.

## Open Questions

- The user-provided source dataset location and license/redistribution constraints must be confirmed during implementation; they do not change the specified RFM behavior contract.
- The environment-specific Atlas URI, database, and collection names are runtime configuration values and must be supplied outside the repository.
