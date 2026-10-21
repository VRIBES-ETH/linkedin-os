# Contributing

The most useful contribution is a verified source.

1. Confirm the feed responds and entries carry a date and a link:
   `python3 -c "import urllib.request;print(urllib.request.urlopen('<feed url>').read()[:400])"`
2. Decide the tier by the rule in the README (regulator, central bank, institution, the company itself or a primary research house = 1; press, wires, aggregators = 2).
3. Add the entry to `fuentes/fuentes.json` with `activo: true` and today's date in `nota`.
4. Run `python3 scripts/radar.py --horas 72 --sin-estado --sin-temas` and check the source appears without errors.

Bug reports on the scanner, the hooks or the Publer notes are welcome as issues. Keep pull requests small: one source or one fix each.
