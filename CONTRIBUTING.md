# Contributing

Thanks for helping. Chronicle is a small Python project with no build step for the dashboard.

1. `uv sync && uv run pytest -q` runs the tests in about 12 seconds. They use a fake `claude` binary and synthetic
   Codex, Copilot and Bob stores, so they never touch your real data or spend tokens.
2. `uv run python -m chronicle ui --port 8799` serves the dashboard from your checkout. To work on it without your
   own sessions, build the demo home first (see [Demo data](docs/development.md#demo-data)).
3. `uv run --extra app python -m chronicle app` runs the macOS app from the checkout.

[docs/development.md](docs/development.md) covers the code layout, building the app and releasing.

When you open a pull request, say what changed and how you checked it, and include a screenshot for UI changes
(taken from the demo data, not your own sessions). Please keep all data local: Chronicle must not send anything
anywhere except the analysis calls through the user's own `claude`.
