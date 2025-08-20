# JIRA Card Creation MVP

A minimal viable product for creating JIRA cards using natural language through AWS Bedrock and MCP.

## What It Does

**One simple thing:** Creates JIRA cards in your MBA project based on natural language descriptions.

## Files

### Core MVP Files
- `mvp_jira_client.py` - Simple JIRA client (create issues only)
- `mvp_mcp_server.py` - Minimal MCP server (one tool: create_jira_issue)
- `mvp_bedrock_client.py` - Simple Bedrock integration

### Configuration
- `.env` - Your JIRA and AWS credentials

## Setup

1. **Install dependencies** (already done if you used uv):
   ```bash
   source .venv/bin/activate
   ```

2. **Configure credentials** in `.env`:
   ```bash
   JIRA_URL=https://yourcompany.atlassian.net
   JIRA_USERNAME=your-email@company.com
   JIRA_API_TOKEN=your-api-token
   
   AWS_ACCESS_KEY_ID=your-access-key
   AWS_SECRET_ACCESS_KEY=your-secret
   ```

## Usage

```bash
python mvp_bedrock_client.py
```

**Then describe what card you want:**
- "Create a task to fix the login timeout bug"
- "Add a story for user profile pictures" 
- "Epic for mobile app redesign"

The system will:
1. 🧠 Analyze your request with Bedrock
2. 📝 Create the appropriate JIRA card
3. ✅ Show you the result with a link

## Issue Types

The MVP automatically chooses:
- **Task** - Bug fixes, small improvements, general work
- **Story** - User features, functionality
- **Epic** - Large projects, major features
- **Subtask** - Work that's part of larger tasks

## That's It!

Simple, focused, and effective. Just natural language → JIRA cards.