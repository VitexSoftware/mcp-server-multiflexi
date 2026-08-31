# MultiFlexi MCP Server

[![PyPI version](https://badge.fury.io/py/multiflexi-mcp-server.svg)](https://badge.fury.io/py/multiflexi-mcp-server)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![MCP: Model Context Protocol](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-orange)
![Packaging: deb](https://img.shields.io/badge/packaging-.deb-red?logo=debian&logoColor=white)
![Self-hosted](https://img.shields.io/badge/deployment-self--hosted%20%2F%20intranet-informational)
[![MCP Badge](https://lobehub.com/badge/mcp/vitexsoftware-multiflexi-mcp-server)](https://lobehub.com/mcp/vitexsoftware-multiflexi-mcp-server)
[![M8ven Score](https://m8ven.ai/badge/mcp/vitexsoftware-multiflexi-mcp-server-1ibvl7)](https://m8ven.ai/mcp/vitexsoftware-multiflexi-mcp-server-1ibvl7)

MCP (Model Context Protocol) Server for MultiFlexi API integration. This server provides tools and resources for interacting with MultiFlexi applications, jobs, companies, users, and run templates.

## Features

- **Applications**: List, retrieve, and manage MultiFlexi applications
- **Jobs**: Create, retrieve, and monitor job execution
- **Companies**: Manage company data and configurations
- **Users**: Access user information and profiles
- **Run Templates**: Create and update execution templates
- **GDPR Compliance**: Request and manage data exports
- **Authentication**: Support for basic authentication
- **Error Handling**: Comprehensive error handling and logging

## Installation

### Using pip

```bash
pip install multiflexi-mcp-server
```

### From source

```bash
git clone https://github.com/VitexSoftware/multiflexi-mcp-server.git
cd multiflexi-mcp-server
pip install -e .
```

## Configuration

The server can be configured using environment variables:

### Required Configuration

- `MULTIFLEXI_HOST`: MultiFlexi API host URL. No default - the server refuses to
  start without it. Must include the full API base path, e.g.
  `https://your-instance.example.com/api/VitexSoftware/MultiFlexi/1.0.0`; the
  `/VitexSoftware/MultiFlexi/1.0.0` segment is required by the server's routing.

### Optional Configuration

- `MULTIFLEXI_USERNAME`: Username for basic authentication
- `MULTIFLEXI_PASSWORD`: Password for basic authentication
- `MULTIFLEXI_VERIFY_SSL`: Whether to verify SSL certificates (default: true)
- `MULTIFLEXI_TIMEOUT`: Request timeout in seconds (default: 30)
- `MULTIFLEXI_MAX_RETRIES`: Maximum number of retries (default: 3)
- `MULTIFLEXI_DEBUG`: Enable debug logging (default: false)
- `MULTIFLEXI_READONLY`: When true (the default), all mutating tools
  (create/update/set/delete/assign/unassign) are rejected before any API call
  is made. Set to `false` to allow writes.

There is no zero-config default: the server always requires an explicit
`MULTIFLEXI_HOST` (and, unless your instance allows anonymous access,
`MULTIFLEXI_USERNAME`/`MULTIFLEXI_PASSWORD`) so it never silently talks to an
unintended backend. If you just want to try the server without your own
MultiFlexi instance, VitexSoftware runs a public demo you can point at
explicitly: `MULTIFLEXI_HOST=https://demo.multiflexi.eu/api` with
`MULTIFLEXI_USERNAME=demo` / `MULTIFLEXI_PASSWORD=demo`.

### Example Configuration

```bash
export MULTIFLEXI_HOST="https://your-multiflexi-instance.example.com/api/VitexSoftware/MultiFlexi/1.0.0"
export MULTIFLEXI_USERNAME="your-username"
export MULTIFLEXI_PASSWORD="your-password"
export MULTIFLEXI_VERIFY_SSL="true"
export MULTIFLEXI_DEBUG="false"
```

## Usage

### Running the Server

```bash
multiflexi-mcp-server
```

### Claude Desktop Integration

Add the following to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS or `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "multiflexi": {
      "command": "multiflexi-mcp-server",
      "env": {
        "MULTIFLEXI_HOST": "https://your-multiflexi-instance.example.com/api/VitexSoftware/MultiFlexi/1.0.0",
        "MULTIFLEXI_USERNAME": "your-username",
        "MULTIFLEXI_PASSWORD": "your-password"
      }
    }
  }
}
```

### Using with MCP Clients

The server provides the following resources:

- `multiflexi://apps` - List of applications
- `multiflexi://jobs` - List of jobs
- `multiflexi://companies` - List of companies
- `multiflexi://users` - List of users
- `multiflexi://runtemplates` - List of run templates
- `multiflexi://credentials` - List of credentials
- `multiflexi://credential_types` - List of credential types
- `multiflexi://topics` - List of topics (capability contracts)
- `multiflexi://eventsources` - List of event sources
- `multiflexi://eventrules` - List of event rules
- `multiflexi://tasks` - List of tasks (per-window fulfilment obligations)

### Available Prompts

- `diagnose_job_failure` (`job_id`) - Investigate why a job failed and whether a
  retry is safe
- `task_fulfillment_report` (`runtemplate_id`, optional) - Summarize Task states
  (fulfilled/fulfilled_late/failed/missed) for one or all RunTemplates
- `gdpr_export_checklist` (`export_type`, optional) - Request a GDPR data export
  and produce a compliance-ready summary once it completes

### Available Tools

Requires a `multiflexi-client` build generated from the current
`openapi-schema.yaml` (not yet released to PyPI as of this writing — see
"Known limitations" below).

#### Application Management
- `get_app` - Get application by ID
- `get_apps` - List all applications (via resources)

#### Job Management
- `get_job` - Get job by ID
- `create_job` - Schedule a job from a RunTemplate (`runtemplate_id`, `scheduled`, `executor`, `env`)
- `get_job_status` - Get job execution status
- `get_jobs` - List all jobs (via resources)

#### Company Management
- `get_company` - Get company by ID
- `list_companies` - List all companies
- `list_company_users` - List users assigned to a company
- `assign_user_to_company` - Assign a user to a company with an access role
- `unassign_user_from_company` - Remove a user's assignment from a company

#### User Management
- `get_user` - Get user by ID
- `list_users` - List all users
- `get_user_roles` - Get RBAC roles assigned to a user
- `set_user_roles` - Assign RBAC roles to a user

#### Credential & Credential Type Management
- `list_credentials` / `get_credential` / `update_credential` - List/get/update credentials
- `list_credential_types` / `get_credential_type` / `update_credential_type` - List/get/update credential types

#### Topic Management
- `list_topics` / `get_topic` / `update_topic` - List/get/update topics

#### Event Source Management
- `list_event_sources` / `get_event_source` - List/get event sources
- `set_event_source` - Create or update an event source
- `delete_event_source` - Delete an event source
- `test_event_source_connection` - Live-test connectivity/credentials

#### Event Rule Management
- `list_event_rules` / `get_event_rule` - List/get event rules
- `set_event_rule` - Create or update an event rule
- `delete_event_rule` - Delete an event rule

#### Task (read-only — tasks are system-materialized per RunTemplate window)
- `list_tasks` - List tasks, optionally filtered by `state`/`runtemplate_id`
- `get_task` - Get a task by ID, including its job attempt history

#### Run Template Management
- `get_runtemplate` - Get run template by ID
- `update_runtemplate` - Update run template
- `get_runtemplates` - List all templates (via resources)

#### GDPR Compliance
- `request_data_export` - Request data export
- `get_export_status` - Check export status

### Known limitations

- `set_company_by_id` still has no `requestBody` defined in
  `openapi-schema.yaml`, so Company writes are not exposed as an MCP tool —
  only list/get. `update_credentials`, `update_credential_type`, and
  `update_topic` now have `requestBody` schemas and are exposed as
  `update_credential`, `update_credential_type`, and `update_topic`.
- `get_credential`'s schema declares a required `token` parameter alongside
  `credential_id` that looks like a schema-authoring artifact on a
  session-authenticated endpoint; it's exposed but defaults to an empty
  string.

### Example Tool Usage

```json
{
  "tool": "get_app",
  "arguments": {
    "app_id": 123,
    "format": "json"
  }
}
```

```json
{
  "tool": "create_job",
  "arguments": {
    "runtemplate_id": 15,
    "scheduled": "now",
    "env": {"DOCID": "FV-2025-0042"}
  }
}
```

```json
{
  "tool": "request_data_export",
  "arguments": {
    "export_type": "personal_data",
    "format": "json"
  }
}
```

## Development

### Prerequisites

- Python 3.9+
- pip
- virtualenv (recommended)

### Setup Development Environment

```bash
git clone https://github.com/VitexSoftware/multiflexi-mcp-server.git
cd multiflexi-mcp-server

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Type checking
mypy src/

# Linting
ruff src/ tests/
```

## API Documentation

This server integrates with the MultiFlexi API. For detailed API documentation, refer to:
- [MultiFlexi API Documentation](https://github.com/multiflexi/multiflexi-api)
- [OpenAPI Specification](https://virtserver.swaggerhub.com/VitexSoftware/MultiFlexi/1.0.0)

## Error Handling

The server provides comprehensive error handling:

- **API Errors**: Formatted with status codes and detailed messages
- **Authentication Errors**: Clear authentication failure messages
- **Validation Errors**: Input validation with descriptive errors
- **Network Errors**: Timeout and connection error handling

All errors are returned in a consistent JSON format:

```json
{
  "error": true,
  "operation": "get_app",
  "status": 404,
  "reason": "Not Found",
  "details": {
    "message": "Application with ID 123 not found"
  }
}
```

## Security Considerations

- **Authentication**: Use environment variables for credentials
- **SSL Verification**: Enable SSL verification in production
- **Network Security**: Ensure secure network connections
- **Data Privacy**: Handle GDPR exports with appropriate security

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/VitexSoftware/multiflexi-mcp-server/issues)
- **Documentation**: [GitHub Wiki](https://github.com/VitexSoftware/multiflexi-mcp-server/wiki)
- **Email**: info@vitexsoftware.cz

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full history. Highlights:

### v0.2.0
- Fixed slow cold-start import time: `multiflexi_client` (the generated API SDK)
  is now imported lazily on first use instead of at module load, cutting
  process startup from ~5s to well under 1s -- this matters because the server
  is spawned fresh per connection by consumers with a bounded handshake timeout.
- Added `update_credential`, `update_credential_type`, and `update_topic` tools
- Fixed several API method/response mismatches against `multiflexi-client`

### v0.1.0 (Initial Release)
- Basic MCP server implementation
- MultiFlexi API integration
- Application, job, company, user, and template management
- GDPR compliance features
- Comprehensive error handling
- Environment-based configuration