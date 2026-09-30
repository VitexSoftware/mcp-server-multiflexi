# Changelog

All notable changes to the MultiFlexi MCP Server project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Server crashed at import when `MULTIFLEXI_HOST` was unset, so hosts that
  register it without env (mcprack) saw an empty `tools/list`. Config and
  client are now built lazily: `initialize`/`tools/list` always work and tool
  calls fail with a clear configuration error until the env is set.

### Planned
- OAuth2 authentication support
- Connection pooling for better performance
- Metrics and monitoring endpoints
- Custom CA certificate support
- Multiple backend support with load balancing
- Improved error messages and retry logic

## [0.3.0] - 2026-08-08

### Added
- MCP prompts capability: `diagnose_job_failure`, `task_fulfillment_report`, and
  `gdpr_export_checklist`, each a guided workflow over existing tools.
- `SKILL.md` describing a MultiFlexi operations skill built on this server's
  tools.

### Fixed
- Server version reported in the MCP `initialize` handshake (and
  `multiflexi_mcp_server.__version__`) was hardcoded to `0.1.0` and had drifted
  from the actual package version; it's now read from installed package
  metadata via `importlib.metadata`, so it can never drift again.
- Default `MULTIFLEXI_HOST` was a non-functional SwaggerHub mock/virtual server,
  contradicting the README/`.env.example`, which document a working public demo
  server. The default now points at `https://demo.multiflexi.eu/api` (the
  generated client's REST paths live under `/api`, not the domain root) with the
  `demo`/`demo` account, so a zero-config install talks to a real backend.

## [0.2.0] - 2026-07-29

### Added
- `update_credential`, `update_credential_type`, and `update_topic` tools, now that
  `multiflexi-api`'s `openapi-schema.yaml` defines `requestBody` schemas for
  `updateCredentials`, `updateCredentialType`, and `updateTopic` (previously
  parameter-only, documentation/spec gaps that also left the generated
  `multiflexi-client` SDK without request models for these writes).

### Fixed
- `MultiFleXiConfig` used Pydantic v1-style `@validator` and `cls.__fields__`,
  which are deprecated under the installed Pydantic v2 (Debian `python3-pydantic`).
  Migrated to `@field_validator` + `@classmethod` and `cls.model_fields`.
- Console script entry point (`multiflexi-mcp-server`) was `async def main()`, which the
  generated script called without awaiting -- it printed an unawaited-coroutine warning
  and exited immediately without ever starting the server. `main()` is now a sync wrapper
  around `asyncio.run(run_server())`.
- `MultiFleXiClient.get_configuration()` constructed `multiflexi_client.Configuration`,
  which resolves to an unrelated domain model (app configuration record: id/app_id/name/value)
  due to a name collision in `multiflexi_client`'s top-level exports, not the API connection
  settings class. Every API call failed with a pydantic `ValidationError` as soon as
  `username`/`password` were assigned. Now imports `multiflexi_client.configuration.Configuration`
  explicitly.
- `client.py` called API methods that do not exist on `multiflexi-client` 1.1.0
  (`AppApi.get_apps`, `JobApi.get_jobs`/`add_job`/`get_jobs_status`,
  `CompanyApi.get_companies`, `UserApi.get_users`, `RuntemplateApi.get_runtemplates`/
  `get_runtemplate_by_id`/`update_runtemplate_by_id`, `GdprApi.get_data_export_status`),
  so every tool and resource crashed against the real API. Renamed to the real methods
  (`list_apps`, `listjobs`, `list_companies`, `list_users`, `list_run_templates`,
  `get_run_template_by_id`, `update_run_template_by_id`) and fixed `RequestDataExportPostRequest`
  usage.
- `get_job_status` now derives status from `Job.begin`/`end`/`exitcode` -- the real API
  has no per-job status endpoint (`DefaultApi.get_jobs_status` returns aggregate stats
  across all jobs, not one job).
- `create_job` now returns an explicit `not_supported_by_client_sdk` error instead of
  silently creating an empty job: `multiflexi-client` 1.1.0's create/update job endpoint
  (`JobApi.setjob_by_id`) has no request-body parameter, so job data could never reach
  the server.
- Slow cold-start import time: `client.py` imported `multiflexi_client` (the generated
  OpenAPI SDK) at module scope, which eagerly loads all ~15 API classes and every model
  class regardless of which are used, adding ~1.5-2s to every process start. Since
  `multiflexi-mcp-server` is spawned fresh per connection by consumers like mcprack's
  per-user HTTP proxy and must answer the MCP `initialize` handshake within a bounded
  timeout, this was causing intermittent handshake-timeout failures. `multiflexi_client`
  is now imported lazily inside each `MultiFleXiClient` method, deferring the cost to the
  first real API call instead of paying it before the handshake responds. Total import
  time of `multiflexi_mcp_server.server` drops from ~5s to well under 1s.

## [0.1.0] - 2026-02-01

### Added
- Initial release of MultiFlexi MCP Server
- Basic MCP server implementation with stdio transport
- MultiFlexi API client integration using `multiflexi-client` package
- Comprehensive tool set for MultiFlexi operations:
  - `get_app` - Get application by ID
  - `get_job` - Get job by ID
  - `create_job` - Create new jobs
  - `get_job_status` - Check job execution status
  - `get_company` - Get company information
  - `get_user` - Get user details
  - `get_runtemplate` - Get run template by ID
  - `update_runtemplate` - Update run templates
  - `request_data_export` - GDPR data export requests
  - `get_export_status` - Check export status
- Resource endpoints for listing:
  - `multiflexi://apps` - List all applications
  - `multiflexi://jobs` - List all jobs
  - `multiflexi://companies` - List all companies
  - `multiflexi://users` - List all users
  - `multiflexi://runtemplates` - List all run templates
- Environment-based configuration system
- Basic HTTP authentication support
- Comprehensive error handling with detailed error responses
- SSL verification support with configurable options
- Request timeout and retry configuration
- Debug logging capabilities
- Modular architecture with separate config, client, and server modules
- Full test suite with pytest
- Comprehensive documentation including:
  - API usage examples
  - Configuration examples for different environments
  - Docker and Kubernetes deployment examples
  - Security best practices
- Development tools configuration:
  - Black code formatting
  - isort import sorting
  - mypy type checking
  - ruff linting
  - pytest testing framework

### Technical Details
- Python 3.9+ support
- Built on Model Context Protocol (MCP) framework
- Uses `multiflexi-client` for API interactions
- Pydantic for configuration validation
- Async/await support throughout
- Proper resource management with context managers
- JSON-based communication protocol
- Structured logging with configurable levels

### Documentation
- Complete README with installation and usage instructions
- Configuration examples for various deployment scenarios
- API examples with request/response samples
- Error handling documentation
- Security considerations and best practices
- Development setup and contribution guidelines

### Testing
- Unit tests for all major components
- Configuration validation tests
- API client wrapper tests
- MCP server functionality tests
- Mock-based testing for external dependencies
- Coverage for error scenarios

### Configuration
- Environment variable based configuration
- Support for development, testing, and production environments
- Docker and Kubernetes configuration examples
- Security-focused default settings
- Flexible timeout and retry settings