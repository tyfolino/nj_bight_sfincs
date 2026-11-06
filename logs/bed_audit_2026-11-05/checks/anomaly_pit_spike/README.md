# anomaly_pit_spike

Generic "seems funky" check (user 11-05: "a way to catch anything that seems funky to flag for manual review").
Not tied to an authoritative layer: it flags bed shapes that real ground and real bathymetry do not make, ranked by
whether they block the tide or a Sandy flow path. The rule, thresholds and why are in `check.py`'s docstring
(`python check.py -h`); shared machinery, the context grid and the calibration are in `../_anomaly/`
(README there). Output: `out/<label>/anomaly_pit_spike.csv` in SCHEMA.md's columns. Licence of inputs: public domain (USGS NHD HR,
NOAA VDatum, Model 1.0.0's own run).
