
import requests
from typing import List, Dict, Any, Optional
from core.models import Ticket, TicketStatus
from core.config import config
import logging

logger = logging.getLogger(__name__)

class JIRAClient:
    def __init__(self):
        self.base_url = config.jira_base_url
        self.api_token = config.jira_api_token
        self.username = config.jira_username
        
        # Use basic auth if username provided, otherwise bearer token
        if self.username:
            import base64
            auth_string = base64.b64encode(f"{self.username}:{self.api_token}".encode()).decode()
            self.headers = {
                "Authorization": f"Basic {auth_string}",
                "Content-Type": "application/json"
            }
        else:
            self.headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
    
    async def fetch_new_tickets(self) -> List[Dict[str, Any]]:
        """Fetch tickets from JIRA with pagination support"""
        if not self.base_url or not self.api_token:
            logger.warning("JIRA credentials not configured")
            return []
        
        try:
            jql = config.get_jira_jql()
            logger.info(f"🔍 JIRA FETCH - Using JQL query: {jql}")
            logger.info(f"🔍 JIRA FETCH - Configured statuses: {config.jira_statuses}")
            logger.info(f"🔍 JIRA FETCH - Max results per page: {config.jira_max_results}")
            logger.info(f"🔍 JIRA FETCH - Safety limit total: {config.jira_max_total_results}")
            
            all_issues = []
            start_at = 0
            total_fetched = 0
            page_count = 0
            
            while True:
                page_count += 1
                logger.info(f"📄 JIRA FETCH - Page {page_count}: Fetching from startAt={start_at}")
                
                response = requests.get(
                    f"{self.base_url}/rest/api/3/search",
                    headers=self.headers,
                    params={
                        "jql": jql,
                        "fields": "summary,description,priority,created,key,issuetype,status",
                        "maxResults": config.jira_max_results,
                        "startAt": start_at
                    }
                )
                
                if response.status_code != 200:
                    logger.error(f"❌ JIRA API error: {response.status_code} - {response.text}")
                    break
                
                data = response.json()
                issues = data.get("issues", [])
                total_available = data.get("total", 0)
                
                logger.info(f"📄 JIRA FETCH - Page {page_count} results:")
                logger.info(f"   - Issues in this page: {len(issues)}")
                logger.info(f"   - Total available in JIRA: {total_available}")
                logger.info(f"   - Fetched so far: {total_fetched}")
                
                if not issues:
                    logger.info("📄 JIRA FETCH - No more issues to fetch")
                    break
                
                # Log status breakdown for this page
                status_counts = {}
                for issue in issues:
                    status = issue.get("fields", {}).get("status", {}).get("name", "Unknown")
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                logger.info(f"📊 JIRA FETCH - Page {page_count} status breakdown: {status_counts}")
                
                all_issues.extend(issues)
                total_fetched += len(issues)
                
                # Check if we've fetched all available issues
                if total_fetched >= total_available:
                    logger.info(f"✅ JIRA FETCH - Fetched all {total_fetched} available issues")
                    break
                
                # Safety limit check
                if total_fetched >= config.jira_max_total_results:
                    logger.warning(f"⚠️ JIRA FETCH - Hit safety limit of {config.jira_max_total_results} issues")
                    break
                
                # Prepare for next page
                start_at += config.jira_max_results
            
            # Final summary
            final_status_counts = {}
            for issue in all_issues:
                status = issue.get("fields", {}).get("status", {}).get("name", "Unknown")
                final_status_counts[status] = final_status_counts.get(status, 0) + 1
            
            logger.info(f"🎯 JIRA FETCH COMPLETE:")
            logger.info(f"   - Total pages fetched: {page_count}")
            logger.info(f"   - Total issues fetched: {len(all_issues)}")
            logger.info(f"   - Final status breakdown: {final_status_counts}")
            
            return all_issues
                
        except Exception as e:
            logger.error(f"❌ Error fetching JIRA tickets: {e}")
            logger.exception("Full error traceback:")
            return []
    
    async def update_ticket_status(self, jira_id: str, status: str, comment: str = ""):
        """Update ticket status in JIRA"""
        if not self.base_url or not self.api_token:
            return False
        
        try:
            # Add comment if provided
            if comment:
                comment_response = requests.post(
                    f"{self.base_url}/rest/api/3/issue/{jira_id}/comment",
                    headers=self.headers,
                    json={
                        "body": {
                            "type": "doc",
                            "version": 1,
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": comment
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                )
                logger.info(f"Added comment to {jira_id}: {comment_response.status_code}")
            
            # Get available transitions
            transitions_response = requests.get(
                f"{self.base_url}/rest/api/3/issue/{jira_id}/transitions",
                headers=self.headers
            )
            
            if transitions_response.status_code == 200:
                transitions = transitions_response.json().get("transitions", [])
                
                # Find matching transition by name
                target_transition = None
                for transition in transitions:
                    if transition["name"].lower() == status.lower():
                        target_transition = transition
                        break
                
                if target_transition:
                    # Execute transition
                    transition_response = requests.post(
                        f"{self.base_url}/rest/api/3/issue/{jira_id}/transitions",
                        headers=self.headers,
                        json={
                            "transition": {
                                "id": target_transition["id"]
                            }
                        }
                    )
                    
                    return transition_response.status_code in [200, 204]
                else:
                    logger.warning(f"No transition found for status '{status}' on ticket {jira_id}")
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating JIRA ticket {jira_id}: {e}")
            return False
    
    def format_ticket_data(self, jira_issue: Dict) -> Dict[str, Any]:
        """Format JIRA issue data for our system using configured field mappings"""
        fields = jira_issue.get("fields", {})
        
        # Extract description text from Atlassian Document Format
        description = self._extract_description_text(fields.get("description", {}))
        
        # Extract priority using configured field
        priority = "medium"  # default
        priority_field = fields.get(config.jira_priority_field)
        if priority_field and isinstance(priority_field, dict):
            priority = priority_field.get("name", "medium").lower()
        
        # Extract current status for logging
        status = fields.get("status", {}).get("name", "Unknown")
        
        ticket_data = {
            "jira_id": jira_issue.get("key"),
            "title": fields.get("summary", ""),
            "description": description,
            "priority": priority,
            "error_trace": self._extract_error_trace(description)
        }
        
        logger.debug(f"🎫 Formatted ticket {ticket_data['jira_id']} - Status: {status}, Priority: {priority}")
        
        return ticket_data
    
    def _extract_description_text(self, description: Dict) -> str:
        """Extract plain text from Atlassian Document Format"""
        if not description or not isinstance(description, dict):
            return ""
        
        content = description.get("content", [])
        text_parts = []
        
        for block in content:
            if block.get("type") == "paragraph":
                for inline in block.get("content", []):
                    if inline.get("type") == "text":
                        text_parts.append(inline.get("text", ""))
            elif block.get("type") == "codeBlock":
                # Handle code blocks
                for inline in block.get("content", []):
                    if inline.get("type") == "text":
                        text_parts.append(f"\n```\n{inline.get('text', '')}\n```\n")
        
        return " ".join(text_parts)
    
    def _extract_error_trace(self, description: str) -> str:
        """Extract error trace from description"""
        if not description:
            return ""
        
        # Look for common error patterns
        error_indicators = ["traceback", "error:", "exception:", "stacktrace", "at "]
        
        lines = description.split('\n')
        error_lines = []
        in_error_block = False
        
        for line in lines:
            line_lower = line.lower()
            if any(indicator in line_lower for indicator in error_indicators):
                in_error_block = True
                error_lines.append(line)
            elif in_error_block:
                if line.strip() and (line.startswith(' ') or line.startswith('\t') or 'file' in line_lower):
                    error_lines.append(line)
                else:
                    break
        
        return '\n'.join(error_lines) if error_lines else ""
