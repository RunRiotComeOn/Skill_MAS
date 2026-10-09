# BrowseComp-Plus profile (`bcp`)

Adapted from [optimized_skill/bcp.md](https://github.com/linhh29/Skill_MAS/blob/b55d47e/optimized_skill/bcp.md).
Use for source-grounded retrieval and entity identification from multiple clues.

1. **Map the clues.** Distinguish essential constraints from supporting clues.
   Rank clues by specificity and independence; several repetitions of one fact
   are not independent confirmation.
2. **Search in bounded parallel branches.** Group related clues into up to four
   coherent retrieval tasks. Maintain multiple candidate hypotheses until the
   evidence distinguishes them. Each branch returns candidates, sources, and
   supported, missing, or contradicted constraints.
3. **Adapt a weak search.** Start with the original clue. If evidence is sparse,
   broaden the least specific search term, then try candidate-anchored queries
   for remaining clues. Broader queries do not relax the user's acceptance
   criteria. Stop when evidence is sufficient or the search budget is exhausted.
4. **Verify relationships explicitly.** If clues concern separate entities,
   assign a link-verification step after candidate retrieval to establish the
   relationship itself, using sources rather than name co-occurrence.
5. **Let the merger investigate.** Give the merge/verifier role retrieval access
   when the host provides it. It should pursue missing or contradictory evidence
   and compare the candidates against the full constraint set.
6. **Report calibrated conclusions.** Return the supported answer with sources.
   If evidence cannot establish a unique match, explain the uncertainty and
   remaining clues; label a tentative candidate as tentative.

The source's weighted evidence strategy guides search priority. Its numerical
thresholds are not calibrated confidence probabilities, and a high weighted
score cannot override a contradicted essential constraint. The benchmark's
literal `UNANSWERABLE` format applies only if the user requests it. Live web or
repository search may replace benchmark BM25 retrieval when available.
