# Key user journeys for the zkm CLI. No web surface exists, so these are
# @manual human-checklist scenarios (run them on the real machine, not CI).
# Scenarios tagged @roadmap-XXXX describe behaviour that ships with that
# ROADMAP.md item and are expected to fail until it is done.

@manual
Feature: Fresh-machine quickstart
  The ready-to-publish bar: a new user gets from install to search results
  in under 5 minutes using only the README.

  Scenario: Init, ingest, index, search on a clean machine
    Given a machine with uv installed and no existing knowledge store
    When I run "uv tool install zkm"
    And I run "ZKM_STORE=~/knowledge zkm init"
    And I run "zkm plugin add <git-url-of-zkm-notes>" with a folder of .txt notes configured
    And I run "zkm convert notes"
    And I run "zkm index --no-embed"
    And I run "zkm search <a word that occurs in one note>"
    Then each step completes without errors in under 5 minutes total
    And the search output lists the matching note with a snippet
    And "git -C ~/knowledge log --oneline" shows an ingest commit

@manual
Feature: Hybrid search degrades gracefully
  Dense embeddings are additive; BM25 is the floor.

  Scenario: Search with the embedding endpoint down
    Given an indexed store with ZKM_EMBED_ENDPOINT pointing at a stopped server
    When I run "zkm search invoice"
    Then I still get BM25 results
    And a stderr notice mentions the dense index being unavailable
    And the exit code is 0

@manual
Feature: Concurrent and gamemode guards
  Long-running commands refuse to start instead of corrupting state or
  competing with a game for resources. Exit 75 means "retry later".

  Scenario: Second convert of the same plugin while one is running
    Given "zkm convert eml" is running in terminal A
    When I run "zkm convert eml" in terminal B
    Then terminal B exits immediately with code 75
    And the message names the running PID and start time

  @roadmap-1098
  Scenario: Index refuses while the gamemode lock exists
    Given the file /tmp/zomni-gamemode.lock exists
    When I run "zkm index"
    Then it exits immediately with code 75
    And the message names the lock path
    And "zkm doctor" shows a "gamemode lock" row with exit code unchanged

  @roadmap-62f3
  Scenario: Freezing a running index from the gamemode toggle
    Given "zkm index" was started from a normal shell (no INVOCATION_ID)
    When I run "systemctl --user freeze zkm-index.scope"
    Then the index process stops consuming CPU until thawed
    And "systemctl --user thaw zkm-index.scope" resumes it to completion
    And starting a second "zkm index" while frozen exits 75 naming the scope state

@manual
Feature: Progress visibility for long runs

  Scenario: Watching a long convert from a second terminal
    Given "zkm convert eml" is processing a large mailbox in terminal A
    When I run "zkm status" in terminal B
    Then I see one row with command "convert(eml)", a progress count and an ETA
    And "zkm status --json | jq ." emits a valid JSON array
    When the process is SIGKILLed and I run "zkm status" again
    Then the stale row is dropped with a stderr notice

@manual
Feature: Store hygiene is dry-run first
  Destructive commands never delete on the first invocation.

  Scenario: Removing a managed note and collecting orphans
    Given a store where "mail/2026/some-bill.md" was ingested with an attachment
    When I run "zkm rm mail/2026/some-bill.md"
    Then I see a plan (sidecar updates and deletions) and nothing is deleted
    When I re-run with "--apply"
    Then the .md, its orphaned inbox symlink, sidecar and CAS object are gone
    And a commit "chore(rm): ..." appears in the store log
    When I run "zkm gc" and then "zkm gc --apply"
    Then remaining unreferenced CAS objects are listed first, then removed

@manual
Feature: Amenders enrich only what was just ingested
  @roadmap-dd89
  Scenario: No-op convert skips the amender pass
    Given an mbsync run that delivered no new mail
    When the post-sync hook runs "zkm convert eml"
    Then the command prints "Skipping amenders (0 files created)"
    And returns within seconds (no NER sweep)

@manual
Feature: Store health at a glance

  Scenario: Doctor on a healthy configured store
    Given an indexed store with embed and LLM endpoints configured and running
    When I run "zkm doctor"
    Then I see md/bm25/embed document counts that agree with each other
    And each configured endpoint reports OK with model and dimension
    And the exit code is 0
