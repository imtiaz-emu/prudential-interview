# Software Requirements Specification (SRS)

## Project Title
Django Image Gallery Application

## Source of Requirements
This SRS is based on the assignment brief in docs/django_image_gallery_assignment.md.

## 1. Purpose
Build a Django web application that generates image gallery content from picsum.dev, supports configurable image transformations, handles upstream failures safely, improves repeat performance with caching, and is fully runnable in containers.

## 2. Scope

### In Scope
- Paginated image gallery with configurable images per page.
- Backend-only image URL generation.
- Image transformations: size, grayscale, blur (0-10), including grayscale plus blur combinations.
- Image detail page with larger image and active parameter display.
- Input validation and sanitized query handling.
- Retry, timeout, and cache-fallback behavior for upstream failures.
- Structured logs, health endpoint, and containerized runtime.
- Automated tests with minimum 70 percent coverage.
- README with build, run, test, API, and design rationale.

### Out of Scope
- Authentication and user accounts.
- Persistent user preferences.
- External services beyond local container tooling.
- Advanced design system work beyond a simple responsive UI.

## 3. Constraints and Assumptions
- picsum.dev does not provide a list endpoint for image metadata.
- Each gallery page must be assembled from multiple direct upstream image requests.
- Application must remain lightweight and run locally.
- No additional external infrastructure services should be introduced.

## 4. Functional Requirements

### FR-01 Gallery Rendering
- System shall display images in a grid layout.
- System shall support responsive behavior on mobile, tablet, and desktop.

### FR-02 Pagination
- System shall support URL-driven page state.
- Invalid page values shall redirect to page 1 and show a user-facing validation message.
- Pagination links shall preserve active filters and size parameters.
- System shall default to 10 images per page.
- User shall be able to configure image count per page via UI.
- Page mapping shall be deterministic: page 1 maps images 1-10, page 2 maps 11-20, and so on.

### FR-03 Image Transformations
- System shall support named sizes (for example: small, medium, large).
- System shall support normal rendering.
- System shall support grayscale rendering.
- System shall support blur with intensity range 0-10.
- System shall allow grayscale and blur together.
- Invalid transformation values shall return clear validation errors.

### FR-04 Image Detail View
- System shall provide a detail page per image.
- Detail page shall display a larger image.
- Detail page shall preserve and apply active transformations.
- Detail page shall display parameters used to generate the image.

### FR-05 Backend URL Generation
- All upstream image URL logic shall be implemented in backend services.
- Templates shall not construct upstream image URLs directly.
- Internal route links shall use Django URL reversing.

### FR-06 Caching
- System shall cache generated image metadata or URL payloads while app is running.
- Cache key strategy shall include all output-affecting inputs (page, size, transforms, config-dependent factors).
- Equivalent requests shall not trigger duplicate upstream calls.

### FR-07 Resilience and Fallback
- System shall enforce timeouts on upstream calls.
- System shall retry transient failures with backoff.
- System shall use cached fallback when upstream calls fail and cached data exists.

### FR-08 Error Handling Matrix
System shall explicitly handle:
- invalid or unsupported parameters
- upstream timeout
- upstream non-success response
- missing data and empty gallery results
- no cached fallback available

For each case:
- user-facing behavior shall be clear
- HTTP behavior shall be predictable
- logs shall be useful for debugging

### FR-09 Validation and Security
- System shall validate and sanitize all user query parameters.
- System shall use allow-lists for constrained values such as size, transform options, blur, and page.

### FR-10 Observability
- System shall emit structured logs for upstream requests/responses, cache hit/miss, handled errors, and fallback paths.
- Logs shall be available from container output.

### FR-11 Containerization
- System shall provide a Dockerfile.
- System shall provide Docker Compose configuration.
- System shall start with a single command.
- System shall expose a health endpoint suitable for container checks.

### FR-12 Documentation
README shall include:
- build and prerequisites
- run instructions and access URL
- test and coverage commands with reported results
- API contract for endpoints and parameters
- architectural decisions, trade-offs, assumptions, and state model rationale
- resilience strategy rationale
- performance measurement notes and outcomes
- future improvements

## 5. Non-Functional Requirements

### NFR-01 Maintainability
- Clear module boundaries (service, transformations, validation, views).
- Provider abstraction must allow image-source replacement with minimal code changes.

### NFR-02 Testability
- Automated unit and integration tests are required.
- Minimum test coverage: 70 percent.

### NFR-03 Performance
- Repeated equivalent requests should improve in response behavior due to caching.
- Concurrency behavior should be validated lightly and documented.

### NFR-04 Reliability
- No raw exception output should reach end users.
- Behavior under upstream failure should be deterministic and recoverable where possible.

## 6. Acceptance Criteria
- All functional requirements are implemented.
- All required error scenarios are handled with clear user output and logs.
- Coverage report shows at least 70 percent.
- App runs via container command with no manual setup.
- Health endpoint responds successfully.
- README includes all required sections.

## 7. Risks and Mitigation
- Upstream instability risk: mitigate via timeout, retries, backoff, cached fallback.
- Incorrect cache key risk: mitigate via comprehensive cache-key inputs and tests.
- Validation inconsistency risk: mitigate via centralized validation layer and unit tests.

## 8. Definition of Done
The assignment is complete when the application is functionally correct, resilient, test-covered, observable, containerized, and fully documented according to the stated requirements.
