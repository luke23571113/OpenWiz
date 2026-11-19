# Scale-50 kit

**Kept (MT11, #830):** it tests the scale report contract: `report.py` validates and compares `openwiz.scale-50.v1` reports, `tools/fleet-load/scale.py` reads its reports through it, and open spec #77 builds its live baseline (#81) and final proof (#85) on `report-format.md`.

The contract is [report-format.md](report-format.md); its synthetic examples are in [fixtures/](fixtures/README.md).

```sh
python3 -I tools/fleet-load/scale-50/report.py REPORT [--compare CANDIDATE]
python3 -I tools/fleet-load/scale-50/test_report.py
```
