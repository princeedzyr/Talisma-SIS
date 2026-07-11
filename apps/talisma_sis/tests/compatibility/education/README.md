# Frappe Education v16 Compatibility Evaluation

This directory defines an isolated technical evaluation for ADR-001. It does not modify or share the `talisma.local` database, sites volume, Redis data, network, or frontend port.

## Pinned versions

- Frappe Framework: `v16.25.0`
- ERPNext: `v16.26.2`
- Frappe Education: `v16.0.1`
- Talisma SIS: current working tree

## Isolation

- Compose project: `talisma-education-eval`
- Site: `education-eval.local`
- Frontend: `http://127.0.0.1:8082`
- Named volumes and network are generated under the evaluation project.

## Purpose

The environment supports installation, migration, schema, role, workspace, API, accounting, portal, backup, and restore evaluation. It is disposable and must never be used for production or real student data.

The evaluation Containerfile follows frappe_docker's layered image recipe and increases only Yarn's network timeout to accommodate slower Docker Desktop dependency downloads. It also normalizes copied shell scripts to LF so images built from a Windows checkout remain executable.

Evaluation results are recorded in [the fit-gap report](../../../docs/architecture/FRAPPE_EDUCATION_V16_FIT_GAP_REPORT.md).

## Safety

Do not run evaluation commands without the explicit project name and override file. Never use `down -v` against the normal Talisma project.
