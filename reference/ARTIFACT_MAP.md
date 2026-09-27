# Generated Artifact Map

The Git repository stores the canonical source inputs and implementation files. Generated delivery artifacts are intentionally not duplicated as opaque binaries when their contents are already represented losslessly in source form.

| Generated artifact | Canonical repository source |
|---|---|
| `Food_History_Master_Taxonomy_v1.1.xlsx` | `seeds/taxonomy/*`, `seeds/taxonomy/manifest.json`, taxonomy documentation |
| `Food_History_Database_Schema_and_Data_Dictionary_v1.0.xlsx` | `migrations/*`, architecture/docs, controlled-vocabulary rules |
| `Food_History_Database_Schema_v1.0_PostgreSQL.sql` | Ordered migrations `0001`–`0012` |
| `Food_History_Backend_Phase1_Implementation_v1.0.zip` | Entire repository source tree |
| Preview PNGs | Generated presentation/QA previews only; not canonical research or application data |

## Release policy

For formal releases, generate downloadable XLSX/SQL/ZIP artifacts from a tagged/identified commit and attach them to the release. The commit SHA, schema version, and taxonomy version should be recorded with each generated artifact.

This keeps Git history reviewable while ensuring every published binary can be traced back to reproducible source.
