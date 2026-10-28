# Verification record

Verified on 2026-10-27 using synthetic data only.
No production company database was connected.

## Passed

- Six Python unit tests covering company configuration, duplicate company rejection, missing credentials, source-column allowlists, incompatible schemas and decimal/timestamp preservation.
- Ruff checks.
- Docker Compose configuration validation for both demo and dump profiles.
- Shell syntax validation for PostgreSQL initialization.
- dbt project parsing.
- Native integration with isolated MySQL 9.6.0 and PostgreSQL 16.13 instances.
- Integration builds executing 15 dbt models and four data tests.

## End-to-end evidence

| Scenario | Result |
|---|---|
| Initial load of two companies with reused source IDs/invoice numbers | Separate AED and SAR results, 330 net sales each |
| Repeat incremental load | No duplicated sales lines |
| Update an existing invoice line | Updated value reflected |
| Void an existing invoice | Its lines excluded from reports |
| Company A changes | Company B remained at 330 |
| Connection to missing source database | Load failed and previous raw data remained |
| Controlled PostgreSQL failure after sales rows were written | Entire company transaction rolled back |
| Remove failure and perform full load | Load succeeded |
| Source hard deletion followed by full load | Deleted line removed from warehouse |
| Read marts as BI role | Succeeded |
| Read raw records or attempt a raw write as BI role | Rejected with insufficient privilege |
| Read marts again after denied operations | Succeeded |

The native runner stopped both temporary servers and removed their data after the test.

## Not executed

The Docker daemon was unavailable, so container image builds, execution against the configured MySQL 8.4/PostgreSQL 17 images, and live Metabase dashboard provisioning were not executed.
The Metabase dashboard-update request shape was checked against the upstream v0.56.1 API source, but this is not a substitute for a live provisioning check.
Actual company schemas, remote connectivity/TLS, real dumps and application-report reconciliation still require company data/access.

## Reproduce

Use `make test`, `make demo`, `make integration` and `make dashboard` as documented in the README.
When Docker is unavailable, use `scripts/verify_local.py` with installed server binary paths.

## Subsequent Docker and KAKU verification

The initial Docker limitation above was subsequently resolved by starting Docker Desktop.
The pipeline image built successfully and all 15 models and four data checks passed against PostgreSQL 17 in Docker.
The synthetic demo source ran MySQL 8.4.
Metabase v0.56.1 provisioning and an authenticated browser check succeeded.

KAKU was selectively restored into a separate MySQL 9.6 database, `tenant_kaku_sales`, using 11 source tables.
The warehouse loaded the inclusive date window 2026-09-28 through 2026-10-27.
Actual transaction dates were 2026-10-07 through 2026-10-26.
Source and warehouse agreed on 53 invoices, 96 lines, SAR net sales of 1,835.1500 and INR net sales of 500.0000.
The same window was loaded twice with unchanged totals and zero out-of-window fact rows.
All six KAKU Metabase questions executed successfully, and the browser displayed both currencies without demo company rows or error cards.

The updated test suite passed eight unit tests and two isolated native integration tests.
The new tests cover selected-table dump extraction, matching header/line date predicates, repeated bounded loads, stored coverage and rejection of unrestricted incremental loading after a bounded snapshot.
Ruff and Docker Compose configuration checks passed.

During a model rebuild at 14:09:14 UTC, a concurrent Metabase product query briefly failed because the dependent view was being recreated.
The PostgreSQL log confirmed the timing.
After the build, the relation existed, direct SQL returned the reconciled totals, and all six saved questions executed successfully.
Live model rebuilding is not a zero-downtime publication mechanism; production publication gates remain future work.
