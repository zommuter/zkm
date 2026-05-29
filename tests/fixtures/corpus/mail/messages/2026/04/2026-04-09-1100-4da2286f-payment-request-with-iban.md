---
date: '2026-04-09T11:00:00+00:00'
entities:
- canonical: DE44500105175407324931
  scope: body
  standard: ISO 13616
  type: iban
  value: DE44 5001 0517 5407 3249 31
- canonical: '1250'
  scope: body
  standard: ISO 4217
  type: amount
  unit: CHF
  value: CHF 1250
- canonical: '31'
  scope: body
  standard: ISO 4217
  type: amount
  unit: BIC
  value: '31

    BIC'
- scope: body
  type: person
  value: Bob
- scope: body
  type: org
  value: 'Bank:'
- scope: body
  type: org
  value: Deutsche Bank AG
- scope: body
  type: org
  value: IBAN
- scope: body
  type: person
  value: Alice
- scope: signature
  type: person
  value: Alice
- scope: salutation
  type: person
  value: Bob
message_id: <corpus-iban-invoice@example.com>
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


  Please transfer the outstanding amount for the March invoice.'
sha256: ad216929fd03737229794828a1e68a5d935ed9e461fa77c1959fed534e5ce063
signature_block: 'Best regards,

  Alice'
source: eml
source_blob: b605978fde6ec452375405e324985afb21750211
source_path: src/zkm/plugins/zkm-eml/tests/fixtures/corpus/corpus_iban_invoice.eml
source_repo_commit: 2b1e384b9844bfbd6155c407ac7eec93db94fa0a
subject: Payment request with IBAN
tags: []
thread: mail/threads/2026/04/2026-04-09-4da2286f-payment-request-with-iban.md
thread_id: 4da2286f9c67cf88
---

Dear Bob,

Please transfer the outstanding amount for the March invoice.

Amount due: CHF 1250
Bank: Deutsche Bank AG
IBAN: DE44 5001 0517 5407 3249 31
BIC: DEUTDEDB

Payment is requested within 14 days.

Best regards,
Alice