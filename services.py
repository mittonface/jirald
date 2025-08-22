#!/usr/bin/env python3
"""
Service classes for GitHub JIRA bot
"""

import json
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone

import jwt
import boto3
from github import Github, GithubIntegration

from config import Config

logger = logging.getLogger(__name__)


class PromptService:
    """Service for loading and processing prompt templates"""
    
    @staticmethod
    def load_prompt(filename: str) -> str:
        """Load prompt from file and extract content"""
        with open(f'prompts/{filename}', 'r') as f:
            content = f.read()
            
        # Extract text content, removing markdown formatting
        lines = content.split('\n')
        system_prompt = []
        for line in lines:
            # Skip headers and code blocks
            if not line.startswith('#') and not line.startswith('```'):
                system_prompt.append(line)
        
        return '\n'.join(system_prompt).strip()


class BedrockService:
    """Service for AWS Bedrock interactions"""
    
    def __init__(self):
        self.client = boto3.client('bedrock-runtime', region_name=Config.AWS_DEFAULT_REGION)
    
    def generate_jira_card(self, context_text: str) -> Dict[str, Any]:
        """Generate JIRA card data using Bedrock"""
        system_prompt = PromptService.load_prompt('card_creation_prompt.md')
        
        response = self.client.invoke_model(
            modelId=Config.BEDROCK_MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "system": system_prompt,
                "messages": [{"role": "user", "content": context_text}]
            })
        )
        
        response_body = json.loads(response['body'].read())
        ai_response = response_body['content'][0]['text'].strip()
        
        return json.loads(ai_response)
    
    def generate_response_comment(self, context_text: str) -> str:
        """Generate response comment using Bedrock"""
        system_prompt = PromptService.load_prompt('response_generation_prompt.md')
        
        response = self.client.invoke_model(
            modelId=Config.BEDROCK_MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 500,
                "system": system_prompt,
                "messages": [{"role": "user", "content": context_text}]
            })
        )
        
        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text'].strip()
    
    def analyze_jira_request(self, context_text: str) -> Dict[str, Any]:
        """Analyze user intent for JIRA operations"""
        system_prompt = """
You are a JIRA request analyzer. Based on the user's request and context, determine what action they want to take.

Analyze the request and respond with a JSON object indicating:
1. "action": "create", "update", or "query"
2. If action is "update": provide "issue_key" and "updates" object with fields to change
3. If action is "query": no additional fields needed

Examples:
- "Update MBA-123 to change the summary to 'New title'" -> {"action": "update", "issue_key": "MBA-123", "updates": {"summary": "New title"}}
- "Show me existing cards" -> {"action": "query"}
- "Create a new task for this bug" -> {"action": "create"}
- "Change the description of MBA-456" -> {"action": "update", "issue_key": "MBA-456", "updates": {"description": "new description from user"}}

Respond with ONLY a JSON object.
"""
        
        response = self.client.invoke_model(
            modelId=Config.BEDROCK_MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "system": system_prompt,
                "messages": [{"role": "user", "content": context_text}]
            })
        )
        
        response_body = json.loads(response['body'].read())
        ai_response = response_body['content'][0]['text'].strip()
        
        try:
            return json.loads(ai_response)
        except json.JSONDecodeError:
            # Fall back to create if we can't parse the response
            return {"action": "create"}


class GitHubService:
    """Service for GitHub API interactions"""
    
    def __init__(self):
        self.app_id = Config.GITHUB_APP_ID
        self.private_key = Config.decode_private_key()
    
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
    
    def get_authenticated_client(self, installation_id: int) -> Github:
        """Get authenticated GitHub client for installation"""
        token = self._get_installation_token(installation_id)
        return Github(token)
    
    def get_pr_with_files(self, github_client: Github, repo_name: str, pr_number: int) -> Tuple[Dict[str, Any], Any]:
        """Get full PR details including files and diff"""
        repo = github_client.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        
        # Build PR data structure
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
        
        # Add files
        files = list(pr.get_files())
        pr_data['changed_files'] = [{'filename': f.filename} for f in files]
        
        # Get code diff
        pr_diff = ""
        total_diff_size = 0
        
        for file in files:
            if total_diff_size >= Config.MAX_DIFF_SIZE:
                pr_diff += f"\n... (truncated - showing first {len([f for f in files if total_diff_size < Config.MAX_DIFF_SIZE])} files)\n"
                break
                
            file_diff = f"\n--- {file.filename} ---\n"
            if file.patch:
                file_diff += file.patch[:Config.MAX_FILE_DIFF_SIZE]
                if len(file.patch) > Config.MAX_FILE_DIFF_SIZE:
                    file_diff += "\n... (file diff truncated)"
            file_diff += "\n"
            
            if total_diff_size + len(file_diff) <= Config.MAX_DIFF_SIZE:
                pr_diff += file_diff
                total_diff_size += len(file_diff)
            else:
                break
        
        pr_data['code_diff'] = pr_diff
        
        return pr_data, pr