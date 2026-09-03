# Item-type coverage: Fabric's catalog vs fabric-cicd — the basis for the scope

**Date** 2026-09-03 · Sources: installed fabric-cicd 1.3.0 `ACCEPTED_ITEM_TYPES`,
[item management API support](https://learn.microsoft.com/rest/api/fabric/articles/item-management/item-management-overview),
[Git integration supported items](https://learn.microsoft.com/fabric/cicd/git-integration/intro-to-git-integration#supported-items)

## fabric-cicd deploys 29 item types

ApacheAirflowJob · CopyJob · DataAgent · DataBuildToolJob · DataPipeline ·
Dataflow · Environment · Eventhouse · Eventstream · GraphQLApi · KQLDashboard ·
KQLDatabase · KQLQueryset · Lakehouse · Map · MirroredDatabase · MLExperiment ·
MountedDataFactory · Notebook · Ontology · PaginatedReport · Reflex · Report ·
SemanticModel · SparkJobDefinition · SQLDatabase · UserDataFunction ·
VariableLibrary · Warehouse

`deploy.py` takes this list from the library at runtime, so newly supported types
flow into deployments with a version bump and no code change.

## The gap, by reason

| Item types | Why fabric-cicd doesn't deploy them | Verdict |
|---|---|---|
| SQLEndpoint, MirroredWarehouse | Auto-provisioned children of Lakehouse/Warehouse — no create API by design | Not a gap: they arrive with their parent |
| Dashboard, Scorecard, Datamart, streaming dataflows/datasets | Legacy/UI-only — no API, no Git support | The one real user-facing gap; nothing can code-manage these. Build reports, not dashboards |
| MLModel (and MLExperiment content) | Run-produced, not authored — no definition API | Marginal by nature |
| OrgApp / OrgAppAudience | APIs exist; fabric-cicd removed org apps and tracks reintroduction ([#1026](https://github.com/microsoft/fabric-cicd/issues/1026)) | Temporary, upstream roadmap |
| Digital Twin Builder, EventSchemaSet, Graph model/queryset, Cosmos DB, Snowflake DB, AzureDatabricksStorage, Mirrored catalogs | Newer/preview types (several still lack service-principal support) not yet absorbed by fabric-cicd | The moving frontier — historically absorbed within a release or two |

## Conclusion (decision D23)

Scoping the project to "what fabric-cicd deploys, plus dbt as the transformation
engine" is very nearly scoping to "what Fabric permits to be deployed as code at
all". The excluded remainder is either impossible for any tool (no API), produced
by runs rather than authored, or upstream's short-term backlog.
