# Assessment Tracker MCP Server

This server provides Model Context Protocol (MCP) tools
for the ASD Student Portal.

The reduced Release 2 implementation focuses exclusively
on the Assessment Tracker microservice.

## Implementation

- Framework: MCP Python SDK
- Transport: Streamable HTTP
- Port: 8011
- Endpoint: http://localhost:8011/mcp
- Execution: Local Python process (not Dockerised)

## Available Tools

### assessments_get_upcoming

Returns incomplete assessments for a student that are due
within a specified number of days.

Arguments:

- student_id: Required integer
- days_ahead: Optional integer (1-90), defaults to 14

Returns:

- status
- as_of
- assignments

Each assignment includes:

- assignment_id
- title
- course_id
- due_date
- weighting
- status

## Starting the Server

From the project root:

```powershell
python -m pip install -r ai-services/mcp-server/requirements.txt
python ai-services/mcp-server/server.py
```

The server starts on port 8011.

## Integration

The Assessment Tracker backend connects through:

http://host.docker.internal:8011/mcp

The MCP tool queries the Assessment Tracker backend,
which retrieves assignment data from its database service.

## Configuration

ASSESSMENT_BACKEND_URL

Default: http://127.0.0.1:5007

## Security

- Read-only assessment retrieval
- Student ID validation
- Date-range validation
- HTTP request timeout
- No direct database modification
