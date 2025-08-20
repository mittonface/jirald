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
from datetime import datetime, timedelta, timezone
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
BOT_MENTION_PATTERN = r'/jirald\s+(.*)'

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
        now = datetime.now(timezone.utc)
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
            
            # Debug AWS configuration
            logger.info("=== AWS/Bedrock Configuration Debug ===")
            
            # Check for AWS credentials in environment
            aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
            aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
            aws_region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
            
            logger.info(f"AWS_ACCESS_KEY_ID present: {bool(aws_access_key)}")
            logger.info(f"AWS_SECRET_ACCESS_KEY present: {bool(aws_secret_key)}")
            logger.info(f"AWS_DEFAULT_REGION: {aws_region}")
            
            if aws_access_key:
                logger.info(f"AWS_ACCESS_KEY_ID starts with: {aws_access_key[:4]}...")
            
            try:
                bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
                logger.info("Bedrock client created successfully")
            except Exception as e:
                logger.error(f"Failed to create Bedrock client: {e}")
                return {"success": False, "error": f"Bedrock client creation failed: {e}"}
            
            # Load system prompt from file
            with open('prompts/card_creation_prompt.md', 'r') as f:
                prompt_content = f.read()
                # Extract just the text content, removing markdown formatting
                lines = prompt_content.split('\n')
                system_prompt = []
                for line in lines:
                    # Skip headers and code blocks
                    if not line.startswith('#') and not line.startswith('```'):
                        system_prompt.append(line)
                system_prompt = '\n'.join(system_prompt).strip()

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
    
    async def generate_response_comment(self, user_request: str, pr_context: Dict[str, Any], jira_result: Dict[str, Any]) -> str:
        """Generate LLM response for PR comment"""
        try:
            # Load response generation prompt
            with open('prompts/response_generation_prompt.md', 'r') as f:
                prompt_content = f.read()
                # Extract just the text content, removing markdown formatting
                lines = prompt_content.split('\n')
                system_prompt = []
                for line in lines:
                    # Skip headers and code blocks
                    if not line.startswith('#') and not line.startswith('```'):
                        system_prompt.append(line)
                system_prompt = '\n'.join(system_prompt).strip()
            
            # Prepare context for LLM
            context_text = f"""
User Request: {user_request}

PR Information:
- Title: {pr_context['title']}
- Repository: {pr_context['repository']}
- Files changed: {len(pr_context['files_changed'])} files
- Changes: +{pr_context['additions']} -{pr_context['deletions']} lines

JIRA Creation Result:
- Success: {jira_result.get('success', False)}
"""
            if jira_result.get('success'):
                context_text += f"- Issue Key: {jira_result['issue_key']}\n- URL: {jira_result['url']}"
            else:
                context_text += f"- Error: {jira_result.get('error', 'Unknown error')}"
            
            # Call Bedrock for response generation
            import boto3
            bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
            
            response = bedrock.invoke_model(
                modelId='anthropic.claude-3-haiku-20240307-v1:0',
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 500,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": context_text}]
                })
            )
            
            response_body = json.loads(response['body'].read())
            return response_body['content'][0]['text'].strip()
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            # Fallback to simple response
            if jira_result.get('success'):
                return f"✅ Created JIRA issue: [{jira_result['issue_key']}]({jira_result['url']})\n\n📝 Summary: {pr_context['title']}"
            else:
                return f"❌ Failed to create JIRA issue: {jira_result.get('error', 'Unknown error')}"
    
    async def handle_pr_comment(self, payload: Dict[str, Any]):
        """Handle PR comment events"""
        try:
            logger.info("=== Processing PR comment ===")
            
            comment = payload.get('comment', {})
            comment_body = comment.get('body', '')
            comment_author = comment.get('user', {}).get('login', 'unknown')
            
            logger.info(f"Comment author: {comment_author}")
            logger.info(f"Comment body: {comment_body}")
            
            # Check if bot is mentioned
            match = re.search(BOT_MENTION_PATTERN, comment_body, re.IGNORECASE)
            if not match:
                logger.info("Bot not mentioned in comment - skipping")
                return
            
            user_request = match.group(1).strip()
            if not user_request:
                logger.info("Empty user request after bot mention - skipping")
                return
            
            logger.info(f"User request: {user_request}")
            
            # Get PR data - for issue_comment events, PR data is in issue.pull_request
            issue_data = payload.get('issue', {})
            pr_url = issue_data.get('pull_request', {}).get('url', '')
            
            if not pr_url:
                logger.error("No pull_request URL in payload")
                return
            
            logger.info(f"PR URL from issue: {pr_url}")
            
            # Get basic info from issue data
            pr_number = issue_data.get('number', 'unknown')
            logger.info(f"PR number: {pr_number}")
            
            # Get installation token
            installation_id = payload.get('installation', {}).get('id')
            if not installation_id:
                logger.error("No installation ID in payload")
                return
            
            logger.info(f"Installation ID: {installation_id}")
            
            try:
                token = self._get_installation_token(installation_id)
                logger.info("Successfully obtained installation token")
            except Exception as e:
                logger.error(f"Failed to get installation token: {e}")
                return
            
            github = Github(token)
            
            # Get full PR details with files
            try:
                repo_name = payload.get('repository', {}).get('full_name', '')
                logger.info(f"Getting repo: {repo_name}")
                repo = github.get_repo(repo_name)
                
                logger.info(f"Getting PR #{pr_number}")
                pr = repo.get_pull(pr_number)
                
                # Build PR data structure from the actual PR object
                pr_data = {
                    'number': pr.number,
                    'title': pr.title,
                    'body': pr.body,
                    'user': {'login': pr.user.login},
                    'head': {'ref': pr.head.ref},
                    'base': {
                        'ref': pr.base.ref,
                        'repo': {'full_name': repo_name}
                    },
                    'html_url': pr.html_url,
                    'additions': pr.additions,
                    'deletions': pr.deletions,
                    'commits': pr.commits
                }
                
                # Add files to PR data
                files = list(pr.get_files())
                pr_data['changed_files'] = [{'filename': f.filename} for f in files]
                logger.info(f"Found {len(files)} changed files")
                
            except Exception as e:
                logger.error(f"Failed to get PR details: {e}")
                return
            
            # Extract context and create JIRA card
            logger.info("Extracting PR context")
            pr_context = self.extract_pr_context(pr_data)
            
            logger.info("Creating JIRA card")
            result = await self.create_jira_card_from_pr(pr_context, user_request)
            
            logger.info(f"JIRA card creation result: {result}")
            
            # Generate LLM response for PR comment
            logger.info("Generating response comment")
            comment_text = await self.generate_response_comment(user_request, pr_context, result)
            
            # Post comment on PR
            try:
                pr.create_issue_comment(comment_text)
                logger.info("Successfully posted comment to PR")
            except Exception as e:
                logger.error(f"Failed to post comment: {e}")
            
            logger.info(f"Processed PR comment for {pr_data['base']['repo']['full_name']}#{pr_data['number']}")
            
        except Exception as e:
            logger.error(f"Error handling PR comment: {e}", exc_info=True)


# Initialize bot
bot = GitHubJiraBot()


@app.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle GitHub webhooks"""
    
    logger.info("=== Webhook received ===")
    
    # Log headers
    headers = dict(request.headers)
    logger.info(f"Headers: {headers}")
    
    # Verify signature
    signature = request.headers.get('X-Hub-Signature-256', '')
    payload = await request.body()
    
    logger.info(f"Signature: {signature}")
    logger.info(f"Payload size: {len(payload)} bytes")
    
    if not bot._verify_webhook_signature(payload, signature):
        logger.error("Invalid webhook signature")
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    logger.info("Webhook signature verified")
    
    # Parse payload
    try:
        event_data = json.loads(payload.decode())
        logger.info(f"Parsed JSON payload successfully")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    event_type = request.headers.get('X-GitHub-Event', '')
    logger.info(f"Event type: {event_type}")
    
    # Log key payload info
    if 'action' in event_data:
        logger.info(f"Action: {event_data['action']}")
    
    if 'repository' in event_data:
        repo_name = event_data['repository'].get('full_name', 'unknown')
        logger.info(f"Repository: {repo_name}")
    
    # Handle different event types
    if event_type == 'issue_comment' and event_data.get('issue', {}).get('pull_request'):
        logger.info("This is a PR comment event")
        pr_number = event_data.get('issue', {}).get('number', 'unknown')
        comment_body = event_data.get('comment', {}).get('body', '')
        comment_author = event_data.get('comment', {}).get('user', {}).get('login', 'unknown')
        
        logger.info(f"PR #{pr_number}")
        logger.info(f"Comment by: {comment_author}")
        logger.info(f"Comment body: {comment_body[:200]}...")
        
        # Check if bot is mentioned
        match = re.search(BOT_MENTION_PATTERN, comment_body, re.IGNORECASE)
        if match:
            logger.info(f"Bot mentioned! User request: {match.group(1).strip()}")
        else:
            logger.info("Bot not mentioned in comment")
        
        background_tasks.add_task(bot.handle_pr_comment, event_data)
    else:
        logger.info(f"Event type '{event_type}' not handled or not a PR comment")
        if event_type == 'issue_comment':
            if not event_data.get('issue', {}).get('pull_request'):
                logger.info("This is an issue comment, not a PR comment")
    
    logger.info("=== Webhook processing complete ===")
    return JSONResponse({"status": "ok"})


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "JIRA GitHub Bot is running", "timestamp": datetime.now(timezone.utc).isoformat()}


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