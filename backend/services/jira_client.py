
import requests
from typing import List, Dict, Any, Optional
from core.models import Ticket, TicketStatus
import os
import logging

logger = logging.getLogger(__name__)

class JIRAClient:
    def __init__(self):
        self.base_url = os.getenv("JIRA_BASE_URL")
        self.api_token = os.getenv("JIRA_API_TOKEN")
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
    
    async def fetch_new_tickets(self) -> List[Dict[str, Any]]:
        """Fetch new bug tickets from JIRA"""
        if not self.base_url or not self.api_token:
            logger.warning("JIRA credentials not configured")
            return []
        
        try:
            # JQL to find new bug tickets
            jql = "project = YOUR_PROJECT AND issuetype = Bug AND status = 'To Do' AND created >= -1d"
            
            response = requests.get(
                f"{self.base_url}/rest/api/3/search",
                headers=self.headers,
                params={
                    "jql": jql,
                    "fields": "summary,description,priority,created,key",
                    "maxResults": 50
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("issues", [])
            else:
                logger.error(f"JIRA API error: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching JIRA tickets: {e}")
            return []
    
    async def update_ticket_status(self, jira_id: str, status: str, comment: str = ""):
        """Update ticket status in JIRA"""
        if not self.base_url or not self.api_token:
            return False
        
        try:
            # Add comment if provided
            if comment:
                requests.post(
                    f"{self.base_url}/rest/api/3/issue/{jira_id}/comment",
                    headers=self.headers,
                    json={"body": comment}
                )
            
            # Update status (simplified - real implementation would need transition IDs)
            transition_data = {
                "transition": {"name": status}
            }
            
            response = requests.post(
                f"{self.base_url}/rest/api/3/issue/{jira_id}/transitions",
                headers=self.headers,
                json=transition_data
            )
            
            return response.status_code in [200, 204]
            
        except Exception as e:
            logger.error(f"Error updating JIRA ticket {jira_id}: {e}")
            return False
    
    def format_ticket_data(self, jira_issue: Dict) -> Dict[str, Any]:
        """Format JIRA issue data for our system"""
        fields = jira_issue.get("fields", {})
        
        return {
            "jira_id": jira_issue.get("key"),
            "title": fields.get("summary", ""),
            "description": fields.get("description", {}).get("content", [{}])[0].get("content", [{}])[0].get("text", ""),
            "priority": fields.get("priority", {}).get("name", "medium").lower(),
            "error_trace": self._extract_error_trace(fields.get("description", {}))
        }
    
    def _extract_error_trace(self, description: Dict) -> str:
        """Extract error trace from JIRA description"""
        # Simplified extraction - would need better parsing for real implementation
        content = str(description)
        if "traceback" in content.lower() or "error" in content.lower():
            return content
        return ""
