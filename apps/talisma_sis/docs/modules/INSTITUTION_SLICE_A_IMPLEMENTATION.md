# Talisma Institution Slice A Implementation

Status: **Implemented on feature branch; pending code review**

## Scope

This implementation follows the [Slice A approval record](../architecture/INSTITUTIONAL_SCHEMA_SLICE_A_APPROVAL.md). It adds only the `Talisma Institution` DocType, its approved roles, validation and automated tests.

No Campus, Academic Unit, hierarchy, mapping, identity, Education, API, portal, workspace, report or Docker configuration was added.

## Implementation

- UUIDv4 names are generated in the controller because Frappe v16 metadata `UUID` naming generates UUIDv7.
- Institution codes are trimmed, uppercased, validated against `A-Z`, `0-9`, hyphen and underscore, limited to 2–32 characters, unique and immutable.
- Date intervals, IANA timezones and HTTP/HTTPS website URLs are validated server-side.
- Change tracking is enabled.
- Import, quick entry and rename are disabled.
- `Talisma Institution Manager` receives create/read/write/delete permissions.
- `Talisma Institution Viewer` receives read-only permission.
- `System Manager` retains development/recovery administration.

## Verification

Run against the development site:

```bash
bench --site talisma.local migrate
bench --site talisma.local run-tests --doctype "Talisma Institution" --app talisma_sis
bench --site talisma.local backup
```

Verified scenarios include UUIDv4 naming, code normalization, invalid/duplicate/immutable code, invalid date interval, invalid timezone, invalid URL scheme, Manager/Viewer permissions, change-tracking metadata and unreferenced deletion.

Static Link deletion protection will be tested when the first authorized dependent DocType is implemented. Generic references such as ToDo are intentionally non-blocking in Frappe and are not valid substitutes for a real Link field.

## Deployment

The existing custom image recipe copies the application into the ERPNext v16.26.2 image. After merging this implementation, rebuild the image, recreate the unchanged Compose stack and run `bench migrate`. No Compose edit is required.
