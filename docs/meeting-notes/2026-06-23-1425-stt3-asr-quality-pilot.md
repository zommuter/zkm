# 2026-06-23 — STT3: ASR quality pilot design

**Started:** 2026-06-23 14:25
**Session:** 82f12219-f657-4219-9f1a-5441114cd41e
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 🎙️ Aria (speech-pipeline, new), 🧠 Mira (multimodal ML / privacy, new)
**Topic:** Design the STT3 pilot — compare ASR models/means on real private voice notes and pick an `stt_model` default, without the agent reading transcript content.

## Surfaced discoveries
- [2026-05-14 helferli] Schweizerdeutsch Mundart is beyond ggml-small AND gemma4-e4b ("Chasch mer hälfe" → whisper returns Arabic, Gemma returns Hindi). Lexical-Alemannic ceiling, no fix at current tier.
- [2026-05-12 helferli] Gemma 4 E4B is audio-in/text-out only; multimodal path activates via HELFERLI_MULTIMODAL_URL.
- [2026-05-10 helferli] whisper.cpp only exposes `/inference` (not `/v1/audio/transcriptions`); standalone whisper-server required.
- [2026-05-13 zkm] thinking-mode models (gemma4-e4b) show ~20s TTFT even warm.
- [2026-06-22 zkm-stt] WhatsApp day-files reconstituted from manifest every convert → derived transcripts must live in their own CAS-linked file.

## Existing harness (helferli) — what we reuse and what we don't
`~/src/helferli/tools/relay/scripts/asr_bench.py` + `asr_bench.results.md` score **language-tag accuracy** on **edge-tts-synthesized** stimuli. Gap vs STT3: different metric (lang-tag → WER/quality), different input (synthetic → real private), new privacy constraint (agent must not read content). We borrow its *skeleton* (HTTP `/inference` call, `verbose_json` lang extraction, the markdown report writer) but build a new script.

Disk/server check at meeting time: `ggml-small.bin` + `ggml-large-v3-turbo.bin` both on disk; whisper-server live on :8089 (small only — **one model per process**); llama-swap :8080 serves `gemma4-e4b`, `aya-expanse-8b`, `llama-3.2-3b`, `deepseek-r1-7b`, `bge-m3`.

## Agenda
1. Privacy & ground-truth protocol — score quality on private clips without the agent reading content.
2. Model matrix scope — which candidates run (N=2 discipline).
3. Metric — WER vs ordinal human-rank vs judge-agreement, given the Swiss-German ceiling.
4. Local-LLM judge — role, agreement-bias trap, privacy posture.
5. Harness home, deliverable, decision rule.

## Discussion

### Item 1 — Privacy & ground-truth protocol
Aria: WER/CER needs references; the user hand-transcribes a handful; the agent must not read content. Mira: the real leak is the agent's *output stream* — the helferli harness prints transcript snippets and a 60-char `text_snippet` column; if the agent reads that file every transcript lands in Claude's cloud context (the chidiai egress lesson, id:f3e1). Privacy must be **structural, not behavioural**. Archie: split output into a scores tier (numbers + clip-ids + model names → agent-readable, committable) and a content tier (references + side-by-side transcript matrix → gitignored, agent never given the path). Riku: (a) all candidate models must be local or the audio egresses — rule out cloud Whisper API as a "ceiling"; (b) the scores tier carries literally zero text — suspicious spans referenced by offset/clip-id, never quoted. Petra: n≈8–10, a pilot not a benchmark suite; no transcription UI. Mira: audio clips themselves gitignored.

### Item 2 — Model matrix scope
Aria: cheapest axis is within whisper.cpp (small vs large-v3-turbo — same `/inference`, restart the server or stand up a 2nd port). The different *means* is Gemma-E4B multimodal (audio-in via llama-swap), which is also the N=2 backend-seam question — but helferli found that audio path only *partial*, so verify it first. Petra: stop at three for pass 1; faster-whisper / distil-whisper / CH-German fine-tune are new runtimes, against N=2. Riku: faster-whisper has no Vulkan → CPU-slow on Arc; distil-whisper is English-distilled, weak on DE/CH-DE; only a real CH fine-tune could move the dialect needle (its own mini-project). Mira: the likely finding is large-v3-turbo > small on Standard German and nothing clears the Mundart ceiling — Tier-1 answers the practical question alone. **User addendum:** each reference clip carries a predefined language tag {de, de-CH, en} (de most likely, en least) → per-language slicing + lang-tag reused as a free secondary metric.

### Item 3 — Metric
Aria: primary = WER + CER per clip, aggregated per lang slice, both from one alignment pass, with a documented normalizer (casefold + strip punctuation + collapse whitespace) applied before scoring. Riku: WER saturates ~100% on the de-CH slice for every model → it can't rank "least bad" at n≈3; treat de-CH as ceiling confirm/clear, not a fine ranking; WER/CER are actionable on the de + en slices. Mira: reuse helferli's lang-tag accuracy as a free secondary (meaningfully measurable even on dialect, and it's a number → fits the scores tier); slicing keeps the `de` verdict clean of dialect garbage. Petra: no third bespoke metric — the ordinal "least-bad on dialect" call stays the user's eyeball pass on the private matrix. **User addendum:** sample is ~90% regular German → the `de` slice is dominant.

### Item 4 — Local-LLM judge
Mira: the agreement-bias trap — a judge scoring by candidate-agreement favours consistent garbage or diverging hallucinations on dialect; agreement ≠ correctness; the judge is triage, never the arbiter, never overrides WER or the user. Riku: ref-free it can only flag divergence (attention director); ref-aware it can soft-rate fidelity, tolerating synonyms/formatting that brittle WER over-penalizes — strictly more useful, and local so reading the reference costs no egress. Mira: inherits D1 — judge → agent output is numbers + clip-ids only (fidelity per model×clip + divergence flag); annotated text goes to the user-only tier. Aria: offline batch → latency irrelevant → aya-expanse-8b (better multilingual) over gemma4-e4b (thinking-mode TTFT + query-echo). Petra: the judge is the droppable piece if time is tight.

### Item 5 — Harness home, deliverable, decision rule
Archie: a NEW script `plugins/zkm-stt/tools/asr_quality_bench.py` borrowing helferli's skeleton but driving zkm-stt's own `transcribe(audio_path, config)` seam over a config matrix — so the pilot measures the real production backend, not a parallel reimplementation. Aria: `transcribe()` speaks whisper `/inference` today; Gemma-E4B is OpenAI `input_audio` (a different `stt_api_style` = exactly the N=2 seam the pilot is meant to justify), so the bench carries a local Gemma adapter just for the comparison and `transcribe()` grows the multimodal style only *if* Gemma wins — "verify path first" is a bench step, not a precondition. Riku: at n≈8-10 the CLAUDE.md pilot-sample heuristic (~10pp indistinguishable) forces asymmetric bars — a cheap reversible config swap (small→large-v3-turbo) on a modest consistent `de`-WER win, but a new expensive sticky backend (Gemma) only on a clear margin or a unique dialect clearance; a tie does not earn a new backend. Mira: honour the likely-null result — "keep small / swap to large-turbo if the de win is clean; do NOT wire Gemma; Tier-2 stays gated; dialect is a known ceiling" is a *successful* pilot outcome. Petra: deliverable = scores artifact (committable) + user-only transcript matrix + a short recommendation in zkm-stt meeting-notes. **User refinement (key):** unlike helferli's fast-as-sensible interactive constraint, this pilot is batch/offline — transcription *may be slower if it buys accuracy*, so latency is an informational tiebreaker, NOT a gate; accuracy (de-slice WER) dominates.

## Decisions
- **D1 — Tiered structural privacy.** Bench emits a scores-only artifact (numbers + clip-ids + model names; agent-readable, committable) and a gitignored content tier (references + side-by-side transcript matrix + audio clips; agent never given the path). All candidates run locally → no audio/text egress. *Out of scope:* any cloud ASR (e.g. OpenAI Whisper API) — it would egress private audio.
- **D2 — Model matrix.** Tier-1 now: whisper `ggml-small`, whisper `ggml-large-v3-turbo`, Gemma-4-E4B multimodal (verify path first). Tier-2 (faster-whisper, distil-whisper, CH-German fine-tune) gated on "Tier-1 didn't clear the bar". Each reference clip carries a predefined lang tag {de, de-CH, en}; sample ~90% de. *Out of scope:* building any Tier-2 backend on spec.
- **D3 — Metric.** Per (model×clip): WER, CER, detected-lang, lang-correct, latency. Aggregates per (model×lang-slice): mean WER, mean CER, lang-tag accuracy. `de`-slice mean WER = headline; `de-CH` = ceiling confirm/clear (not a fine rank at n≈3); documented normalizer pre-scoring. *Out of scope:* a bespoke third metric; an agent-computed dialect ranking.
- **D4 — Judge.** aya-expanse-8b, ref-aware, advisory triage. Numeric fidelity + divergence flags → scores tier; annotated text → user-only tier. Reported alongside WER, never overrides it/user; "agreement ≠ correctness" caveat printed on the artifact. *Out of scope:* judge as arbiter / default-picker.
- **D5 — Home.** `plugins/zkm-stt/tools/asr_quality_bench.py`, borrowing helferli's skeleton, driving zkm-stt's `transcribe(audio,config)` seam over a config matrix; bench-local Gemma adapter; `transcribe()` grows the multimodal `api_style` only if Gemma wins. *Out of scope:* extending helferli's asr_bench.py in place.
- **D6 — Decision rule (asymmetric bars; latency NOT a gate — batch/offline).** Default swap small→large-v3-turbo on a consistent `de`-slice WER improvement (low, reversible bar). Wire Gemma multimodal only on a clear `de`-slice margin over the best whisper option OR a unique dialect-ceiling clearance (high, N=2 bar). Sub-threshold everywhere → keep ggml-small, defer Tier-2. A "change nothing" outcome is a valid successful pilot.

## Action items
(Implementation breakdown of STT3 / id:4ab4 — the umbrella item tracks completion; sub-steps are un-IDed by design.)
- [ ] Build `plugins/zkm-stt/tools/asr_quality_bench.py`: config-matrix driver over `transcribe()`; Tier-1 backends incl. bench-local Gemma adapter; tiered output (D1); WER+CER+lang-tag sliced by {de,de-CH,en} (D3); documented normalizer; aya-expanse-8b ref-aware soft-judge (D4). Contract: a run over populated clips+references produces a scores-only artifact containing ZERO transcript text + a gitignored side-by-side matrix.
- [ ] gitignore the private tier in `plugins/zkm-stt/.gitignore` (clips dir, `references.json`, `*.transcripts.md`). Contract: `git status` after a pilot run shows no audio/transcript/reference files.
- [ ] Bench step-zero: verify Gemma-4-E4B audio path on :8080 accepts `input_audio` and returns a transcript (not a chat reply). Contract: a probe returns transcript text; on failure Gemma drops from Tier-1 with a logged note.
- [ ] [USER] Author `references.json` (~8–10 clips, ~90% de + few de-CH + ≤1 en; each clip: predefined lang tag + hand transcript), populate the gitignored clips dir. Prerequisite for the pilot run.
- [ ] Run pilot + write recommendation to `plugins/zkm-stt/docs/meeting-notes/`: `stt_model` verdict + wire-Gemma yes/no + Tier-2 trigger status. Closes STT3 (id:4ab4).
- [ ] [FORWARD-FLAG] Append to STT4 (id:fa7b): WhatsApp speaker-ID / diarisation can use contact/sender metadata (manifest sender per message), not acoustic voiceprinting → cheaper path.
