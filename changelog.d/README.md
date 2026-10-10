# changelog.d

A pull request that users will notice adds one file here, named after its topic (`menu-bar.md`, `postgres-mirror.md`),
holding its changelog line, written the same way as the lines in [CHANGELOG.md](../CHANGELOG.md):

```markdown
- **A copy in Postgres:** Chronicle can keep a copy of your archive in a Postgres database you choose. Set it up under
  **Settings › Storage** ([A copy in Postgres](docs/postgres.md)).
```

Links are relative to the repository root, as in CHANGELOG.md. Don't edit CHANGELOG.md itself, and don't start an
`## Unreleased` section there: the **Changelog** check fails both a pull request that changes `src/`, `ee/src/`,
`docker/` or `vscode-extension/` without a new file here and one that adds lines under `## Unreleased`. Label a pull
request `no-changelog` when users won't notice anything.

A release's notes are the files added here since the previous tag, in the order they were merged, so a pull request
merged at any moment (even during a release) goes out in exactly one release. After publishing, the release opens a
pull request that moves its files' lines into CHANGELOG.md under `## <version> (<date>)` and deletes them; files merged
since stay for the next release, and the next release doesn't wait for that pull request.
