#!/usr/bin/env python3
"""
GitHub App for creating JIRA cards from PR context
"""

import os
import re
import json
import hmac
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import jwt
from github import Github, GithubIntegration
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn
from dotenv import load_dotenv

from mvp_jira_client import SimpleJiraClient

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# GitHub App configuration
GITHUB_APP_ID = os.getenv('GITHUB_APP_ID')
GITHUB_PRIVATE_KEY = os.getenv('GITHUB_PRIVATE_KEY')  # Base64 encoded
GITHUB_WEBHOOK_SECRET = os.getenv('GITHUB_WEBHOOK_SECRET')

# Bot trigger patterns
BOT_MENTION_PATTERN = r'@jira-bot\s+(.*)'

app = FastAPI(title="JIRA GitHub Bot", version="1.0.0")


class GitHubJiraBot:
    """GitHub App that creates JIRA cards from PR context"""
    
    def __init__(self):
        self.app_id = GITHUB_APP_ID
        self.private_key = self._load_private_key()
        self.webhook_secret = GITHUB_WEBHOOK_SECRET
        self.jira_client = SimpleJiraClient()
    
    def _load_private_key(self) -> str:
        """Load GitHub App private key from base64 encoded environment variable"""
        key = GITHUB_PRIVATE_KEY
        if not key:
            raise ValueError("GITHUB_PRIVATE_KEY not configured")
        
        # Decode base64 encoded private key
        try:
            import base64
            return base64.b64decode(key).decode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to decode base64 private key: {e}")
    
    def _get_jwt_token(self) -> str:
        """Generate JWT token for GitHub App authentication"""
        now = datetime.utcnow()
        payload = {
            'iat': now,
            'exp': now + timedelta(minutes=10),
            'iss': self.app_id
        }
        return jwt.encode(payload, self.private_key, algorithm='RS256')
    
    def _get_installation_token(self, installation_id: int) -> str:
        """Get installation access token"""
        integration = GithubIntegration(self.app_id, self.private_key)
        return integration.get_access_token(installation_id).token
    
    def _verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify GitHub webhook signature"""
        if not self.webhook_secret:
            return True  # Skip verification if no secret configured
        
        expected = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(f"sha256={expected}", signature)
    
    def extract_pr_context(self, pr_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant context from PR data"""
        pr = pr_data
        
        # Get changed files
        files_changed = []
        if 'changed_files' in pr:
            files_changed = [f.get('filename', '') for f in pr.get('changed_files', [])]
        
        # Extract PR details
        context = {
            'title': pr.get('title', ''),
            'description': pr.get('body', ''),
            'author': pr.get('user', {}).get('login', ''),
            'branch': pr.get('head', {}).get('ref', ''),
            'base_branch': pr.get('base', {}).get('ref', ''),
            'url': pr.get('html_url', ''),
            'number': pr.get('number', ''),
            'repository': pr.get('base', {}).get('repo', {}).get('full_name', ''),
            'files_changed': files_changed,
            'additions': pr.get('additions', 0),
            'deletions': pr.get('deletions', 0),
            'commits': pr.get('commits', 0)
        }
        
        return context
    
    async def create_jira_card_from_pr(self, pr_context: Dict[str, Any], user_request: str) -> Dict[str, Any]:
        """Create JIRA card using PR context and user request"""
        try:
            # Prepare context for LLM
            context_text = f"""
PR Context:
- Title: {pr_context['title']}
- Author: {pr_context['author']}
- Repository: {pr_context['repository']}
- Branch: {pr_context['branch']} → {pr_context['base_branch']}
- Files changed: {len(pr_context['files_changed'])} files
- Changes: +{pr_context['additions']} -{pr_context['deletions']} lines
- URL: {pr_context['url']}

PR Description:
{pr_context['description']}

Files Changed:
{', '.join(pr_context['files_changed'][:10])}{'...' if len(pr_context['files_changed']) > 10 else ''}

User Request: {user_request}
"""
            
            # Use Bedrock to analyze and create appropriate JIRA card
            import boto3
            bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
            
            system_prompt = """You are a JIRA card creation assistant with access to PR context.

Analyze the PR information and user request to create an appropriate JIRA card.

Consider:
- The scope and type of changes in the PR
- The user's specific request
- Whether this should be a Task, Story, or Epic
- How to write a clear summary and detailed description

Guidelines:
- Task: Bug fixes, small improvements, code changes
- Story: User-facing features, functionality improvements
- Epic: Large features, major architectural changes

Include relevant PR details in the description (author, files changed, etc.).

Respond with ONLY a JSON object:
{"summary": "Clear title", "description": "Detailed description with PR context", "issue_type": "Task"}"""

            response = bedrock.invoke_model(
                modelId='anthropic.claude-3-haiku-20240307-v1:0',
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1000,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": context_text}]
                })
            )
            
            response_body = json.loads(response['body'].read())
            ai_response = response_body['content'][0]['text'].strip()
            
            # Parse response and create JIRA card
            card_data = json.loads(ai_response)
            
            # Validate issue type
            valid_types = ["Task", "Story", "Epic"]
            issue_type = card_data.get("issue_type", "Task")
            if issue_type not in valid_types:
                issue_type = "Task"
            
            # Create JIRA issue
            result = self.jira_client.create_issue(
                summary=card_data["summary"],
                description=card_data["description"],
                issue_type=issue_type
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error creating JIRA card: {e}")
            return {"success": False, "error": str(e)}
    
    async def handle_pr_comment(self, payload: Dict[str, Any]):
        """Handle PR comment events"""
        try:
            comment = payload.get('comment', {})
            comment_body = comment.get('body', '')
            
            # Check if bot is mentioned
            match = re.search(BOT_MENTION_PATTERN, comment_body, re.IGNORECASE)
            if not match:
                return
            
            user_request = match.group(1).strip()
            if not user_request:
                return
            
            # Get PR data
            pr_data = payload.get('pull_request', {})
            if not pr_data:
                return
            
            # Get installation token
            installation_id = payload.get('installation', {}).get('id')
            if not installation_id:
                return
            
            token = self._get_installation_token(installation_id)
            github = Github(token)
            
            # Get full PR details with files
            repo = github.get_repo(pr_data['base']['repo']['full_name'])
            pr = repo.get_pull(pr_data['number'])
            
            # Add files to PR data
            pr_data['changed_files'] = [{'filename': f.filename} for f in pr.get_files()]
            
            # Extract context and create JIRA card
            pr_context = self.extract_pr_context(pr_data)
            result = await self.create_jira_card_from_pr(pr_context, user_request)
            
            # Post result as PR comment
            if result.get('success'):
                comment_text = f"✅ Created JIRA issue: [{result['issue_key']}]({result['url']})\n\n📝 Summary: {pr_context['title']}"
            else:
                comment_text = f"❌ Failed to create JIRA issue: {result.get('error', 'Unknown error')}"
            
            # Post comment on PR
            pr.create_issue_comment(comment_text)
            
            logger.info(f"Processed PR comment for {pr_data['base']['repo']['full_name']}#{pr_data['number']}")
            
        except Exception as e:
            logger.error(f"Error handling PR comment: {e}")


# Initialize bot
bot = GitHubJiraBot()


@app.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle GitHub webhooks"""
    
    # Verify signature
    signature = request.headers.get('X-Hub-Signature-256', '')
    payload = await request.body()
    
    if not bot._verify_webhook_signature(payload, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    # Parse payload
    try:
        event_data = json.loads(payload.decode())
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    event_type = request.headers.get('X-GitHub-Event', '')
    
    # Handle different event types
    if event_type == 'issue_comment' and event_data.get('issue', {}).get('pull_request'):
        # This is a PR comment
        background_tasks.add_task(bot.handle_pr_comment, event_data)
    
    return JSONResponse({"status": "ok"})


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "JIRA GitHub Bot is running", "timestamp": datetime.utcnow().isoformat()}


@app.get("/health")
async def health_check():
    """Health check for the service"""
    return {"status": "healthy", "service": "jira-github-bot"}


if __name__ == "__main__":
    # Check required environment variables
    required_vars = ['GITHUB_APP_ID', 'GITHUB_PRIVATE_KEY', 'JIRA_URL', 'JIRA_USERNAME', 'JIRA_API_TOKEN']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        exit(1)
    
    logger.info("Starting JIRA GitHub Bot...")
    uvicorn.run(app, host="0.0.0.0", port=8000)