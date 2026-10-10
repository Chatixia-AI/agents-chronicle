- **Analyze the queue now:** **Status › Analysis** has an **Analyze N now** button under the queue. It analyzes the
  sessions ready now at once instead of waiting for the background run, even with automatic analysis off or during a
  usage-limit pause, which it lifts when it gets through. When nothing is ready but sessions are still active, it
  offers to analyze those. It's in the command palette too, and the stale "Paused until" line that stayed after a
  pause ran out is gone ([How analysis works](docs/analysis.md)).
