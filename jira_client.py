import requests
from typing import Dict, Any
from dotenv import load_dotenv
import os

load_dotenv()


class SimpleJiraClient:
    def __init__(self):
        """Initialize JIRA client with environment variables"""
        self.base_url = os.getenv('JIRA_URL').rstrip('/')
        username = os.getenv('JIRA_USERNAME')
        api_token = os.getenv('JIRA_API_TOKEN')
        
        self.session = requests.Session()
        self.session.auth = (username, api_token)
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def create_issue(self, summary: str, description: str = "", issue_type: str = "Task") -> Dict[str, Any]:
        """Create a JIRA issue in MBA project"""
        issue_data = {
            "fields": {
                "project": {"key": "MBA"},
                "summary": summary,
                "issuetype": {"name": issue_type},
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": description
                                }
                            ]
                        }
                    ]
                }
            }
        }
        
        url = f"{self.base_url}/rest/api/3/issue"
        response = self.session.post(url, json=issue_data)
        
        if response.status_code == 201:
            result = response.json()
            return {
                "success": True,
                "issue_key": result["key"],
                "url": f"{self.base_url}/browse/{result['key']}"
            }
        else:
            return {
                "success": False,
                "error": f"Failed to create issue: {response.status_code} {response.text}"
            }