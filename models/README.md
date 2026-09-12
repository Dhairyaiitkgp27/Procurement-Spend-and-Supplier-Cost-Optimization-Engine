# models/

This project uses **transparent, rule-based** scoring and recommendation logic
(documented in `config.yaml` and the `src/` phase modules), not a trained/opaque
ML model, so there is no serialized model artifact to persist here. Supplier
Performance Index, risk scoring, savings levers, recommendations and negotiation
priority are all deterministic functions of the data and the config weights,
which keeps every output explainable and auditable.

If the approach were extended with a learned component (e.g. a savings-capture or
supplier-default predictor), the fitted estimator would be serialized to this
directory.
