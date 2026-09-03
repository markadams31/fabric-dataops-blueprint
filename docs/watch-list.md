# Watch list

Upstream changes that should trigger a design revisit. Each row names its trigger and
the response — check them when bumping tool versions.

| What | Where | Trigger | Response |
|---|---|---|---|
| TMDL-aware `key_value_replace` for semantic models | [fabric-cicd #552](https://github.com/microsoft/fabric-cicd/issues/552) (PR open) | Ships in a release | Use it for the semantic model's `expressions.tmdl` rewrite instead of `find_replace` |
| Validate-only / dry-run mode | [fabric-cicd issues](https://github.com/microsoft/fabric-cicd/issues) | Ships | Add to `pr-validation` as a cloud-free publish check |
| Schedule pause/resume around deployments | fabric-cicd feature request | Ships | Consider adopting in the deploy phase before prod schedules exist |
| Full-Lakehouse / Warehouse-schema deployment | fabric-cicd feature requests | Ships | **Do not adopt blindly** — would overlap dbt's ownership of the warehouse (one owner per store) |
| `deploy_with_config` | [config-based deployment](https://microsoft.github.io/fabric-cicd/latest/how_to/config_deployment/) | When orphan control / per-environment publish differences land here | Candidate replacement for the publish block in `deploy.py` |
| `executeQueries` for service principals | Power BI REST API | Tenant behaviour changes (currently 401 for ALL SPN types here, every documented switch satisfied — see evidence 2026-09-03-serve) | Reinstate a DAX smoke against the semantic model in `deploy.py` |
| Finer-grained OneLake read on warehouses | Fabric release notes (OneLake security / item ReadAll via API) | A Terraform-manageable read-only grant appears | Downgrade the cross-solution contract grant from Contributor to it — workspace Viewer does not confer OneLake read |
| PBIR becomes the enforced report format | Fabric release notes | GA (announced Q3 2026) | Format already used here; confirm nothing breaks |
| Fabric Git integration read-write requirement | [Git limitations](https://learn.microsoft.com/fabric/cicd/git-integration/git-integration-process#considerations-and-limitations) | 2026-12-01 | Verify branched-workspace flow for Viewer-only users |
| Workspace item Bulk Import/Export APIs | [Fabric CI/CD announcement](https://community.fabric.microsoft.com/blog/fbc_fabricupdatesblogs/new-cicd-resources-for-microsoft-fabric-from-concepts-to-end-to-end-automation/5358502) (Mar 2026) | GA | Evaluate as a definitions backup/restore mechanism for the README's system-of-record caveat — Microsoft still recommends fabric-cicd for deployment |
