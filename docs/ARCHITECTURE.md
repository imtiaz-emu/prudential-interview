# Architecture and Delivery Plan

## Project
Django Image Gallery Application

## 1. Architectural Goals
- Keep provider integration isolated and replaceable.
- Keep views thin and move behavior into services and domain logic.
- Ensure deterministic output for identical inputs.
- Prioritize resilience, observability, and testability.

## 2. High-Level Architecture

### Presentation Layer
- Django views and templates.
- URL-driven query state and pagination links.
- User-facing validation and error messaging.

### Application Layer
- Gallery orchestration service.
- Request parameter normalization handoff.
- Detail page context building.

### Domain Layer
- Validation rules and allow-lists.
- Transformation modeling (size, grayscale, blur, combinations).
- Deterministic page-to-image-index mapping.

### Infrastructure Layer
- picsum provider client abstraction.
- HTTP timeout, retry with backoff, response mapping.
- Cache strategy and key building.
- Structured logging.

### Platform Layer
- Environment-driven configuration.
- Docker and Docker Compose runtime.
- Health endpoint for container checks.

## 3. Suggested Module Layout
- gallery/views.py
- gallery/urls.py
- gallery/services/gallery_service.py
- gallery/services/image_provider.py
- gallery/services/url_builder.py
- gallery/domain/validation.py
- gallery/domain/transformations.py
- gallery/cache/cache_service.py
- gallery/logging/events.py
- gallery/health.py
- tests/unit/
- tests/integration/

## 4. Core Runtime Flows

### Flow A: Gallery Request
1. View reads query params.
2. Validation layer sanitizes and normalizes inputs.
3. Gallery service computes image index range for requested page.
4. For each image item, service checks cache by deterministic key.
5. Cache miss triggers provider call with timeout and retry policy.
6. Success path caches generated payload and returns context.
7. Failure path attempts cached fallback and records structured logs.
8. View renders template with preserved query params in pagination links.

### Flow B: Detail Request
1. View resolves image identifier and active transforms.
2. Validation layer enforces allowed values.
3. URL builder generates canonical image URL through service.
4. View renders larger image and parameter summary.

## 5. Detailed Task Breakdown

## Task 1: Project Skeleton
Objective:
- Initialize Django project and gallery app foundation.

Implementation Details:
- Create project and gallery app.
- Configure template and static paths.
- Add base URLs and starter template.

Deliverables:
- Runnable Django baseline.

Exit Criteria:
- Root route returns HTTP 200 locally.

## Task 2: Settings and Environment Configuration
Objective:
- Make runtime behavior configurable via environment.

Implementation Details:
- Add settings for default size, per-page count, cache TTL.
- Add settings for timeout, retry count, and backoff.
- Add safe defaults and type parsing.

Deliverables:
- Centralized config values in settings.

Exit Criteria:
- Behavior changes correctly when env vars change.

## Task 3: Validation Domain
Objective:
- Centralize and enforce all query parameter validation.

Implementation Details:
- Implement allow-lists for size and transform options.
- Enforce blur range 0-10 and valid page values.
- Produce explicit validation error objects/messages.

Deliverables:
- Reusable validation module.

Exit Criteria:
- Invalid inputs consistently produce predictable handling.

## Task 4: Transformation Domain
Objective:
- Normalize transformation logic for deterministic URL generation.

Implementation Details:
- Model size, grayscale, and blur options.
- Support grayscale plus blur combination.
- Convert validated input into canonical transform representation.

Deliverables:
- Transformation utilities independent from views.

Exit Criteria:
- Same input always produces same transformation output.

## Task 5: Provider Boundary and URL Builder
Objective:
- Isolate picsum-specific behavior.

Implementation Details:
- Define provider interface/contract.
- Implement picsum provider adapter.
- Implement backend URL builder service.

Deliverables:
- Provider abstraction and URL composition service.

Exit Criteria:
- Views do not contain provider-specific HTTP logic.

## Task 6: Resilience Policies
Objective:
- Handle upstream instability without breaking UX.

Implementation Details:
- Add HTTP timeout enforcement.
- Add retry with controlled backoff.
- Map upstream errors to app-level error categories.

Deliverables:
- Resilience wrapper integrated at provider boundary.

Exit Criteria:
- Timeout and transient failure paths behave predictably.

## Task 7: Cache Strategy and Implementation
Objective:
- Improve repeat performance and reduce duplicate calls.

Implementation Details:
- Implement cache key builder with all output-affecting inputs.
- Cache generated image payloads/metadata.
- Add cache hit/miss events to structured logs.

Deliverables:
- Cache service plus documented key policy.

Exit Criteria:
- Repeated equivalent requests use cache and reduce upstream calls.

## Task 8: Gallery Service Orchestration
Objective:
- Build deterministic page assembly logic.

Implementation Details:
- Compute page index ranges (1-10, 11-20, etc.).
- Aggregate image payloads with cache + provider calls.
- Propagate normalized parameters for rendering.

Deliverables:
- Gallery orchestration service.

Exit Criteria:
- Pagination mapping and payload assembly are correct.

## Task 9: Views, URLs, and Templates
Objective:
- Expose required user-facing features.

Implementation Details:
- Build gallery view with pagination and query-state preservation.
- Redirect invalid page values to page 1 with user message.
- Build detail view with larger image and active parameter display.

Deliverables:
- Functional gallery and detail pages.

Exit Criteria:
- Required UI behavior is implemented and stable.

## Task 10: UX Responsiveness and Loading Indicator
Objective:
- Meet usability requirements for common screen sizes.

Implementation Details:
- Implement responsive grid behavior.
- Add loading indicator while gallery images download.
- Verify usability on mobile, tablet, and desktop widths.

Deliverables:
- Responsive templates and simple loading feedback.

Exit Criteria:
- UI is clear and functional across target viewports.

## Task 11: Logging and Health Endpoint
Objective:
- Improve diagnosability and runtime readiness checks.

Implementation Details:
- Implement structured logs for upstream calls and cache events.
- Log handled errors and fallback decisions with context.
- Add /health endpoint.

Deliverables:
- Structured logs and health endpoint.

Exit Criteria:
- Container output includes useful logs and health check passes.

## Task 12: Automated Test Suite
Objective:
- Validate correctness and assignment completeness.

Implementation Details:
- Unit tests: validation, transformations, cache key generation, gallery service.
- Integration tests: provider boundary with mocked upstream responses.
- Error-path tests: timeout, non-success, fallback/no-fallback.
- Pagination and query-preservation tests.

Deliverables:
- Automated test suite and coverage report command.

Exit Criteria:
- Test coverage is at least 70 percent.

## Task 13: Containerization and Startup
Objective:
- Enable one-command local execution.

Implementation Details:
- Create Dockerfile.
- Create docker-compose.yml.
- Configure healthcheck wiring and environment loading.

Deliverables:
- Container assets and startup instructions.

Exit Criteria:
- Application starts via one command with no manual setup.

## Task 14: Documentation and Final Review
Objective:
- Produce complete and evaluator-friendly documentation.

Implementation Details:
- Write README sections: build, run, test, coverage, API contract.
- Document architecture decisions, trade-offs, assumptions, state model.
- Document resilience and performance measurement approach and outcomes.

Deliverables:
- Complete README and submission checklist.

Exit Criteria:
- All assignment documentation requirements are explicitly addressed.

## 6. Dependency Order
1. Task 1
2. Task 2
3. Task 3 and Task 4
4. Task 5 and Task 6
5. Task 7 and Task 8
6. Task 9 and Task 10
7. Task 11
8. Task 12
9. Task 13
10. Task 14

## 7. Definition of Done
- All mandatory requirements are implemented.
- Error handling matrix is implemented and tested.
- Coverage threshold is met.
- Containerized one-command startup is verified.
- Documentation fully explains design and operational behavior.
