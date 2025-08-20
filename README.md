# JIRA MCP Server

A Python application that provides JIRA functionality through both a direct API wrapper and an MCP (Model Context Protocol) server for LLM applications.

## Features

### JIRA Operations
- Create new JIRA issues
- Update existing issues  
- Search issues with JQL (JIRA Query Language)
- Add comments to issues
- Transition issues between statuses
- Get issue details and available transitions

### MCP Server
- Full MCP (Model Context Protocol) server implementation
- 7 JIRA tools available to LLM applications
- Automatic schema validation
- Comprehensive error handling
- Logging support

## Setup

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

1. **Install uv** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Activate the virtual environment**:
   ```bash
   source .venv/bin/activate
   ```

3. **Install dependencies** (already done if you used uv init):
   ```bash
   uv sync
   ```

## Configuration

Before using the JIRA client, you need to set up your credentials:

1. **Get your JIRA API token**:
   - Go to https://id.atlassian.com/manage-profile/security/api-tokens
   - Create a new API token
   - Copy the token (you won't be able to see it again)

2. **Set up your .env file**:
   ```bash
   cp .env.example .env
   ```
   
   Then edit `.env` with your actual values:
   ```bash
   JIRA_URL=https://yourcompany.atlassian.net
   JIRA_USERNAME=your-email@company.com
   JIRA_API_TOKEN=your-api-token
   DEFAULT_PROJECT_KEY=YOURPROJECT
   ```

   **Alternative**: You can still use environment variables:
   ```bash
   export JIRA_URL="https://yourcompany.atlassian.net"
   export JIRA_USERNAME="your-email@company.com"
   export JIRA_API_TOKEN="your-api-token"
   ```

## Usage

### Basic Example

```python
from jira_client import JiraClient

# Initialize client
jira = JiraClient(
    base_url="https://yourcompany.atlassian.net",
    username="your-email@company.com", 
    api_token="your-api-token"
)

# Create an issue
issue = jira.create_issue(
    project_key="PROJ",
    summary="New bug report",
    issue_type="Bug",
    description="Description of the bug",
    priority="High"
)

# Search for issues
results = jira.search_issues("project = PROJ AND status = Open")

# Update an issue
jira.update_issue("PROJ-123", summary="Updated summary")

# Add a comment
jira.add_comment("PROJ-123", "This is a comment")
```

### Run the Example Script

```bash
python example.py
```

### Using as an MCP Server

The application can run as an MCP server to provide JIRA functionality to LLM applications like Claude Desktop.

1. **Start the MCP server**:
   ```bash
   python mcp_server.py
   ```

2. **Or use the runner script**:
   ```bash
   python run_mcp_server.py
   ```

3. **Configure in Claude Desktop** (add to your MCP settings):
   ```json
   {
     "mcpServers": {
       "jira": {
         "command": "uv",
         "args": ["run", "python", "mcp_server.py"],
         "cwd": "/path/to/jirald-mcp-server",
         "env": {
           "PYTHONPATH": "/path/to/jirald-mcp-server"
         }
       }
     }
   }
   ```

### Available MCP Tools

When running as an MCP server, the following tools are available:

- `jira_create_issue` - Create a new JIRA issue
- `jira_get_issue` - Get details of a specific issue
- `jira_update_issue` - Update an existing issue
- `jira_search_issues` - Search issues using JQL
- `jira_add_comment` - Add a comment to an issue
- `jira_get_transitions` - Get available status transitions
- `jira_transition_issue` - Move an issue to a different status

## API Reference

### JiraClient

#### `__init__(base_url, username, api_token)`
Initialize the JIRA client with your instance URL and credentials.

#### `create_issue(project_key, summary, issue_type="Task", description="", priority="Medium", **custom_fields)`
Create a new JIRA issue.

#### `update_issue(issue_key, **fields)`
Update an existing issue with new field values.

#### `get_issue(issue_key)`
Retrieve detailed information about an issue.

#### `search_issues(jql, max_results=50, start_at=0)`
Search for issues using JQL (JIRA Query Language).

#### `add_comment(issue_key, comment)`
Add a comment to an issue.

#### `transition_issue(issue_key, transition_id)`
Move an issue to a different status.

#### `get_transitions(issue_key)`
Get available status transitions for an issue.

## Error Handling

The client provides specific exception types:

- `JiraAuthenticationError`: Invalid credentials
- `JiraPermissionError`: Insufficient permissions
- `JiraNotFoundError`: Resource not found
- `JiraValidationError`: Invalid input data
- `JiraError`: General API errors

## Development

To extend the functionality:

1. Add new methods to the `JiraClient` class in `jira_client.py`
2. Follow the existing pattern of using `_make_request()` for API calls
3. Add appropriate error handling and logging
4. Update this README with new functionality

## Requirements

- Python 3.11+
- requests library (managed by uv)
- python-dotenv library (managed by uv)
- Valid JIRA instance with API access

## Files

### Core Components
- `jira_client.py` - Main JIRA API client
- `exceptions.py` - Custom exception classes
- `mcp_server.py` - MCP server implementation

### Configuration
- `.env.example` - Environment variables template
- `mcp_config.json` - MCP server configuration example
- `.gitignore` - Git ignore file (includes .env)

### Examples and Utilities
- `example.py` - Direct API usage example
- `run_mcp_server.py` - MCP server runner script

## MCP Tool Examples

### Create an Issue
```json
{
  "name": "jira_create_issue",
  "arguments": {
    "project_key": "PROJ",
    "summary": "Bug in login system",
    "issue_type": "Bug",
    "description": "Users cannot log in with special characters in password",
    "priority": "High",
    "assignee": "john.doe",
    "labels": ["login", "security"]
  }
}
```

### Search Issues  
```json
{
  "name": "jira_search_issues",
  "arguments": {
    "jql": "project = PROJ AND status = 'In Progress' ORDER BY created DESC",
    "max_results": 10
  }
}
```

### Update an Issue
```json
{
  "name": "jira_update_issue", 
  "arguments": {
    "issue_key": "PROJ-123",
    "summary": "Updated: Bug in login system",
    "priority": "Critical"
  }
}
```