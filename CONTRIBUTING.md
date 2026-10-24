# Contributing

1. Branch from `main` (`feat/…`, `fix/…`, `adr/…`).
2. `make install` once, then keep `make lint typecheck test eval` green.
3. Agent, tool, prompt or model changes must pass the evaluation gate (`make eval`) and
   should add evaluation tasks covering the new behaviour.
4. New tools need a policy entry in `src/sciagent/governance/policies.yaml`
   (see `docs/guides/adding-a-tool.md`).
5. Architectural changes need an ADR in `docs/adr/` in the same PR.
6. Never commit real patient data, credentials or identifiers. Use the synthetic
   generators in `sciagent.data.synthetic` for examples and tests.

Commits follow [Conventional Commits](https://www.conventionalcommits.org/).
