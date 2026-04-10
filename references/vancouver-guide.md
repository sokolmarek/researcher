# Vancouver Citation Style — Quick Reference

Loaded by citation-management and journal-formatting skills. Standard for biomedical journals (ICMJE recommendations).

## In-Text Citations

- Numbered in order of first appearance: superscript or in parentheses
- Superscript style: Smith demonstrated¹ that...
- Parenthetical style: Smith demonstrated (1) that...
- Multiple: (1,2,5) or ranges: (1-3)
- Same number if re-cited

## Reference List Format

### Journal Article
1. Author AA, Author BB, Author CC. Title of article. Abbreviated Journal Name. Year;Volume(Issue):Pages. doi:10.xxxx/xxxxx.

### Book
2. Author AA, Author BB. Title of Book. Edition. Place: Publisher; Year.

### Book Chapter
3. Author AA. Title of chapter. In: Editor AA, Editor BB, editors. Title of Book. Place: Publisher; Year. p. Pages.

### Conference Paper
4. Author AA. Title of paper. In: Proceedings of Conference Name; Year Month Days; City, Country. Place: Publisher; Year. p. Pages.

### Website
5. Author AA. Title of page [Internet]. Place: Publisher; Year [cited Year Month Day]. Available from: URL

### Thesis
6. Author AA. Title of thesis [dissertation]. Place: University; Year.

## Key Rules

- Abbreviate journal names per NLM catalog (Index Medicus)
- List up to 6 authors; 7+: list first 6 then "et al."
- Author format: Surname followed by initials with no periods or spaces (Smith JA, not Smith, J. A.)
- No italics on journal or book titles
- Numbered sequentially by first appearance
- No hanging indent
- Period at end of each reference

## Common Journal Abbreviations

- The Lancet → Lancet
- New England Journal of Medicine → N Engl J Med
- British Medical Journal → BMJ
- Journal of the American Medical Association → JAMA
- Nature Medicine → Nat Med
- PLOS ONE → PLoS One

## LaTeX Implementation

```latex
\usepackage[numbers,super]{natbib}
\bibliographystyle{vancouver}
```

Or with biblatex:
```latex
\usepackage[style=vancouver]{biblatex}
```
