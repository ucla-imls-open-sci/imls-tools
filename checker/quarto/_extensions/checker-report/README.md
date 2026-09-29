Quarto custom format extension used by `checker/report.py` for `--html`/`--pdf`
output. Not meant to be installed standalone with `quarto add` -- `report.py`
copies this directory into the temporary render directory next to the
generated `.qmd` at render time, which is how Quarto discovers any
`_extensions/` directory.

Defines two formats, `checker-report-html` and `checker-report-pdf`, both
extending Quarto's defaults with `toc: true` plus report-specific styling
(`checker-report.scss` for HTML; margins/link color for PDF). Edit
`_extension.yml`/`checker-report.scss` here to change how every rendered
report looks; `report.py` itself only decides *what* the report says.

Link color is The Carpentries' official navy (`#071159`) and the rule under
each file heading is their red (`#FF4955`) -- see
https://docs.carpentries.org/topic_folders/communications/resources/logos.html
for the source. Colors only: the actual logo mark (github.com/carpentries/logo)
ships with no LICENSE, and Carpentries' own docs require prior approval
(community@carpentries.org) for any derived/modified use of the mark itself,
so nothing from that repo is vendored here.
