#!/usr/bin/env python3
"""
MVP Bedrock + JIRA Integration - Only creates cards
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict

import boto3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SimpleMCPClient:
    """Simple MCP client for card creation only"""
    
    def __init__(self):
        self.process = None
        self.request_id = 1
    
    async def start_server(self):
        """Start the MVP MCP server"""
        try:
            self.process = await asyncio.create_subprocess_exec(
                sys.executable, 'mvp_mcp_server.py',
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Initialize MCP connection
            init_request = {
                "jsonrpc": "2.0",
                "id": self.request_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "mvp-client", "version": "1.0.0"}
                }
            }
            await self._send_request(init_request)
            self.request_id += 1
            
            # Send initialized notification
            await self._send_request({"jsonrpc": "2.0", "method": "notifications/initialized"})
            
            return True
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            return False
    
    async def _send_request(self, request: Dict[str, Any]):
        """Send request to MCP server"""
        request_json = json.dumps(request) + '\n'
        self.process.stdin.write(request_json.encode())
        await self.process.stdin.drain()
        
        if "id" not in request:
            return None
        
        response_line = await self.process.stdout.readline()
        if response_line:
            return json.loads(response_line.decode().strip())
        return None
    
    async def create_issue(self, summary: str, description: str = "", issue_type: str = "Task"):
        """Create a JIRA issue"""
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "tools/call",
            "params": {
                "name": "create_jira_issue",
                "arguments": {
                    "summary": summary,
                    "description": description,
                    "issue_type": issue_type
                }
            }
        }
        self.request_id += 1
        
        response = await self._send_request(request)
        if response and "result" in response:
            content = response["result"]["content"]
            if content and len(content) > 0:
                return content[0]["text"]
        return "Failed to create issue"
    
    async def close(self):
        """Close the MCP server"""
        if self.process:
            self.process.terminate()
            await self.process.wait()


class MVPBedrockIntegration:
    """Minimal Bedrock integration for JIRA card creation"""
    
    def __init__(self, model_id: str = 'anthropic.claude-3-haiku-20240307-v1:0'):
        self.bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
        self.model_id = model_id
        self.mcp_client = SimpleMCPClient()
    
    async def initialize(self):
        """Initialize the integration"""
        if not await self.mcp_client.start_server():
            raise RuntimeError("Failed to start MCP server")
        return True
    
    async def create_card(self, user_request: str) -> str:
        """Create a JIRA card based on user request"""
        try:
            system_prompt = """You are a JIRA card creation assistant. 

Your job is to analyze user requests and extract:
1. A clear, concise summary (title) for the JIRA card
2. A detailed description 
3. The appropriate issue type: Task, Story, Epic, or Subtask

Guidelines:
- Task: Bug fixes, small improvements, general work items
- Story: User features, functionality, user-facing improvements  
- Epic: Large projects, major features

IMPORTANT: Only use these exact issue types: "Task", "Story", "Epic" (case-sensitive)

Respond with ONLY a JSON object in this format:
{"summary": "Brief title", "description": "Detailed description", "issue_type": "Task"}

Do not include any other text or explanation."""

            # Call Bedrock
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 500,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_request}]
                })
            )
            
            response_body = json.loads(response['body'].read())
            ai_response = response_body['content'][0]['text'].strip()
            
            # Parse the JSON response
            try:
                card_data = json.loads(ai_response)
                
                # Validate issue type
                valid_types = ["Task", "Story", "Epic"]
                issue_type = card_data.get("issue_type", "Task")
                if issue_type not in valid_types:
                    issue_type = "Task"  # Default fallback
                
                # Create the issue via MCP
                result = await self.mcp_client.create_issue(
                    summary=card_data["summary"],
                    description=card_data["description"], 
                    issue_type=issue_type
                )
                
                return result
                
            except json.JSONDecodeError:
                return f"❌ Failed to parse AI response: {ai_response}"
                
        except Exception as e:
            logger.error(f"Error creating card: {e}")
            return f"❌ Error: {str(e)}"
    
    async def close(self):
        """Close the integration"""
        await self.mcp_client.close()


async def main():
    """Main function"""
    print("🚀 JIRA Card Creation MVP")
    print("=" * 40)
    
    # Check credentials
    if not all([os.getenv('JIRA_URL'), os.getenv('JIRA_USERNAME'), os.getenv('JIRA_API_TOKEN')]):
        print("❌ JIRA credentials not configured in .env file")
        return
    
    if not os.getenv('AWS_ACCESS_KEY_ID') and not os.getenv('AWS_PROFILE'):
        print("❌ AWS credentials not configured")
        return
    
    integration = MVPBedrockIntegration()
    
    try:
        await integration.initialize()
        print("✅ Ready to create JIRA cards!")
        print("\n💡 Examples:")
        print("  - 'Create a task to fix the login timeout bug'")
        print("  - 'Add a story for user profile pictures'")
        print("  - 'Epic for mobile app redesign'")
        print("\nType 'quit' to exit\n")
        
        while True:
            try:
                user_input = input("📝 Describe the card to create: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    break
                
                if not user_input:
                    continue
                
                print("🔄 Creating card...")
                result = await integration.create_card(user_input)
                print(result)
                print()
                
            except EOFError:
                break
            except KeyboardInterrupt:
                break
    
    except Exception as e:
        logger.error(f"Error: {e}")
        print(f"❌ Error: {e}")
    finally:
        await integration.close()
        print("\n👋 Goodbye!")

if __name__ == "__main__":
    asyncio.run(main())