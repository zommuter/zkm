---
date: '2026-01-01T00:00:00+00:00'
source: test
sha256: 0000000000000000000000000000000000000000000000000000000000000002
subject: HTML entity NER artifact fixture
entities:
  - {scope: body, type: org, value: "&gt;&nbsp;", valid: false}
  - {scope: body, type: org, value: "&nbsp;&gt;&nbsp;", valid: false}
  - {scope: body, type: org, value: "&gt; &gt;", valid: false}
  - {scope: body, type: org, value: "Actual Company GmbH", valid: true}
---

Re: previous message from Actual Company GmbH.

Please see the attached invoice for details.
Payment is due within 30 days of receipt.
