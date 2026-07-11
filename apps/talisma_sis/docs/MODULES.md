# Module Map

> Detailed ownership, capabilities, candidate records, dependencies, integrations, and build classifications are defined in [Module Architecture](modules/MODULE_ARCHITECTURE.md).

This document defines anticipated product boundaries. It does not authorize creation of DocTypes; each module requires a reviewed domain design first.

## Admissions

Owns recruitment-to-admission processes: applications, requirements, reviews, decisions, offers, and matriculation handoff. It must preserve decision history and avoid creating duplicate person or student identities.

## Student Information

Owns the authoritative student academic profile, statuses, institutional relationships, privacy indicators, and effective-dated history. Shared person data must align with the chosen identity model.

## Course and Curriculum Management

Owns programs, credentials, catalogs, curricula, courses, requisites, equivalencies, and governance. Curriculum versions must remain reproducible for historical students.

## Registration

Owns section enrollment and lifecycle events, including eligibility, capacity, windows, holds, waitlists, overrides, adds, drops, withdrawals, and audit history.

## Degree Audit

Evaluates a student's completed and in-progress work against an assigned curriculum version. Results must be explainable and reproducible.

## Academic Advising

Supports advisor assignments, academic plans, recommendations, approvals, and appropriately restricted notes. Advising access must be narrower than general administrative access.

## Attendance

Records attendance or participation against valid section enrollments and published schedules. Aggregation rules must remain configurable and traceable.

## Assessments

Supports assessment structures, results, grade calculation, submission, approval, publication, and controlled grade changes.

## Transcript Management

Produces authoritative academic histories from governed source records. Transcript calculation, formatting, release authorization, and reissue history require strict controls.

## Graduation

Coordinates graduation applications, degree-audit completion, institutional clearances, approvals, conferral, and credential records.

## Financial Aid

Supports aid applications, eligibility, awards, packaging, disbursement, and reconciliation while integrating financial postings with ERPNext rather than duplicating accounting.

## Billing

Translates academic events and institutional policies into student charges, payments, refunds, sponsorships, and account views backed by ERPNext financial records.

## Faculty Portal

Provides scoped access to assigned sections, rosters, attendance, assessments, grading, and advisees. Faculty access must derive from active institutional assignments.

## Student Portal

Provides secure self-service access to applications, profile maintenance, registration, schedules, results, finances, documents, requests, and notifications.

## FERPA and permissions

Provides cross-cutting privacy classification, access policy, disclosure controls, audit evidence, and operational review. It is an architectural concern across every module, not a standalone checkbox.

## Reports and analytics

Provides governed operational reports and approved analytical outputs. Metrics require shared definitions, appropriate row-level access, and documented data freshness.

## Shared platform capabilities

Identity, institutional structure, academic periods, policy configuration, integrations, notifications, attachments, audit, and reference data are shared foundations. They should not be reimplemented independently by each module.
