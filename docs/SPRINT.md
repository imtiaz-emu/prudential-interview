# Sprint Execution Plan

## Project
Django Image Gallery Application

## Sprint Goal
Deliver a complete, production-style Django gallery app that satisfies all assignment requirements for architecture, resilience, performance, testing, containerization, and documentation.

## Suggested Sprint Duration
- 10 working days (single developer baseline)

## Delivery Strategy
- Build in dependency order from architecture.
- Keep vertical slices testable as early as possible.
- Treat each task as a mini-deliverable with explicit verification.

## Tracking Fields Per Task
- Implementation Steps
- Files to Create or Update
- Technical Notes
- Test Checklist
- Exit Criteria

## Task 1: Project Skeleton

### Implementation Steps
1. Create Django project and gallery app.
2. Configure app registration, template dirs, and static dirs.
3. Add base route and base template.
4. Add starter settings package or clear sectioned settings file.

### Files to Create or Update
- manage.py
- project/settings.py
- project/urls.py
- gallery/apps.py
- gallery/views.py
- templates/base.html

### Technical Notes
- Keep initial view minimal to validate project wiring.
- Ensure URL names are stable for future reverse calls.

### Test Checklist
- Run Django checks.
- Confirm root endpoint responds HTTP 200.

### Exit Criteria
- Local dev server starts successfully.
- Root page renders without errors.

## Task 2: Settings and Environment Configuration

### Implementation Steps
1. Add environment-driven settings for default size and per-page count.
2. Add timeout, retry count, and backoff settings.
3. Add cache backend and cache TTL configuration.
4. Add type-safe parsing helpers with fallback defaults.

### Files to Create or Update
- project/settings.py
- .env.example
- README.md (configuration section)

### Technical Notes
- Keep names explicit, for example IMAGE_DEFAULT_SIZE and UPSTREAM_TIMEOUT_SECONDS.
- Centralize defaults so they are reused by services and tests.

### Test Checklist
- Start app with and without env file.
- Validate setting overrides through runtime behavior.

### Exit Criteria
- Runtime behavior changes when env vars change.
- No hard-coded operational constants remain in business modules.

## Task 3: Validation Domain

### Implementation Steps
1. Create parser and validator for page, per_page, size, grayscale, blur.
2. Enforce allow-lists and blur range 0 to 10.
3. Add normalized result object and validation error object.
4. Standardize user-facing validation messages.

### Files to Create or Update
- gallery/domain/validation.py
- gallery/constants.py (optional)

### Technical Notes
- Return normalized typed values to prevent repeated parsing in views.
- Separate validation failure reasons for accurate logging.

### Test Checklist
- Unit tests for valid and invalid combinations.
- Boundary tests for blur 0 and 10.
- Invalid page redirection behavior prepared for view integration.

### Exit Criteria
- Validation behavior is deterministic and reusable.

## Task 4: Transformation Domain

### Implementation Steps
1. Define canonical transformation model.
2. Map validated input into transform options.
3. Support grayscale and blur combination.
4. Generate canonical representation for cache keys and URL builder.

### Files to Create or Update
- gallery/domain/transformations.py

### Technical Notes
- Canonical order matters for stable cache keys.
- Keep transformation logic provider-agnostic.

### Test Checklist
- Unit tests for normal, grayscale, blur, and combined modes.
- Determinism tests for same-input same-output.

### Exit Criteria
- Transformation output is canonical and stable.

## Task 5: Provider Boundary and URL Builder

### Implementation Steps
1. Define provider interface contract.
2. Implement picsum adapter behind that contract.
3. Build URL generator service using normalized parameters.
4. Ensure templates consume backend-generated URL payloads only.

### Files to Create or Update
- gallery/services/image_provider.py
- gallery/services/url_builder.py
- gallery/types.py (optional for contracts)

### Technical Notes
- Keep HTTP client calls outside views.
- Prefer session-based HTTP client reuse when practical.

### Test Checklist
- Unit tests for URL generation patterns.
- Mocked provider contract tests.

### Exit Criteria
- Swapping provider implementation would not require view/template rewrite.

## Task 6: Resilience Policies

### Implementation Steps
1. Add timeout enforcement to provider calls.
2. Add retry for transient errors with bounded backoff.
3. Classify and map upstream errors to internal categories.
4. Wire fallback hooks for cached values.

### Files to Create or Update
- gallery/services/image_provider.py
- gallery/errors.py

### Technical Notes
- Retry only idempotent operations.
- Avoid retry storms by setting sensible retry cap.

### Test Checklist
- Simulated timeout test.
- Simulated transient failure then success test.
- Simulated repeated failure mapping test.

### Exit Criteria
- Timeouts and retries behave as configured and observable in logs.

## Task 7: Cache Strategy and Implementation

### Implementation Steps
1. Build cache key function including all output-affecting inputs.
2. Implement cache read and write wrapper.
3. Add fallback read path for upstream failures.
4. Add cache hit or miss structured log events.

### Files to Create or Update
- gallery/cache/cache_service.py
- gallery/cache/keys.py

### Technical Notes
- Include config-dependent values in keys where output differs.
- Document cache invalidation philosophy in README.

### Test Checklist
- Unit tests for key uniqueness and stability.
- Cache hit or miss behavior tests.
- Repeated request test proving reduced upstream calls.

### Exit Criteria
- Equivalent requests avoid duplicate upstream calls.

## Task 8: Gallery Service Orchestration

### Implementation Steps
1. Implement deterministic page index calculation.
2. Assemble page payload with cache-first strategy.
3. Request missing items from provider and persist in cache.
4. Return full render context including pagination metadata.

### Files to Create or Update
- gallery/services/gallery_service.py

### Technical Notes
- Page 1 maps to 1-10, page 2 to 11-20, based on selected per-page.
- Keep orchestration separate from HTTP concerns.

### Test Checklist
- Unit tests for index range logic.
- Service tests for mixed cache hit and miss scenarios.
- Fallback behavior tests when upstream fails.

### Exit Criteria
- Gallery service returns complete deterministic payload.

## Task 9: Views, URLs, and Templates

### Implementation Steps
1. Build gallery view using validation + gallery service.
2. Redirect invalid page values to page 1 with user message.
3. Preserve active params in pagination links.
4. Build detail view with larger image and displayed parameters.

### Files to Create or Update
- gallery/views.py
- gallery/urls.py
- templates/gallery.html
- templates/detail.html

### Technical Notes
- Views should orchestrate only, no provider logic.
- Use Django messages framework for validation feedback.

### Test Checklist
- Integration tests for pagination parameter preservation.
- Invalid page redirect and message tests.
- Detail view parameter reflection tests.

### Exit Criteria
- Required user-facing behavior is complete and correct.

## Task 10: UX Responsiveness and Loading Indicator

### Implementation Steps
1. Implement responsive gallery grid CSS.
2. Add loading indicator visible while images are loading.
3. Verify behavior on mobile, tablet, desktop breakpoints.

### Files to Create or Update
- templates/gallery.html
- static/css/gallery.css
- static/js/gallery.js (optional)

### Technical Notes
- Keep UI simple and functional per assignment.
- Avoid heavy frontend dependencies.

### Test Checklist
- Manual responsive checks at representative widths.
- Confirm indicator appears during delayed image load simulation.

### Exit Criteria
- UI remains usable and responsive across target viewports.

## Task 11: Logging and Health Endpoint

### Implementation Steps
1. Add structured logging helpers with consistent fields.
2. Log upstream requests, responses, retry attempts, cache events.
3. Add handled-error and fallback-path logging.
4. Add lightweight /health endpoint.

### Files to Create or Update
- gallery/logging/events.py
- gallery/health.py
- project/urls.py
- project/settings.py

### Technical Notes
- Include correlation-friendly fields, for example request path and parameter hash.
- Ensure logs print to stdout for container visibility.

### Test Checklist
- Verify health endpoint status and response body.
- Validate log shape in local container output.

### Exit Criteria
- Health check passes and logs are diagnosable.

## Task 12: Automated Test Suite

### Implementation Steps
1. Build unit tests for domain and service logic.
2. Build integration tests around provider boundary using mocks.
3. Add error-path tests for timeout, non-success, and no-fallback.
4. Add coverage configuration and command.

### Files to Create or Update
- tests/unit/test_validation.py
- tests/unit/test_transformations.py
- tests/unit/test_cache_keys.py
- tests/unit/test_gallery_service.py
- tests/integration/test_gallery_views.py
- tests/integration/test_provider_failures.py
- pyproject.toml or pytest.ini (coverage config)

### Technical Notes
- Keep tests deterministic by mocking upstream dependencies.
- Prefer fast tests and minimal fixture complexity.

### Test Checklist
- Full test run green.
- Coverage report shows at least 70 percent.

### Exit Criteria
- Coverage target achieved and documented.

## Task 13: Containerization and Startup

### Implementation Steps
1. Create Dockerfile for Django runtime.
2. Create docker-compose.yml with web service.
3. Configure healthcheck and environment wiring.
4. Validate one-command start.

### Files to Create or Update
- Dockerfile
- docker-compose.yml
- entrypoint.sh (optional)

### Technical Notes
- Keep image lean and startup deterministic.
- Expose app port and map clearly in compose.

### Test Checklist
- docker compose up builds and starts app.
- Healthcheck reports healthy.

### Exit Criteria
- App can be started with one command and no manual setup.

## Task 14: Documentation and Final Review

### Implementation Steps
1. Write README build, run, test, coverage, API sections.
2. Document architecture decisions and trade-offs.
3. Document resilience strategy and cache policy.
4. Add performance notes and future improvements.
5. Perform final checklist validation against assignment requirements.

### Files to Create or Update
- README.md
- docs/SRS.md
- docs/ARCHITECTURE.md

### Technical Notes
- Keep commands copy-paste ready.
- Ensure docs match actual implemented behavior.

### Test Checklist
- Cross-check every assignment requirement against documented evidence.

### Exit Criteria
- Submission package is complete, coherent, and reproducible.

## Sprint Milestones

### Milestone A (Days 1-3)
- Tasks 1 to 4 complete.
- Core domain and config baseline established.

### Milestone B (Days 4-6)
- Tasks 5 to 9 complete.
- End-to-end feature behavior working with resilience and cache integration.

### Milestone C (Days 7-8)
- Tasks 10 to 12 complete.
- UX, testing, and coverage target complete.

### Milestone D (Days 9-10)
- Tasks 13 to 14 complete.
- Container and documentation finalized for submission.

## Final Completion Checklist
- All architecture tasks implemented and verified.
- Error handling matrix covered in code and tests.
- 70 percent coverage achieved.
- Docker and Compose startup works with health checks.
- README and docs fully aligned with implementation.
