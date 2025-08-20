#!/usr/bin/env python3
"""
MVP JIRA MCP Server - Only creates issues
"""

import asyncio
import logging
from typing import Any, Dict, List

from dotenv import load_dotenv
from mcp.server import Server, InitializationOptions, NotificationOptions
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from mvp_jira_client import SimpleJiraClient

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the MCP server
server = Server("jira-mvp-server")

@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available tools"""
    return [
        Tool(
            name="create_jira_issue",
            description="Create a new JIRA issue in the MBA project",
            inputSchema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Issue title/summary"},
                    "description": {"type": "string", "description": "Issue description", "default": ""},
                    "issue_type": {"type": "string", "description": "Issue type: Task, Story, Epic, or Subtask", "default": "Task"}
                },
                "required": ["summary"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls"""
    if name == "create_jira_issue":
        try:
            client = SimpleJiraClient()
            
            summary = arguments["summary"]
            description = arguments.get("description", "")
            issue_type = arguments.get("issue_type", "Task")
            
            result = client.create_issue(summary, description, issue_type)
            
            if result["success"]:
                return [TextContent(
                    type="text",
                    text=f"✅ Created JIRA issue {result['issue_key']}: {summary}\n🔗 {result['url']}"
                )]
            else:
                return [TextContent(
                    type="text",
                    text=f"❌ Failed to create issue: {result['error']}"
                )]
                
        except Exception as e:
            logger.error(f"Error creating issue: {e}")
            return [TextContent(
                type="text",
                text=f"❌ Error: {str(e)}"
            )]
    
    return [TextContent(
        type="text",
        text=f"Unknown tool: {name}"
    )]

async def main():
    """Run the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="jira-mvp-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())