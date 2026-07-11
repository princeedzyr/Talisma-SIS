# Institutional Hierarchy Standard DocType Fit-Gap

Status: **Accepted supporting analysis under ADR-003**

Evidence source: metadata inspected from the project's ERPNext v16 image and isolated Frappe Education v16.0.1 evaluation image on 2026-07-11. No standard metadata or database state was changed.

## Summary

| Standard record | Authoritative use | Gap | Talisma treatment |
|---|---|---|---|
| ERPNext `Company` | Legal entity, accounting books and defaults | Not an academic institution or campus | Map explicitly to Talisma Institution; never create for ordinary academic units |
| ERPNext `Department` | Company-bound operational/HR department tree | Current-state tree lacks academic type, versioned structure and cross-company governance | Map to Academic Unit where operational equivalence exists |
| ERPNext `Branch` | Lightweight organizational/location label | Only a unique name; no institution, address, hierarchy or effective dates | Do not use as campus master; optional mapping only |
| ERPNext `Cost Center` | Company-bound financial responsibility tree | Accounting purpose and current tree do not equal academic governance | Effective-dated financial mapping from academic unit |
| Education `Program` | Program master and Department association | One current Department; no effective ownership or joint ownership | Preserve Program; add effective Talisma ownership assignment if ADR-001 permits Education |
| Education `Course` | Course master and Department association | One current Department; no historical/joint/cross-campus ownership | Preserve Course; add effective Talisma ownership assignment |
| Education `Instructor` | Teaching profile with Employee/Department links | Current Department is not appointment or academic governance history | Preserve Instructor; use separate effective assignments |
| Education `Room` | Room name, number and capacity | No campus/building/location hierarchy | Reuse only as scheduling room after separate facilities mapping |

## Company

Observed metadata requires company name, abbreviation, country, currency and valuation method. It owns chart-of-accounts creation, default accounts, inventory, tax, banking, finance books, cost centers and accounting controls. Company is itself a nested-set legal/accounting hierarchy.

### Decision

Company remains the authority for accounting and legal-entity configuration. A Talisma Institution may map to one or more Companies where accounting structures require it. A Company-to-Institution mapping must declare purpose and effective interval. Company is not the identity `institution_scope` because legal consolidation and academic/security boundaries are not guaranteed to coincide.

## Department

Observed metadata contains required department name and Company, optional parent Department, group and disabled flags, plus nested-set fields.

### Decision

Department remains the operational/HR tree inside a Company. It may map to an Academic Unit, but neither record is automatically created or renamed from the other. The mapping is explicit and effective-dated. Department cannot represent every college, faculty, institute, cross-company unit or historical academic structure.

## Branch

Observed metadata contains one required unique `branch` Data field and no Company, address, location, hierarchy, type, status or effective-date fields.

### Decision

Branch is insufficient as the campus master. Talisma requires its own Campus record and may optionally map a Campus to Branch for HR or operational compatibility. The mapping does not make Branch authoritative for campus identity.

## Cost Center

Observed metadata contains required name, parent and Company, optional number/group/disabled flags and nested-set fields.

### Decision

Cost Center remains the financial-responsibility hierarchy. Academic Units map to one or more Cost Centers by institution, Company, purpose and effective interval. Academic reorganization must not silently rewrite accounting mappings or historical ledger dimensions.

## Education Program and Course

Observed Program and Course records each have a single optional Department link. Program has a unique program name, abbreviation and course child table. Course has a unique course name, topics and assessment fields.

### Decision

The Department link may remain for upstream Education behavior if ADR-001 is accepted, but it cannot be Talisma's authoritative academic-ownership history. Talisma ownership assignments support primary, joint and administrative ownership with effective dates and structure-version context. Existing Department fields are synchronized only through an explicit adapter policy, never uncontrolled bidirectional hooks.

## Education Instructor

Observed Instructor optionally links Employee and Department and owns teaching-specific status.

### Decision

Department remains an upstream current convenience field. Faculty appointment, home academic unit, teaching assignment and administrative responsibility are different relationships and require effective-dated Talisma assignments in their owning modules.

## Education Room

Observed Room contains name, number and capacity only.

### Decision

Room can remain a scheduling resource, but Campus and facility hierarchy require separate ownership. Room names/numbers are not assumed globally unique without a campus/building namespace.

## Reuse rules

- Do not modify ERPNext or Education core JSON/Python.
- Do not create Company to represent a school, faculty or department.
- Do not treat Department parent changes as academic history.
- Do not treat Branch as a complete campus/location master.
- Do not copy Cost Center hierarchy into academic units.
- Use explicit, effective-dated mappings with validation and reconciliation.
- Keep all Education targets optional until ADR-001 is accepted.
- Historical academic and financial transactions retain the ownership/mapping version used at the time.
