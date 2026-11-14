# v4 design tools (2026-09-27)

Helpers used to draw v4's forced sea line by hand: `trace_ocean_line.py` (first trace through NACCS save points at
~10 m), `label_naccs_nodes.py` + `build_node_picker.py` / `node_picker_template.html` (the clickable NACCS node picker
the user routed the line with), `river_widths.py` (channel widths for the narrow-channel rule; re-used 11-14 by the nj2
refinement work). The line itself is `data/v4_design/waterlevel_line_v4.csv` (FINDINGS part 4). README written at the
11-14 wrap-up (the dir was touched when its `river_widths.py` was imported for nj2).
