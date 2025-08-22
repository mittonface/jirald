#!/usr/bin/env python3
"""
Configuration management for the GitHub JIRA bot
"""

import os
import base64
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration settings for the GitHub JIRA bot"""
    
    # GitHub App configuration
    GITHUB_APP_ID: str = os.getenv('GITHUB_APP_ID', '')
    GITHUB_PRIVATE_KEY: str = os.getenv('GITHUB_PRIVATE_KEY', '')  # Base64 encoded
    GITHUB_WEBHOOK_SECRET: str = os.getenv('GITHUB_WEBHOOK_SECRET', '')
    
    # AWS configuration
    AWS_DEFAULT_REGION: str = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
    
    # JIRA configuration
    JIRA_URL: str = os.getenv('JIRA_URL', '')
    JIRA_USERNAME: str = os.getenv('JIRA_USERNAME', '')
    JIRA_API_TOKEN: str = os.getenv('JIRA_API_TOKEN', '')
    
    # Bot configuration
    BOT_MENTION_PATTERN: str = r'/jirald\s+(.*)'
    BEDROCK_MODEL_ID: str = 'anthropic.claude-3-haiku-20240307-v1:0'
    
    # Limits
    MAX_DIFF_SIZE: int = 8000
    MAX_FILE_DIFF_SIZE: int = 2000
    
    @classmethod
    def get_required_vars(cls) -> List[str]:
        """Return list of required environment variables"""
        return [
            'GITHUB_APP_ID', 
            'GITHUB_PRIVATE_KEY', 
            'JIRA_URL', 
            'JIRA_USERNAME', 
            'JIRA_API_TOKEN'
        ]
    
    @classmethod
    def validate(cls) -> List[str]:
        """Validate configuration and return list of missing variables"""
        return [var for var in cls.get_required_vars() if not getattr(cls, var)]
    
    @classmethod
    def decode_private_key(cls) -> str:
        """Decode GitHub App private key from base64"""
        if not cls.GITHUB_PRIVATE_KEY:
            raise ValueError("GITHUB_PRIVATE_KEY not configured")
        
        try:
            return base64.b64decode(cls.GITHUB_PRIVATE_KEY).decode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to decode base64 private key: {e}")