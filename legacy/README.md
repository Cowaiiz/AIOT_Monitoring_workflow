# Legacy prototypes

This directory retains earlier project stages so their behavior and measurements can be reviewed without confusing them with the real-image application.

| Prototype | Purpose | Requires model weights? |
|---|---|---|
| [http-mock](http-mock/README.md) | Send synthetic scores through validation, thresholding and alert acknowledgment | No |

Start with http-mock if you want to learn the workflow or verify Node-RED connectivity before setting up the ML environment.

The legacy alert engine uses RAM and loses state on restart/redeployment. The current [real-image demo](../demo/README.md) uses SQLite. Do not assume that the newer storage guarantees apply to the legacy version.

[Project overview](../README.md) · [Implementation report](../reports/IMPLEMENTATION_REPORT.md)
