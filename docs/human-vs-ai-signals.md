<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# Human-vs-AI Writing Signals: What Is Known, and Where It Fails

> **Status:** research reference (required deliverable, `vision.md` §9)
> **Last literature check:** 2026-10-07
> **Scope:** cues used by AI-text detectors and by human readers, with an evidence grade for each and its known failure modes.

---

## Read this first

> **Every signal in this document is a statistical correlation, not proof of authorship.**
> A text can show every "AI-like" feature and still be entirely human-written, and the reverse is also true. Detector scores, this project's ensemble score included, are **indicators** to investigate. They are not evidence that a specific person did or did not use AI.
>
> **This project does NOT implement a home-grown detector based on this document.** The library orchestrates *external* detectors (`vision.md` §1, §2.1). This document exists to help interpret their outputs, design tests and benchmark samples, and guide future research. Do not turn the cues below into scoring rules, regexes, or "AI-word" counters in the codebase.

---

## Evidence classes

Each topic is labelled with one or more of these classes. When a topic has several, the label says which part each class applies to.

| Label | Meaning |
|---|---|
| **Established (peer-reviewed)** | Shown in peer-reviewed work, or in widely cited preprints whose results other groups have reproduced. It still applies only to the models, domains and languages that were tested. |
| **Provider claim** | Stated by a detector or model vendor (blog, documentation, technical report). Not independently verified, or verified only partly. |
| **Plausible heuristic** | Has a sensible mechanism or partial evidence, but has not been shown to work reliably as a standalone signal. |
| **Folklore** | Popular belief that the evidence does not support as a reliable cue. It may hold in a narrow window and then disappear. |

A recurring theme in the literature: what holds for one generator, one decoding setting, one domain, or one year often fails for the next (RAID [Dugan et al. 2024]; M4 [Wang et al. 2024]; MAGE [Li et al. 2024]).

---

## 1. Token predictability and perplexity

**Class:** Established (peer-reviewed) as a detection signal. Folklore when read as "low perplexity = AI".

**What is known.** Language models tend to sample high-probability tokens, so their output usually has lower perplexity under a similar scoring model than human text does. GLTR showed this with per-token rank histograms and raised untrained human detection from 54% to 72% [Gehrmann et al. 2019]. Later zero-shot methods refine the idea:
- **DetectGPT** compares a passage's log-probability with that of perturbed rewrites. Machine text tends to sit in regions of negative curvature [Mitchell et al. 2023].
- **Fast-DetectGPT** replaces perturbation with conditional sampling and reports a relative gain of about 75% over DetectGPT, at roughly 340x the speed [Bao et al. 2024].
- **Binoculars** normalises perplexity by the cross-perplexity between two related models and reports detecting over 90% of ChatGPT samples at a 0.01% false-positive rate, with no training data [Hans et al. 2024].
- **Ghostbuster** feeds features from several weaker language models into a trained classifier [Verma et al. 2024].

Ippolito et al. [2020] found that decoding strategies that fool humans (e.g. top-k) leave statistical traces that machines can detect.

**Where it fails.**
- *Formulaic or memorised human text* (legal boilerplate, famous passages, standard abstracts, textbook definitions) has low perplexity too. The Binoculars authors discuss memorised text as a failure case.
- *Constrained writers* with smaller vocabularies, such as non-native writers and children, produce more predictable text. This is the mechanism behind the bias that Liang et al. [2023] found (see §17).
- *Sampling settings matter.* Higher temperature, different sampling, or repetition penalties can push machine text towards human perplexity. RAID found that detectors are easily fooled by changes in sampling strategy and repetition penalty [Dugan et al. 2024].
- *Paraphrasing* breaks the token-level probability signature [Krishna et al. 2023; Sadasivan et al. 2023].
- *Scoring-model mismatch.* Results are strongest when the scoring model is close to the generator. They weaken on unseen generators [Wang et al. 2024 (M4)].
- **Provider claim / history:** GPTZero originally advertised perplexity (with "above 85 suggests human") and burstiness as its core signals. GPTZero states that since autumn 2023 it no longer uses them and has moved to a deep-learning classifier [GPTZero 2023].

## 2. Burstiness: variation in sentence length and structure

**Class:** Provider claim (as a named detection feature). Established (peer-reviewed) only as a weak population-level difference.

**What is known.** "Burstiness" was popularised by GPTZero: humans supposedly vary perplexity and sentence length more over a document [GPTZero 2023]. In peer-reviewed work, Muñoz-Ortiz et al. [2024] found that human news text has "more scattered sentence length distributions" than the output of six LLMs. Reinhart et al. [2025] found that LLMs "struggle to match human stylistic variation".

**Where it fails.** The difference holds for distributions over many texts, not for any single document. Many human genres are deliberately uniform, such as technical documentation, legal text, and scientific abstracts. A prompt like "vary your sentence length" or a "humanizer" pass can add variation on purpose. GPTZero itself dropped the feature as a primary signal [GPTZero 2023].

## 3. Lexical diversity

**Class:** Established (peer-reviewed) as a population-level difference. Plausible heuristic at most for single documents.

**What is known.** Muñoz-Ortiz et al. [2024] report "more variety of vocabulary" in human news text. Liang et al. [2023] showed that *lower* lexical sophistication drives false positives: asking ChatGPT to "enhance the word choices" of non-native essays cut the average false-positive rate from 61.22% to 11.77%. Simplifying native essays raised it from 5.19% to 56.65%.

**Where it fails.** Lexical diversity depends heavily on text length (type-token ratios fall as texts get longer), on topic, and on proficiency. DIPPER's paraphraser has an explicit lexical-diversity control, so this feature can be manipulated directly [Krishna et al. 2023]. Russell et al. [2025] found that non-expert annotators wrongly treated "fancy" vocabulary as a sign of AI.

## 4. Repetition and phrase reuse ("AI vocabulary")

**Class:** Established (peer-reviewed) for corpus-level vocabulary shifts. Plausible heuristic for single documents. Folklore when one word is treated as proof.

**What is known.**
- Kobak et al. [2025] analysed more than 15 million PubMed abstracts and found an abrupt 2024 rise in *style* words such as "delves" (frequency ratio r=28.0), "underscores" (r=13.8) and "showcasing" (r=10.7), plus common words like "potential", "findings" and "crucial". From this they estimate that at least 13.5% of 2024 abstracts were LLM-processed. The 2024 excess consisted almost entirely of style words, whereas earlier excess (e.g. COVID) consisted of content words.
- Liang et al. [2024a; 2024b] used population-level frequency estimation to estimate LLM-modified fractions of AI peer reviews (6.5%-16.9%) and scientific papers (up to 17.5% in computer science).
- Russell et al. [2025] found that annotators who use LLMs heavily cite "AI vocabulary" (e.g. *vibrant, crucial, testament, delve, showcase*) as their most frequent cue. A majority vote of five such experts misclassified only 1 of 300 articles.
- Recurrent n-grams and repetition loops were classic artefacts of older, untuned models with poor decoding settings [Ippolito et al. 2020; Gehrmann et al. 2019].

**Where it fails.** These are **corpus-level** estimates. Liang et al. [2024a] explicitly argue that corpus-level estimation is more robust than per-instance inference. Humans have always used these words, and human writers are now absorbing LLM vocabulary themselves. Word lists go stale as providers tune models, and anyone can remove the words with find-and-replace. One "delve" proves nothing.

## 5. Syntactic regularity

**Class:** Established (peer-reviewed) at population level.

**What is known.** Reinhart et al. [2025] used Biber's lexical, grammatical and rhetorical features on parallel corpora (Llama 3 variants, GPT-4o). They found systematic differences between LLMs and humans, for example heavier use of nominalisations and participial clauses in instruction-tuned models. The differences were *larger for instruction-tuned models than for base models* and persisted as models grew. Muñoz-Ortiz et al. [2024] report different dependency and constituent distributions and shorter constituents in human text.

**Where it fails.** Feature differences are statistical, vary by genre, and were measured for specific model families at a specific time. Editing, paraphrasing, or a style prompt shifts them. Human writers trained in a formal register (academic, legal) overlap heavily with LLM-typical profiles.

## 6. Discourse structure and transition patterns

**Class:** Plausible heuristic, with partial support from peer-reviewed and practitioner sources.

**What is known.** Experts in Russell et al. [2025] cite predictable sentence structure (35.9% of explanations), such as "not only ... but also" and groupings of exactly three items. Wikipedia's WikiProject AI Cleanup lists overuse of connectives ("moreover", "furthermore") and section-ending summaries as frequent signs in submitted drafts. The guide itself says it is descriptive and that a combination of signs is needed [Wikipedia: Signs of AI writing].

**Where it fails.** Explicit connectives and signposting are *taught* in school essay writing, EFL/ESL instruction, and academic-writing courses. Such text is therefore over-represented exactly in the populations that already suffer false positives (§17, §18).

## 7. Over-structured prose (headings, bullets, bold lead-ins)

**Class:** Plausible heuristic.

**What is known.** Chat assistants are tuned to produce skimmable, markdown-heavy answers. HC3 documented that ChatGPT's answers were more organised and comprehensive and stayed on topic more strictly than human expert answers [Guo et al. 2023]. Wikipedia editors list markdown artefacts and excessive formatting as signs [Wikipedia: Signs of AI writing].

**Where it fails.** Formatting is the easiest thing to strip or change. Many human genres are heavily structured (READMEs, policies, slide notes). Copying from a chat UI into a plain-text field removes the markup anyway. Formatting style also depends on the provider and the interface.

## 8. Formulaic introductions and conclusions

**Class:** Plausible heuristic.

**What is known.** Restating the question, closing with "In conclusion / Overall / In summary", and adding generic significance statements ("plays a vital role", "stands as a testament") are listed by practitioners [Wikipedia: Signs of AI writing] and appear in expert annotator explanations [Russell et al. 2025].

**Where it fails.** This is the five-paragraph essay template that students are taught. It is also standard in press releases and grant abstracts. A single instruction or a light manual edit removes it.

## 9. Punctuation tendencies (including the em-dash)

**Class:** Folklore, for the em-dash as proof. Plausible heuristic for punctuation profiles in general.

**What is known.** Some studies find surface differences in punctuation and symbol use. Reinhart et al. [2025] mention punctuation among previously reported surface features, and Muñoz-Ortiz et al. [2024] report more numbers and symbols in LLM text. In 2024-2025 the em-dash (—) became a widely shared "ChatGPT tell" in popular media, with backlash from writers who use it habitually [NPR 2025]. Russell et al.'s experts actually describe *humans* as the ones using dashes, ellipses and varied punctuation, and AI as producing grammatically "perfect" text.

**Where it fails.** Em-dashes are standard in edited English prose and in typesetting. Word processors and phones auto-convert "--" to an em-dash. Punctuation norms also differ by language (e.g. French spacing, German quotation marks). Punctuation habits change when providers tune their models and are trivially edited. **Do not treat any single punctuation mark as an authorship signal.**

## 10. Hedging and assistant-style phrasing

**Class:** Plausible heuristic (strong for verbatim leftovers, weak otherwise).

**What is known.** Leftover chat phrases such as "As an AI language model", "I hope this helps", "Certainly! Here is ...", knowledge-cutoff disclaimers, or "it's important to note" are strong evidence that text was pasted from a chatbot, because humans rarely write them in finished prose. Wikipedia editors document them [Wikipedia: Signs of AI writing]. Uniform hedging and a "neutral, balanced" tone were noted in HC3 [Guo et al. 2023].

**Where it fails.** Apart from verbatim chat leftovers, hedging is normal academic and professional practice. Non-expert annotators in Russell et al. [2025] wrongly flagged a neutral tone as a sign of AI. The verbatim leftovers are also the first thing a careful user deletes.

## 11. Model-specific stylistic artefacts

**Class:** Established (peer-reviewed / reproduced preprint).

**What is known.** Sun et al. [2025] fine-tuned text-embedding classifiers that identify the source among ChatGPT, Claude, Grok, Gemini and DeepSeek with 97.1% accuracy. The patterns are rooted in word-level distributions and partly survive rewriting, translation and summarisation by another LLM. Reinhart et al. [2025] find differences *between* LLMs as well as between LLMs and humans. M4GT-Bench includes a multi-way task that asks which model generated a text [Wang et al. 2024b].

**Where it fails.** Model fingerprints are tied to specific model versions and change with each release (§21). Sun et al. study a closed set of known models. An open-world setting with unknown, fine-tuned or local models is much harder [Wang et al. 2024 (M4); Li et al. 2024 (MAGE)].

## 12. Paraphrasing and "humanization"

**Class:** Established (peer-reviewed). Detector robustness claims are provider claims.

**What is known.**
- DIPPER, an 11B paraphraser, cut DetectGPT's detection rate from 70.3% to 4.6% at a 1% false-positive rate. It also evaded watermarking, GPTZero, and OpenAI's classifier [Krishna et al. 2023]. The proposed defence, retrieval against a provider's log of its own generations, only works where the provider keeps that log.
- Recursive paraphrasing degrades watermark, neural, zero-shot and retrieval detectors with only slight quality loss [Sadasivan et al. 2023]. The same paper argues that the best possible detector's AUROC is bounded by the total-variation distance between the human and machine distributions. Chakraborty et al. [2023] respond that detection remains possible unless the distributions are identical, but the required sample size grows as machine text approaches human text.
- RAID evaluated 11 attacks (paraphrase, synonym swap, misspelling, homoglyph, zero-width space, etc.) and found that current detectors are easily fooled [Dugan et al. 2024].
- Russell et al. [2025] report that most detectors degrade on "humanized" text. In their test only Pangram matched expert humans, while Binoculars and Fast-DetectGPT fell to 6.7% and 23.3% TPR on humanized o1 output.
- **Provider claim:** Pangram reports robustness to humanizers and >38x lower error rates than competitors on its own benchmark [Emi & Spero 2024].

**Where it fails.** In both directions: paraphrasing hides AI text, and running human text through a "humanizer" or paraphraser can make it look *more* machine-like.

## 13. Mixed human/AI text

**Class:** Established (peer-reviewed) that it is hard.

**What is known.** Document-level detectors are poorly suited to texts with interleaved authorship. SeqXGPT introduced sentence-level detection for documents that mix human-written and LLM-modified sentences, and showed that earlier methods struggle there [Wang et al. 2023]. M4GT-Bench formulates mixed text as a boundary-detection task [Wang et al. 2024b]. Watermarks diluted inside a long human document remain detectable only with enough watermarked tokens [Kirchenbauer et al. 2024].
**Provider claim:** Turnitin reports a document-level false-positive rate below 1% only for documents with ≥20% AI writing, and a separate, higher (about 4%) sentence-level false-positive rate [Turnitin 2023a; 2023b].

**Where it fails.** A single "AI probability" is ill-defined for a document that is 30% AI. Different vendors interpret it differently: probability that *any* part is AI, or estimated *fraction* that is AI. That alone can make detectors disagree.

## 14. Grammar/style tools and post-editing

**Class:** Established (peer-reviewed).

**What is known.** Saha & Feizi [2025] evaluated twelve detectors on 14.7K samples with graded AI polishing (APT-Eval). Detectors "frequently flag even minimally polished text as AI-generated" and cannot tell degrees of involvement apart. Kobak et al. [2025] and Liang et al. [2024a] measure *LLM-processed* text, which includes editing, not only generation from scratch.

**Where it fails.** The line between "spell-checked", "grammar-tool-polished" and "AI-written" is a policy decision, not a measurable property. Tools such as grammar checkers increasingly use LLMs internally. A flag on polished human text is technically "correct" for some definitions and a false positive for others.

## 15. Translation effects

**Class:** Established (peer-reviewed) that it matters. Direction of the effect is detector-dependent (plausible heuristic).

**What is known.** Weber-Wulff et al. [2023] tested 14 tools and found that machine translation and obfuscation significantly worsened performance. Overall, the tools leaned towards classifying text as human. Sun et al. [2025] found that model idiosyncrasies partly survive translation by another LLM. Multilingual benchmarks show that detectors generalise poorly across languages and generators [Wang et al. 2024 (M4); Macko et al. 2023 (MULTITuDE)].

**Where it fails.** Human text that was machine-translated (e.g. with neural MT) may be flagged as AI, and AI text translated into another language may lose its signal. Detectors trained mostly on English are often uncalibrated for other languages. This project accepts any language on a best-effort basis (`vision.md` §2.5).

## 16. Technical, academic, and formulaic writing

**Class:** Established (peer-reviewed) for the mechanism (low perplexity and conventional style). Plausible heuristic for size of effect per genre.

**What is known.** Conventional genres have low entropy by design. LLM-preferred style overlaps with academic register [Reinhart et al. 2025; Kobak et al. 2025]. RAID and M4 show that performance varies strongly by domain (abstracts, recipes, reviews, poetry, etc.) [Dugan et al. 2024; Wang et al. 2024].

**Where it fails.** Abstracts, legal clauses, medical notes, API documentation and standard operating procedures have high base rates of "AI-like" features with no AI involved. Treat high AI scores on these genres with extra caution.

## 17. Non-native writing

**Class:** Established (peer-reviewed). A counter-claim is a provider claim.

**What is known.** Liang et al. [2023] tested seven detectors on 91 TOEFL essays. The average false-positive rate was 61.22%, 19.78% were flagged by *all seven* detectors, and 97.80% were flagged by at least one. US 8th-grade essays were misclassified about 5.19% of the time. The mechanism is constrained vocabulary and syntax, which lowers perplexity (§1, §3). Kobak et al. [2025] also find higher LLM-marker rates in abstracts from non-English-speaking countries. The authors suggest this reflects more LLM-assisted *editing*, which overlaps with the false-positive problem.
**Provider claim:** Pangram reports no bias against non-native speakers in its technical report [Emi & Spero 2024], and Ghostbuster includes a non-native evaluation [Verma et al. 2024]. These are encouraging, but they are self-evaluations on specific datasets.

**Where it fails.** This is a fairness failure mode, not just an accuracy issue. Detector outputs on non-native writing must never be used as sole evidence.

## 18. Very short samples

**Class:** Established (peer-reviewed). Thresholds are provider claims.

**What is known.** Detection accuracy rises with length for humans and machines alike [Ippolito et al. 2020]. Theory says the sample size needed grows as machine text approaches human text [Chakraborty et al. 2023]. After strong human paraphrasing, a watermark needed about 800 tokens on average to be detected at a 1e-5 false-positive rate [Kirchenbauer et al. 2024].
**Provider claims:** OpenAI's 2023 classifier said reliability improves with length (it required at least 1,000 characters). OpenAI withdrew it in July 2023 for low accuracy, having reported 26% true positives and 9% false positives [OpenAI 2023]. Turnitin raised its minimum from 150 to 300 words [Higher Ed Dive 2023].

**Where it fails.** A tweet, a chat message, a single paragraph, or a list of short answers gives the statistics too little to work with. A confident-looking score on such input is mostly noise.

## 19. Code, quotations, lists, tables, and boilerplate

**Class:** Plausible heuristic (limited direct evidence). Partial support from benchmarks.

**What is known.** Most detectors are trained and evaluated on prose. RAID keeps code (and Czech and German) in a separate "extra" split [Dugan et al. 2024], which shows these are treated as out-of-distribution. Experts in Russell et al. [2025] noticed that AI-written quotations follow uniform patterns, but quoted *human* material inside a document is not the author's writing at all.

**Where it fails.** Code, tables, citations, quoted passages, license headers and templated boilerplate distort token statistics in ways that are unrelated to who wrote the prose. Quoting a famous passage can lower perplexity (memorisation). This project does not strip such content (see Implications). Interpret scores on mixed-content input accordingly.

## 20. Unicode substitutions, confusables, and other evasion artefacts

**Class:** Established (peer-reviewed).

**What is known.** SilverSpeak replaced characters with homoglyphs (e.g. Latin "A" with Cyrillic "А") and drove seven detectors, among them Binoculars, DetectGPT, Fast-DetectGPT, Ghostbuster and watermarking, to near-chance. Average MCC fell from 0.64 to -0.01 [Creo & Pudasaini 2024]. RAID includes homoglyph, zero-width-space, whitespace and upper/lower-case attacks [Dugan et al. 2024].

**Where it fails / interpretation.** These artefacts point to *evasion attempts* rather than to who wrote the text. Confusables also occur legitimately in multilingual text, copy-pasted PDFs, and OCR output. Detectors may react in either direction: they flag everything or flag nothing. Disagreement between providers on such input is expected.

## 21. Detector drift as models and providers change

**Class:** Established (peer-reviewed) for generalisation failure. Provider claims about current accuracy are snapshots.

**What is known.** Detectors generalise poorly to unseen generators, domains and decoding settings. In such cases they tend to classify machine text as human [Wang et al. 2024 (M4); Li et al. 2024 (MAGE); Dugan et al. 2024]. Instruction tuning changes style substantially [Reinhart et al. 2025]. The vocabulary markers Kobak et al. observed are tied to a specific period of model behaviour. Vendors retrain their classifiers silently, and some methods are retired: OpenAI withdrew its classifier [OpenAI 2023], and GPTZero changed its core method [GPTZero 2023]. RAID notes that many detectors claim ≥99% accuracy without shared-benchmark evaluation [Dugan et al. 2024].

**Where it fails.** Any cached accuracy figure, including this document's, ages quickly. Results from the same provider on the same text may change over time.

## 22. Watermarking (related, provider-side)

**Class:** Established (peer-reviewed) for the method. Provider claim for deployment.

**What is known.** Kirchenbauer et al. [2023] proposed "green-list" watermarks that can be detected with interpretable p-values. Google DeepMind's SynthID-Text, published in Nature, was deployed in Gemini [Dathathri et al. 2024].

**Where it fails.** A watermark only proves anything for text from cooperating providers that embed one. Its absence says nothing about authorship. Paraphrasing and spoofing attacks exist [Sadasivan et al. 2023; Krishna et al. 2023], and mixing watermarked text into human text dilutes it [Kirchenbauer et al. 2024].

---

## Summary table

| # | Topic | Primary class | Main failure mode |
|---|---|---|---|
| 1 | Perplexity / predictability | Established | Formulaic, memorised, or non-native human text; sampling changes; paraphrase |
| 2 | Burstiness | Provider claim (weak established) | Uniform human genres; prompted variation |
| 3 | Lexical diversity | Established (population) | Length, topic, and proficiency effects; paraphrase control |
| 4 | Repetition / "AI vocabulary" | Established (corpus-level) | Not valid per document; word lists go stale; human adoption |
| 5 | Syntactic regularity | Established (population) | Register overlap; model-specific |
| 6 | Transitions / discourse | Plausible heuristic | Taught essay and EFL style |
| 7 | Over-structured prose | Plausible heuristic | Easily stripped; structured human genres |
| 8 | Formulaic intro / conclusion | Plausible heuristic | School templates |
| 9 | Punctuation, em-dash | **Folklore** (em-dash) | Autocorrect, typesetting, language norms |
| 10 | Hedging / assistant phrasing | Plausible heuristic | Normal professional hedging |
| 11 | Model-specific artefacts | Established | Version-bound; closed-set only |
| 12 | Paraphrasing / humanization | Established | Defeats most detectors |
| 13 | Mixed text | Established (hard) | Document score ill-defined |
| 14 | Grammar tools / post-editing | Established | Policy, not measurement |
| 15 | Translation | Established (matters) | Effect direction varies |
| 16 | Technical / academic writing | Established (mechanism) | High base-rate false positives |
| 17 | Non-native writing | Established | Documented bias |
| 18 | Short samples | Established | Insufficient statistics |
| 19 | Code / quotes / tables / boilerplate | Plausible heuristic | Out of distribution |
| 20 | Unicode confusables | Established | Pushes scores to either extreme |
| 21 | Detector drift | Established | All figures age |
| 22 | Watermarking | Established / provider | Only cooperating providers; removable |

---

## Implications for this project

These points explain *why* the library behaves as specified in `vision.md`. They shape how outputs are interpreted. They are **not** features to implement as a detector.

1. **Indicator, not proof.** The `HUMAN` / `AI` / `NO_VERDICT` line summarises external opinions. Documentation, verbose output and the JSON result should never phrase it as an authorship finding. The literature above (§1-§21) shows that every known cue has documented false positives on real human writing.

2. **Short texts.** Short inputs carry too little statistical evidence (§18), and several providers impose their own minimum lengths. The project should report a provider's minimum-length refusal as an explicit error, not hide it. It should treat agreement on very short inputs with suspicion, and it may legitimately return `NO_VERDICT`. Benchmark corpora (`vision.md` §10) should include short samples so that their error rates are measured, not assumed.

3. **Non-native writers and formulaic genres.** Expect a raised false-positive rate on non-native, simplified, academic, legal and technical text (§16, §17). The benchmark corpus should contain verified human samples from these populations so that calibration (`vision.md` §8.6) can measure the bias rather than inherit it. Do not compensate with home-grown "fairness" adjustments built from this document. Measure first.

4. **No preprocessing of the user's text.** The project preserves the user's text (`vision.md` §2.4). It does not normalise Unicode, strip code, tables or quotations, remove confusables, or "clean" punctuation. That is deliberate, for three reasons:
   - Each such transformation changes what the provider measures, and different transformations would make results incomparable across providers.
   - Normalisation would itself be an undocumented home-grown judgement.
   - Evasion artefacts (§20) and mixed content (§19) are information the user should see reflected in provider disagreement, not silently erased.
   The verbose output may *describe* the input (length, detected script mix), but should not alter it.

5. **Why disagreement is exposed.** Detectors are trained on different data, define "AI" differently (any AI vs. a fraction of AI, polished vs. generated, §13-§14), react differently to evasion (§12, §20), and drift independently (§21). Disagreement is therefore the expected state, and it is informative. Agreement and confidence are reported separately (`vision.md` §8.5), and verbose mode shows each provider's raw result so that a user can see *which* detectors diverge rather than a blended number that hides the split.

6. **Detector drift.** Provider behaviour changes without notice (§21). Results must record provider and model/version metadata and timestamps where available. Ensemble weights must be recalibrated against the benchmark corpus over time (`vision.md` §8.6, §10). Accuracy figures quoted in this document or in provider marketing must not be hard-coded as trust weights.

7. **Mixed and edited text.** A single label is a lossy summary of mixed or AI-polished text (§13, §14). Where a provider returns sentence-level or segment-level data, the structured result should keep it rather than collapse it.

8. **Use of this document in tests.** Use the cues here to *design* test and benchmark samples (e.g. a human-written text full of em-dashes and "delve", a non-native essay, a homoglyph-perturbed sample). Do not use them to *score* text.

---

## References

All entries below were checked to exist (arXiv API, ACL Anthology, PMLR, or publisher/provider page) on 2026-10-07. Venue information is given where confirmed. Otherwise the arXiv preprint is cited.

### Peer-reviewed and preprint literature

- **Bao et al. 2024** — Guangsheng Bao, Yanbin Zhao, Zhiyang Teng, Linyi Yang, Yue Zhang. "Fast-DetectGPT: Efficient Zero-Shot Detection of Machine-Generated Text via Conditional Probability Curvature." ICLR 2024. arXiv:2310.05130. https://arxiv.org/abs/2310.05130
- **Chakraborty et al. 2023** — Souradip Chakraborty, Amrit Singh Bedi, Sicheng Zhu, Bang An, Dinesh Manocha, Furong Huang. "On the Possibilities of AI-Generated Text Detection." arXiv:2304.04736. https://arxiv.org/abs/2304.04736
- **Creo & Pudasaini 2024** — Aldan Creo, Shushanta Pudasaini. "SilverSpeak: Evading AI-Generated Text Detectors using Homoglyphs." arXiv:2406.11239. https://arxiv.org/abs/2406.11239
- **Dathathri et al. 2024** — Sumanth Dathathri, Abigail See, Sumedh Ghaisas, Po-Sen Huang, et al. "Scalable watermarking for identifying large language model outputs." *Nature* 634, 818-823 (2024). doi:10.1038/s41586-024-08025-4. https://www.nature.com/articles/s41586-024-08025-4
- **Dugan et al. 2024** — Liam Dugan, Alyssa Hwang, Filip Trhlík, Josh Magnus Ludan, Andrew Zhu, Hainiu Xu, Daphne Ippolito, et al. "RAID: A Shared Benchmark for Robust Evaluation of Machine-Generated Text Detectors." ACL 2024 (long). https://aclanthology.org/2024.acl-long.674/ — arXiv:2405.07940; code: https://github.com/liamdugan/raid
- **Emi & Spero 2024** — Bradley Emi, Max Spero. "Technical Report on the Pangram AI-Generated Text Classifier." arXiv:2402.14873 (vendor technical report). https://arxiv.org/abs/2402.14873
- **Gehrmann et al. 2019** — Sebastian Gehrmann, Hendrik Strobelt, Alexander M. Rush. "GLTR: Statistical Detection and Visualization of Generated Text." ACL 2019 System Demonstrations. https://aclanthology.org/P19-3019/ — arXiv:1906.04043
- **Guo et al. 2023** — Biyang Guo, Xin Zhang, Ziyuan Wang, Minqi Jiang, Jinran Nie, Yuxuan Ding, Jianwei Yue, et al. "How Close is ChatGPT to Human Experts? Comparison Corpus, Evaluation, and Detection." arXiv:2301.07597. https://arxiv.org/abs/2301.07597
- **Hans et al. 2024** — Abhimanyu Hans, Avi Schwarzschild, Valeriia Cherepanova, Hamid Kazemi, Aniruddha Saha, Micah Goldblum, Jonas Geiping, et al. "Spotting LLMs With Binoculars: Zero-Shot Detection of Machine-Generated Text." ICML 2024, PMLR 235. https://proceedings.mlr.press/v235/hans24a.html — arXiv:2401.12070
- **Ippolito et al. 2020** — Daphne Ippolito, Daniel Duckworth, Chris Callison-Burch, Douglas Eck. "Automatic Detection of Generated Text is Easiest when Humans are Fooled." ACL 2020. https://aclanthology.org/2020.acl-main.164/ — arXiv:1911.00650
- **Kirchenbauer et al. 2023** — John Kirchenbauer, Jonas Geiping, Yuxin Wen, Jonathan Katz, Ian Miers, Tom Goldstein. "A Watermark for Large Language Models." ICML 2023, PMLR 202. https://proceedings.mlr.press/v202/kirchenbauer23a.html — arXiv:2301.10226
- **Kirchenbauer et al. 2024** — John Kirchenbauer, Jonas Geiping, Yuxin Wen, Manli Shu, Khalid Saifullah, Kezhi Kong, Kasun Fernando, et al. "On the Reliability of Watermarks for Large Language Models." ICLR 2024. arXiv:2306.04634. https://arxiv.org/abs/2306.04634
- **Kobak et al. 2025** — Dmitry Kobak, Rita González-Márquez, Emőke-Ágnes Horvát, Jan Lause. "Delving into LLM-assisted writing in biomedical publications through excess vocabulary." *Science Advances* 11(27), 2025. arXiv:2406.07016. https://arxiv.org/abs/2406.07016
- **Krishna et al. 2023** — Kalpesh Krishna, Yixiao Song, Marzena Karpinska, John Wieting, Mohit Iyyer. "Paraphrasing evades detectors of AI-generated text, but retrieval is an effective defense." NeurIPS 2023. https://papers.nips.cc/paper_files/paper/2023/hash/575c450013d0e99e4b0ecf82bd1afaa4-Abstract-Conference.html — arXiv:2303.13408
- **Li et al. 2024 (MAGE)** — Yafu Li, Qintong Li, Leyang Cui, Wei Bi, Zhilin Wang, Longyue Wang, Linyi Yang, et al. "MAGE: Machine-generated Text Detection in the Wild." arXiv:2305.13242. https://arxiv.org/abs/2305.13242
- **Liang et al. 2023** — Weixin Liang, Mert Yuksekgonul, Yining Mao, Eric Wu, James Zou. "GPT detectors are biased against non-native English writers." *Patterns* 4(7), 2023. https://www.cell.com/patterns/fulltext/S2666-3899(23)00130-7 — arXiv:2304.02819
- **Liang et al. 2024a** — Weixin Liang, Yaohui Zhang, Zhengxuan Wu, Haley Lepp, Wenlong Ji, Xuandong Zhao, Hancheng Cao, et al. "Mapping the Increasing Use of LLMs in Scientific Papers." arXiv:2404.01268. https://arxiv.org/abs/2404.01268
- **Liang et al. 2024b** — Weixin Liang, Zachary Izzo, Yaohui Zhang, Haley Lepp, Hancheng Cao, Xuandong Zhao, Lingjiao Chen, et al. "Monitoring AI-Modified Content at Scale: A Case Study on the Impact of ChatGPT on AI Conference Peer Reviews." ICML 2024, PMLR 235. https://proceedings.mlr.press/v235/liang24b.html — arXiv:2403.07183
- **Macko et al. 2023 (MULTITuDE)** — Dominik Macko, Robert Moro, Adaku Uchendu, Jason Samuel Lucas, Michiharu Yamashita, Matúš Pikuliak, Ivan Srba, et al. "MULTITuDE: Large-Scale Multilingual Machine-Generated Text Detection Benchmark." EMNLP 2023. https://aclanthology.org/2023.emnlp-main.616/ — arXiv:2310.13606
- **Mitchell et al. 2023** — Eric Mitchell, Yoonho Lee, Alexander Khazatsky, Christopher D. Manning, Chelsea Finn. "DetectGPT: Zero-Shot Machine-Generated Text Detection using Probability Curvature." ICML 2023, PMLR 202. https://proceedings.mlr.press/v202/mitchell23a.html — arXiv:2301.11305
- **Muñoz-Ortiz et al. 2024** — Alberto Muñoz-Ortiz, Carlos Gómez-Rodríguez, David Vilares. "Contrasting Linguistic Patterns in Human and LLM-Generated News Text." *Artificial Intelligence Review* 57, 265 (2024). arXiv:2308.09067. https://arxiv.org/abs/2308.09067
- **Reinhart et al. 2025** — Alex Reinhart, Ben Markey, Michael Laudenbach, Kachatad Pantusen, Ronald Yurko, Gordon Weinberg, David West Brown. "Do LLMs write like humans? Variation in grammatical and rhetorical styles." *PNAS* 122 (2025), e2422455122. arXiv:2410.16107. https://arxiv.org/abs/2410.16107
- **Russell et al. 2025** — Jenna Russell, Marzena Karpinska, Mohit Iyyer. "People who frequently use ChatGPT for writing tasks are accurate and robust detectors of AI-generated text." arXiv:2501.15654. https://arxiv.org/abs/2501.15654
- **Sadasivan et al. 2023** — Vinu Sankar Sadasivan, Aounon Kumar, Sriram Balasubramanian, Wenxiao Wang, Soheil Feizi. "Can AI-Generated Text be Reliably Detected?" arXiv:2303.11156. https://arxiv.org/abs/2303.11156
- **Saha & Feizi 2025** — Shoumik Saha, Soheil Feizi. "Almost AI, Almost Human: The Challenge of Detecting AI-Polished Writing." arXiv:2502.15666. https://arxiv.org/abs/2502.15666
- **Sun et al. 2025** — Mingjie Sun, Yida Yin, Zhiqiu Xu, J. Zico Kolter, Zhuang Liu. "Idiosyncrasies in Large Language Models." arXiv:2502.12150. https://arxiv.org/abs/2502.12150
- **Verma et al. 2024** — Vivek Verma, Eve Fleisig, Nicholas Tomlin, Dan Klein. "Ghostbuster: Detecting Text Ghostwritten by Large Language Models." NAACL 2024. https://aclanthology.org/2024.naacl-long.95/ — arXiv:2305.15047
- **Wang et al. 2023 (SeqXGPT)** — Pengyu Wang, Linyang Li, Ke Ren, Botian Jiang, Dong Zhang, Xipeng Qiu. "SeqXGPT: Sentence-Level AI-Generated Text Detection." arXiv:2310.08903. https://arxiv.org/abs/2310.08903
- **Wang et al. 2024 (M4)** — Yuxia Wang, Jonibek Mansurov, Petar Ivanov, Jinyan Su, Artem Shelmanov, Akim Tsvigun, Chenxi Whitehouse, et al. "M4: Multi-generator, Multi-domain, and Multi-lingual Black-Box Machine-Generated Text Detection." EACL 2024. https://aclanthology.org/2024.eacl-long.83/ — arXiv:2305.14902
- **Wang et al. 2024b (M4GT-Bench)** — Yuxia Wang, Jonibek Mansurov, Petar Ivanov, Jinyan Su, Artem Shelmanov, Akim Tsvigun, Osama Mohammed Afzal, et al. "M4GT-Bench: Evaluation Benchmark for Black-Box Machine-Generated Text Detection." ACL 2024. https://aclanthology.org/2024.acl-long.218/ — arXiv:2402.11175
- **Weber-Wulff et al. 2023** — Debora Weber-Wulff, Alla Anohina-Naumeca, Sonja Bjelobaba, Tomáš Foltýnek, Jean Guerrero-Dib, Olumide Popoola, Petr Šigut, et al. "Testing of Detection Tools for AI-Generated Text." *International Journal for Educational Integrity* 19, 26 (2023). arXiv:2306.15666. https://arxiv.org/abs/2306.15666

### Provider claims

- **GPTZero 2023** — GPTZero. "Perplexity, Burstiness, and Statistical AI Detection." 2023-03-01, with later note that GPTZero no longer uses perplexity and burstiness as of autumn 2023. https://gptzero.me/news/perplexity-and-burstiness-what-is-it/
- **OpenAI 2023** — OpenAI. "New AI classifier for indicating AI-written text." January 2023; updated 2023-07-20: classifier withdrawn "due to its low rate of accuracy". https://openai.com/index/new-ai-classifier-for-indicating-ai-written-text/
- **Turnitin 2023a** — Turnitin. "Understanding false positives within our AI writing detection capabilities." https://www.turnitin.com/blog/understanding-false-positives-within-our-ai-writing-detection-capabilities
- **Turnitin 2023b** — Turnitin. "Understanding the false positive rate for sentences of our AI writing detection capability." https://www.turnitin.co.uk/blog/understanding-the-false-positive-rate-for-sentences-of-our-ai-writing-detection-capability
- **Higher Ed Dive 2023** — Higher Ed Dive news report on Turnitin's false-positive disclosures and its raised 300-word minimum (2023). https://www.highereddive.com/news/turnitin-false-positives-AI-detector/652356/

### Practitioner guides and popular coverage (folklore context)

- **Wikipedia: Signs of AI writing** — WikiProject AI Cleanup. "Wikipedia:Signs of AI writing" (descriptive field guide; explicitly "observations, not rules"). https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing
- **NPR 2025** — NPR. "Inside the unofficial movement to save the em dash from A.I." 2025-11-10. https://www.npr.org/2025/11/10/nx-s1-5596088/inside-the-unofficial-movement-to-save-the-em-dash-from-a-i
