---
date: '2026-04-01T09:00:00+00:00'
entities:
- canonical: '1250.'
  scope: body
  standard: ISO 4217
  type: amount
  unit: CHF
  value: CHF 1250.
- scope: body
  type: person
  value: Bob
- scope: body
  type: person
  value: Alice
- scope: signature
  type: person
  value: Alice
- canonical: '1250.'
  scope: salutation
  standard: ISO 4217
  type: amount
  unit: CHF
  value: CHF 1250.
- scope: salutation
  type: person
  value: Bob
message_id: <corpus-standalone@example.com>
participants:
- address: alice@example.com
  name: Alice
  role: from
- address: bob@example.com
  name: Bob
  role: to
processor: eml
processor_version: 0.11.0
salutation_block: 'Dear Bob,


  Please find the invoice for March services totalling CHF 1250.'
sha256: b0cb60976925d8a2787ce46b72e4b339eda2dcaefbd7928a07d0029ffd952c93
signature_block: 'Best regards,

  Alice'
source: eml
source_blob: 7707cff2bbd3ccc7bd4dce81e7ea249f777d9bfb
source_path: src/zkm/plugins/zkm-eml/tests/fixtures/corpus/corpus_standalone.eml
source_repo_commit: 2b1e384b9844bfbd6155c407ac7eec93db94fa0a
subject: Invoice for March services
tags: []
thread: mail/threads/2026/04/2026-04-01-c4a8fe10-invoice-for-march-services.md
thread_id: c4a8fe10f942ed29
---

Dear Bob,

Please find the invoice for March services totalling CHF 1250.
Payment due within 30 days.

Best regards,
Alice