import requests
from typing import Dict, Any, List, Optional
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
    
    def update_issue(self, issue_key: str, summary: str = None, description: str = None, issue_type: str = None) -> Dict[str, Any]:
        """Update a JIRA issue"""
        update_data = {"fields": {}}
        
        if summary:
            update_data["fields"]["summary"] = summary
        
        if description:
            update_data["fields"]["description"] = {
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
        
        if issue_type:
            update_data["fields"]["issuetype"] = {"name": issue_type}
        
        if not update_data["fields"]:
            return {
                "success": False,
                "error": "No fields to update"
            }
        
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
        response = self.session.put(url, json=update_data)
        
        if response.status_code == 204:
            return {
                "success": True,
                "issue_key": issue_key,
                "url": f"{self.base_url}/browse/{issue_key}"
            }
        else:
            return {
                "success": False,
                "error": f"Failed to update issue: {response.status_code} {response.text}"
            }
    
    def search_issues(self, jql: str) -> Dict[str, Any]:
        """Search for JIRA issues using JQL"""
        search_data = {
            "jql": jql,
            "maxResults": 50,
            "fields": ["summary", "description", "issuetype", "status"]
        }
        
        url = f"{self.base_url}/rest/api/3/search"
        response = self.session.post(url, json=search_data)
        
        if response.status_code == 200:
            result = response.json()
            issues = []
            for issue in result.get("issues", []):
                issues.append({
                    "key": issue["key"],
                    "summary": issue["fields"]["summary"],
                    "description": self._extract_description_text(issue["fields"].get("description", {})),
                    "issue_type": issue["fields"]["issuetype"]["name"],
                    "status": issue["fields"]["status"]["name"],
                    "url": f"{self.base_url}/browse/{issue['key']}"
                })
            
            return {
                "success": True,
                "issues": issues,
                "total": result["total"]
            }
        else:
            return {
                "success": False,
                "error": f"Failed to search issues: {response.status_code} {response.text}"
            }
    
    def get_issue(self, issue_key: str) -> Dict[str, Any]:
        """Get a specific JIRA issue"""
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
        response = self.session.get(url)
        
        if response.status_code == 200:
            issue = response.json()
            return {
                "success": True,
                "issue": {
                    "key": issue["key"],
                    "summary": issue["fields"]["summary"],
                    "description": self._extract_description_text(issue["fields"].get("description", {})),
                    "issue_type": issue["fields"]["issuetype"]["name"],
                    "status": issue["fields"]["status"]["name"],
                    "url": f"{self.base_url}/browse/{issue['key']}"
                }
            }
        else:
            return {
                "success": False,
                "error": f"Failed to get issue: {response.status_code} {response.text}"
            }
    
    def find_issues_for_pr(self, repo_name: str, pr_number: int) -> List[Dict[str, Any]]:
        """Find JIRA issues that might be related to a specific PR"""
        # Search for issues that might mention this PR in description or comments
        jql_queries = [
            f'project = MBA AND (description ~ "{repo_name}" OR description ~ "#{pr_number}")',
            f'project = MBA AND summary ~ "{repo_name}"',
        ]
        
        all_issues = []
        for jql in jql_queries:
            result = self.search_issues(jql)
            if result.get("success"):
                all_issues.extend(result["issues"])
        
        # Remove duplicates
        seen_keys = set()
        unique_issues = []
        for issue in all_issues:
            if issue["key"] not in seen_keys:
                seen_keys.add(issue["key"])
                unique_issues.append(issue)
        
        return unique_issues
    
    def _extract_description_text(self, description_obj: Dict) -> str:
        """Extract plain text from JIRA's ADF description format"""
        if not description_obj or not description_obj.get("content"):
            return ""
        
        text_parts = []
        for content in description_obj.get("content", []):
            if content.get("type") == "paragraph":
                for item in content.get("content", []):
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
        
        return " ".join(text_parts)