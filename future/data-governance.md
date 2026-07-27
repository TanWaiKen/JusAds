# Data governance and training-data requirements

Never train on customer content, uploads, prompts, media, or reviewer feedback
by default. A training-data proposal must first document lawful basis/consent,
data minimisation, retention, access controls, regional handling, vendor
sharing, deletion/erasure handling, and an approved review process.

Only use an approved, versioned dataset with:

- immutable dataset and label-set versions;
- provenance, collection date, market/language, licence/consent, and intended
  purpose for each source;
- de-identification and PII/media-risk review before model access;
- role-limited access, encryption, audit logs, and a defined retention period;
- representative coverage across policy categories, languages, and relevant
  customer contexts; and
- documented exclusions, label uncertainty, and annotator guidance.

Synthetic fixtures may be committed for tests only when clearly marked as
synthetic. They must never be described as production evidence.
