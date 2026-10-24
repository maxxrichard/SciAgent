# Adding a tool

1. **Implement** a pydantic input model and a pure function in the relevant module under
   `src/sciagent/tools/` (or a new module), returning a JSON-serialisable `dict`.
   Constrain identifiers with `pattern=` and numeric arguments with `ge`/`le`; these
   constraints are carried into the MCP schema.
2. **Register** it by appending a `Tool(...)` to that module's `TOOLS` list, choosing the
   MCP server (`imaging`, `genomics`, `clinical`).
3. **Govern** it: add an entry to `src/sciagent/governance/policies.yaml` with its data
   group, budget and row limits. Tools missing from the policy are denied.
4. **Test** it: unit tests for the scientific logic, plus a policy test.
5. **Evaluate** it: add tasks to `evals/tasks/<category>.jsonl`, including at least one
   `numbers` check and one governance task where the call must be denied.
6. Open a PR; the eval gate must pass.
