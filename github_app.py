#!/usr/bin/env python3
"""
GitHub App for creating JIRA cards from PR context
"""

import re
import json
import hmac
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn

from config import Config
from services import BedrockService, GitHubService
from jira_client import SimpleJiraClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="JIRA GitHub Bot", version="1.0.0")


class GitHubJiraBot:
    """GitHub App that creates JIRA cards from PR context"""
    
    def __init__(self):
        self.webhook_secret = Config.GITHUB_WEBHOOK_SECRET
        self.jira_client = SimpleJiraClient()
        self.github_service = GitHubService()
        self.bedrock_service = BedrockService()
    
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
    
    def _extract_pr_context(self, pr_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant context from PR data"""
        files_changed = [f.get('filename', '') for f in pr_data.get('changed_files', [])]
        
        return {
            'title': pr_data.get('title', ''),
            'description': pr_data.get('body', ''),
            'author': pr_data.get('user', {}).get('login', ''),
            'branch': pr_data.get('head', {}).get('ref', ''),
            'base_branch': pr_data.get('base', {}).get('ref', ''),
            'url': pr_data.get('html_url', ''),
            'number': pr_data.get('number', ''),
            'repository': pr_data.get('base', {}).get('repo', {}).get('full_name', ''),
            'files_changed': files_changed,
            'additions': pr_data.get('additions', 0),
            'deletions': pr_data.get('deletions', 0),
            'commits': pr_data.get('commits', 0),
            'code_diff': pr_data.get('code_diff', '')
        }
    
    def _build_context_text(self, pr_context: Dict[str, Any], user_request: str) -> str:
        """Build context text for JIRA card creation"""
        return f"""
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

Code Changes:
{pr_context['code_diff'][:6000] if pr_context['code_diff'] else 'No code diff available'}

User Request: {user_request}
"""

    async def create_jira_card_from_pr(self, pr_context: Dict[str, Any], user_request: str) -> Dict[str, Any]:
        """Create JIRA card using PR context and user request"""
        try:
            context_text = self._build_context_text(pr_context, user_request)
            
            # Generate card data using Bedrock
            card_data = self.bedrock_service.generate_jira_card(context_text)
            
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
            
            # Add card details to result for response generation
            if result.get('success'):
                result['card_summary'] = card_data["summary"]
                result['card_description'] = card_data["description"]
                result['card_issue_type'] = issue_type
            
            return result
            
        except Exception as e:
            logger.error(f"Error creating JIRA card: {e}")
            return {"success": False, "error": str(e)}
    
    def _build_response_context(self, user_request: str, pr_context: Dict[str, Any], jira_result: Dict[str, Any]) -> str:
        """Build context text for response generation"""
        context_text = f"""
User Request: {user_request}

PR Information:
- Title: {pr_context['title']}
- Repository: {pr_context['repository']}
- Files changed: {len(pr_context['files_changed'])} files
- Changes: +{pr_context['additions']} -{pr_context['deletions']} lines

Code Changes (sample):
{pr_context['code_diff'][:2000] if pr_context['code_diff'] else 'No code diff available'}

JIRA Creation Result:
- Success: {jira_result.get('success', False)}
"""
        if jira_result.get('success'):
            context_text += f"""- Issue Key: {jira_result['issue_key']}
- URL: {jira_result['url']}
- Card Summary: {jira_result.get('card_summary', 'N/A')}
- Card Description: {jira_result.get('card_description', 'N/A')}
- Issue Type: {jira_result.get('card_issue_type', 'N/A')}"""
        else:
            context_text += f"- Error: {jira_result.get('error', 'Unknown error')}"
        
        return context_text

    async def generate_response_comment(self, user_request: str, pr_context: Dict[str, Any], jira_result: Dict[str, Any]) -> str:
        """Generate LLM response for PR comment"""
        try:
            context_text = self._build_response_context(user_request, pr_context, jira_result)
            return self.bedrock_service.generate_response_comment(context_text)
            
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
            
            # Extract comment info
            comment = payload.get('comment', {})
            comment_body = comment.get('body', '')
            comment_author = comment.get('user', {}).get('login', 'unknown')
            
            logger.info(f"Comment by {comment_author}: {comment_body}")
            
            # Check if bot is mentioned
            match = re.search(Config.BOT_MENTION_PATTERN, comment_body, re.IGNORECASE)
            if not match:
                logger.info("Bot not mentioned in comment - skipping")
                return
            
            user_request = match.group(1).strip()
            if not user_request:
                logger.info("Empty user request after bot mention - skipping")
                return
            
            logger.info(f"User request: {user_request}")
            
            # Get PR details
            installation_id = payload.get('installation', {}).get('id')
            if not installation_id:
                logger.error("No installation ID in payload")
                return
            
            repo_name = payload.get('repository', {}).get('full_name', '')
            pr_number = payload.get('issue', {}).get('number')
            
            if not repo_name or not pr_number:
                logger.error("Missing repo name or PR number")
                return
            
            logger.info(f"Processing PR #{pr_number} in {repo_name}")
            
            # Get GitHub client and PR data
            github_client = self.github_service.get_authenticated_client(installation_id)
            pr_data, pr = self.github_service.get_pr_with_files(github_client, repo_name, pr_number)
            
            logger.info(f"Found {len(pr_data.get('changed_files', []))} changed files")
            
            # Extract context and create JIRA card
            logger.info("Extracting PR context")
            pr_context = self._extract_pr_context(pr_data)
            
            logger.info("Creating JIRA card")
            result = await self.create_jira_card_from_pr(pr_context, user_request)
            
            logger.info(f"JIRA card creation result: {result}")
            
            # Generate and post response comment
            logger.info("Generating response comment")
            comment_text = await self.generate_response_comment(user_request, pr_context, result)
            
            try:
                pr.create_issue_comment(comment_text)
                logger.info("Successfully posted comment to PR")
            except Exception as e:
                logger.error(f"Failed to post comment: {e}")
            
            logger.info(f"Processed PR comment for {repo_name}#{pr_number}")
            
        except Exception as e:
            logger.error(f"Error handling PR comment: {e}", exc_info=True)

    async def handle_pr_labeled(self, payload: Dict[str, Any]):
        """Handle PR labeled events for card-required label"""
        try:
            logger.info("=== Processing PR label event ===")
            
            # Check if it's the card-required label
            label = payload.get('label', {})
            label_name = label.get('name', '').lower()
            
            if label_name != 'card-required':
                logger.info(f"Label '{label_name}' is not 'card-required' - skipping")
                return
            
            logger.info("card-required label detected!")
            
            # Get PR details
            pr_data_raw = payload.get('pull_request', {})
            if not pr_data_raw:
                logger.error("No pull_request data in payload")
                return
            
            installation_id = payload.get('installation', {}).get('id')
            if not installation_id:
                logger.error("No installation ID in payload")
                return
            
            repo_name = payload.get('repository', {}).get('full_name', '')
            pr_number = pr_data_raw.get('number')
            
            if not repo_name or not pr_number:
                logger.error("Missing repo name or PR number")
                return
            
            logger.info(f"Processing labeled PR #{pr_number} in {repo_name}")
            
            # Get GitHub client and detailed PR data with files
            github_client = self.github_service.get_authenticated_client(installation_id)
            pr_data, pr = self.github_service.get_pr_with_files(github_client, repo_name, pr_number)
            
            logger.info(f"Found {len(pr_data.get('changed_files', []))} changed files")
            
            # Extract context and create JIRA card with automatic request
            pr_context = self._extract_pr_context(pr_data)
            
            # Generate automatic request based on PR
            auto_request = f"Create a card to track the changes in PR #{pr_number}: {pr_context['title']}"
            
            logger.info("Creating JIRA card for labeled PR")
            result = await self.create_jira_card_from_pr(pr_context, auto_request)
            
            logger.info(f"JIRA card creation result: {result}")
            
            # Generate and post response comment
            logger.info("Generating response comment")
            comment_text = await self.generate_response_comment(auto_request, pr_context, result)
            
            try:
                pr.create_issue_comment(comment_text)
                logger.info("Successfully posted comment to PR")
            except Exception as e:
                logger.error(f"Failed to post comment: {e}")
            
            logger.info(f"Processed labeled PR for {repo_name}#{pr_number}")
            
        except Exception as e:
            logger.error(f"Error handling PR label: {e}", exc_info=True)


# Initialize bot
bot = GitHubJiraBot()


@app.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle GitHub webhooks"""
    
    logger.info("=== Webhook received ===")
    
    # Verify signature
    signature = request.headers.get('X-Hub-Signature-256', '')
    payload = await request.body()
    
    if not bot._verify_webhook_signature(payload, signature):
        logger.error("Invalid webhook signature")
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    # Parse payload
    try:
        event_data = json.loads(payload.decode())
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    event_type = request.headers.get('X-GitHub-Event', '')
    logger.info(f"Event type: {event_type}")
    
    # Log key info
    if 'repository' in event_data:
        repo_name = event_data['repository'].get('full_name', 'unknown')
        logger.info(f"Repository: {repo_name}")
    
    # Handle PR comment events
    if event_type == 'issue_comment' and event_data.get('issue', {}).get('pull_request'):
        pr_number = event_data.get('issue', {}).get('number', 'unknown')
        comment_body = event_data.get('comment', {}).get('body', '')
        comment_author = event_data.get('comment', {}).get('user', {}).get('login', 'unknown')
        
        logger.info(f"PR #{pr_number} comment by {comment_author}")
        
        # Check if bot is mentioned
        match = re.search(Config.BOT_MENTION_PATTERN, comment_body, re.IGNORECASE)
        if match:
            logger.info(f"Bot mentioned! User request: {match.group(1).strip()}")
            background_tasks.add_task(bot.handle_pr_comment, event_data)
        else:
            logger.info("Bot not mentioned in comment")
    
    # Handle PR labeled events
    elif event_type == 'pull_request' and event_data.get('action') == 'labeled':
        pr_number = event_data.get('pull_request', {}).get('number', 'unknown')
        label_name = event_data.get('label', {}).get('name', '')
        
        logger.info(f"PR #{pr_number} labeled with '{label_name}'")
        
        if label_name.lower() == 'card-required':
            logger.info("card-required label detected - creating JIRA card")
            background_tasks.add_task(bot.handle_pr_labeled, event_data)
        else:
            logger.info(f"Label '{label_name}' is not 'card-required' - skipping")
    
    else:
        logger.info(f"Event type '{event_type}' not handled")
    
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
    missing_vars = Config.validate()
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        exit(1)
    
    logger.info("Starting JIRA GitHub Bot...")
    uvicorn.run(app, host="0.0.0.0", port=8000)