// Compatibility entry for the current intake regression.
// The retired P5 harness assumed anonymous plan creation without Auth and a
// separate confirmation/navigation button. Run intake_ui_server.py on :18083
// and Next on :15103, as documented by intake-flow.mjs.
if (process.env.P5_WEB_ORIGIN && !process.env.INTAKE_WEB_ORIGIN) process.env.INTAKE_WEB_ORIGIN = process.env.P5_WEB_ORIGIN;
await import('./intake-flow.mjs');
