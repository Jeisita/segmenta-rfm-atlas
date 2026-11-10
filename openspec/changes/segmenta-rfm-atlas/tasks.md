# Tasks

## 1. Project Setup

- [x] 1.1 Create the Python project, package, notebook, web, templates, static CSS, tests, and documentation structure; verify the expected paths exist and no JavaScript source is introduced.
- [x] 1.2 Declare pinned or bounded Python dependencies, WSGI server, and runtime configuration names such as `MODEL_PATH`, `OUT_OF_RANGE_POLICY`, `MONGO_URI`, `MONGO_DATABASE`, and `MONGO_COLLECTION`; verify a clean Python environment can install dependencies and that no credential or secret is stored in tracked files.

## 2. RFM Training and Model Artifact

- [ ] 2.1 Add a Python class that downloads UCI dataset 352 when needed, supports Colab manual upload after network failure, and rejects workbooks that do not contain exactly 541.909 transactions; verify with mocked download, fallback, and row-count tests without committing a workbook. The fallback test was added but still needs to run in a working Python environment.
- [x] 2.2 Implement class-based Python data preparation for customer-level recency, distinct transaction frequency, and monetary spend; document source-column, cleaning, return/currency, and reference-date rules and verify them with Python functional tests over representative fixtures.
- [x] 2.3 Implement class-based candidate-cluster evaluation for k=2..10 using calculated inertia and silhouette, select maximum silhouette with deterministic tie-breaking, then fit the final scaler/K-Means model; verify selection and metrics with test-only fixtures.
- [x] 2.4 Extend the serialized artifact with UCI source/hash/count, selected-k evidence, segment labels, customer counts and original-scale centroids; verify round-trip preservation and that the web loader still predicts without calling fit.
- [x] 2.5 Update the Jupyter notebook to auto-download the official UCI workbook in Colab and offer manual `Online Retail.xlsx` upload on download failure; run only after the 541.909-row validation, display calculated cluster-selection/final metrics, and save the final model artifact. Validate cell syntax without generating a synthetic final model.

## 3. Flask Inference and Atlas Persistence

- [x] 3.1 Implement class-based Flask views and server-rendered HTML/CSS form for recency, frequency, and spend; verify GET and POST responses with the Flask test client and confirm there is no JavaScript dependency.
- [x] 3.2 Implement Python class-based domain validation for missing, non-numeric, non-finite, and domain-invalid values; verify invalid submissions render clear errors and trigger neither inference nor persistence.
- [x] 3.3 Implement training-range validation using artifact metadata with rejection as the default and explicit warning mode; verify tests show the warning and continue only in warning mode, while rejection prevents inference and persistence.
- [x] 3.4 Implement real-time inference through the exported pipeline and verify a valid accepted form submission returns the pipeline's segment identifier using a controlled test model.
- [x] 3.5 Implement an Atlas persistence class with Python methods that accepts only RFM values plus segment, reads `MONGO_URI` and other connection settings from environment variables or the hosting secret manager, and invokes exactly one `insert_one`; verify with a fake collection that the payload contains no personal data or secrets and that no read/update/delete operations are exposed.
- [x] 3.6 Handle Atlas insert failures without claiming success; verify functional tests return a clear persistence error and count exactly one attempted insertion for the accepted submission.

## 4. Project Documentation and Functional Coverage

- [x] 4.1 Write README installation, dataset preparation, model training, app launch, external Atlas configuration, WSGI deployment, and test instructions; verify each command and required setting matches the implemented project and explains that secrets such as `MONGO_URI` are configured outside the repository.
- [x] 4.2 Write the technical document with data rules, model artifact contract, runtime flow, validation, security boundary, and failure behavior; verify it makes no unobserved claims about model metrics or data results.
- [x] 4.3 Add C4 context/container and UML class diagrams for the implemented training and web components; verify every actor, component, class, dependency, and Atlas interaction corresponds to the delivered code.
- [x] 4.4 Complete functional test coverage written in Python and organized in test classes and methods for valid and invalid requests, both range policies, inference, insert count/payload, Atlas failures, and absent read/update/delete methods; verify the documented test command passes without Atlas credentials.

## 5. Integration Verification

- [x] 5.1 Run the full documented setup and functional test workflow; verify notebook/model and Flask components use the same feature order, preprocessing artifact, and range metadata.
- [x] 5.2 Review tracked files and rendered web templates for personal data, credentials, and JavaScript, and review the Atlas integration for operations beyond one `insert_one`; record the verification outcome in the technical documentation without inventing training results.
- [x] 5.3 Execute the notebook against the validated official UCI workbook, calculate the selection and final metrics from those real transactions, and serialize the production artifact; verify its provenance, hash, transaction count, selected-k evidence, and segment metadata. Do not mark complete until execution on the real dataset succeeds.
- [x] 5.4 Deploy Flask behind the configured WSGI server using hosting environment variables or a secret manager; verify the deployed HTTP URL serves the form and a controlled functional flow while confirming no secrets appear in repository files, logs, or HTML responses.
