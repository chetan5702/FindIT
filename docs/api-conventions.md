# API conventions

The REST API is versioned under `/api/v1`; interactive OpenAPI documentation is available at `/docs` in development. The OpenAPI schema is the executable source of truth for exact paths and payloads.

## Transport

- JSON is used for ordinary requests and responses; image creation uses `multipart/form-data`.
- Datetimes use timezone-aware ISO 8601 strings and are stored in UTC. The client localizes display values.
- Identifiers are opaque to clients. Clients must not infer authorization or ordering from them.
- Browser authentication uses secure cookie sessions. State-changing requests also include the session-bound CSRF token required by the backend.

## Successful collections

Collection endpoints use server-side pagination and bounded page sizes. The common shape is:

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0,
  "pages": 0
}
```

Search, status, category, location, report type, and date filters are applied before pagination. Sort fields and directions are allowlisted.

## Errors

Application failures use a stable envelope. Validation details may add field-level context without leaking private values.

```json
{
  "error": {
    "code": "claim_transition_invalid",
    "message": "This claim cannot move to the requested state.",
    "details": {},
    "request_id": "opaque-correlation-id"
  }
}
```

Expected status codes include `400` for malformed workflow requests, `401` for no valid session, `403` for authenticated but unauthorized access or CSRF failure, `404` when a visible resource does not exist, `409` for state/concurrency conflicts, `422` for field validation, `429` for throttling, and `500` for an unexpected server failure. Authorization-sensitive lookups may return `404` instead of revealing that a resource exists.

## Compatibility rules

Within v1, adding optional response fields or endpoints is compatible. Removing or renaming fields, changing their meaning, making an optional field required, or changing state-machine semantics requires a new version or a documented migration window. Frontend code should consume generated types or focused API client functions rather than spreading raw fetch calls throughout components.

## Security-sensitive API behavior

- Public report endpoints return only public report fields and safe image URLs.
- Private ownership data is not returned by list/search/match endpoints.
- Claim evidence is fetched through a separately authorized operation.
- Media is resolved by image identifier; request paths are never mapped directly to disk paths.
- User/role, report ownership, workflow state, staff reviewer, and audit actor are derived server-side rather than accepted through mass-assignment payloads.
- Match scores are labeled heuristic scores and include reasons; they must not be presented as probabilities.

