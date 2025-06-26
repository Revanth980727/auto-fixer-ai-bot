
import requests
from typing import List, Dict, Any, Optional
from core.models import Ticket, TicketStatus
from core.config import config
import logging
import json

logger = logging.getLogger(__name__)

class JIRAClient:
    def __init__(self):
        self.base_url = config.jira_base_url
        self.api_token = config.jira_api_token
        self.username = config.jira_username
        
        logger.info("🔧 JIRA CLIENT INIT DEBUG:")
        logger.info(f"   - Base URL: {self.base_url}")
        logger.info(f"   - Username: {self.username}")
        logger.info(f"   - API Token Length: {len(self.api_token) if self.api_token else 0}")
        
        # Use basic auth if username provided, otherwise bearer token
        if self.username:
            import base64
            auth_string = base64.b64encode(f"{self.username}:{self.api_token}".encode()).decode()
            self.headers = {
                "Authorization": f"Basic {auth_string}",
                "Content-Type": "application/json"
            }
            logger.info("   - Auth Method: Basic Auth")
        else:
            self.headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
            logger.info("   - Auth Method: Bearer Token")
    
    async def fetch_new_tickets(self) -> List[Dict[str, Any]]:
        """Fetch tickets from JIRA with enhanced debugging and pagination support"""
        if not self.base_url or not self.api_token:
            logger.error("❌ JIRA FETCH - Missing credentials")
            logger.error(f"   - Base URL: {'✅' if self.base_url else '❌'}")
            logger.error(f"   - API Token: {'✅' if self.api_token else '❌'}")
            return []
        
        try:
            jql = config.get_jira_jql()
            logger.info("🔍 JIRA FETCH DEBUG - Configuration:")
            logger.info(f"   - JQL Query: {jql}")
            logger.info(f"   - Configured Statuses: {config.jira_statuses}")
            logger.info(f"   - Issue Types: {config.jira_issue_types}")
            logger.info(f"   - Max Results Per Page: {config.jira_max_results}")
            logger.info(f"   - Safety Limit Total: {config.jira_max_total_results}")
            logger.info(f"   - Force Reprocess: {config.jira_force_reprocess}")
            
            all_issues = []
            start_at = 0
            total_fetched = 0
            page_count = 0
            
            while True:
                page_count += 1
                logger.info(f"📄 JIRA FETCH - Page {page_count}: Starting from {start_at}")
                
                # Prepare request parameters
                request_params = {
                    "jql": jql,
                    "fields": "summary,description,priority,created,key,issuetype,status",
                    "maxResults": config.jira_max_results,
                    "startAt": start_at
                }
                
                logger.debug(f"🔍 JIRA API REQUEST DEBUG:")
                logger.debug(f"   - URL: {self.base_url}/rest/api/3/search")
                logger.debug(f"   - Params: {json.dumps(request_params, indent=2)}")
                logger.debug(f"   - Headers: {json.dumps({k: v[:50] + '...' if len(str(v)) > 50 else v for k, v in self.headers.items()}, indent=2)}")
                
                response = requests.get(
                    f"{self.base_url}/rest/api/3/search",
                    headers=self.headers,
                    params=request_params
                )
                
                logger.debug(f"🔍 JIRA API RESPONSE DEBUG:")
                logger.debug(f"   - Status Code: {response.status_code}")
                logger.debug(f"   - Response Headers: {dict(response.headers)}")
                
                if response.status_code != 200:
                    logger.error(f"❌ JIRA API ERROR:")
                    logger.error(f"   - Status Code: {response.status_code}")
                    logger.error(f"   - Response Text: {response.text}")
                    logger.error(f"   - Request URL: {response.url}")
                    break
                
                data = response.json()
                issues = data.get("issues", [])
                total_available = data.get("total", 0)
                
                logger.info(f"📄 JIRA FETCH - Page {page_count} Results:")
                logger.info(f"   - Issues in this page: {len(issues)}")
                logger.info(f"   - Total available in JIRA: {total_available}")
                logger.info(f"   - Fetched so far: {total_fetched}")
                
                # Log detailed issue information
                if issues:
                    logger.debug(f"🎫 DETAILED ISSUE INFO - Page {page_count}:")
                    for idx, issue in enumerate(issues):
                        fields = issue.get("fields", {})
                        status = fields.get("status", {}).get("name", "Unknown")
                        priority = fields.get("priority", {}).get("name", "Unknown")
                        issue_type = fields.get("issuetype", {}).get("name", "Unknown")
                        summary = fields.get("summary", "No Summary")[:50]
                        
                        logger.debug(f"   - Issue {idx + 1}: {issue.get('key', 'No Key')}")
                        logger.debug(f"     Status: {status}, Priority: {priority}, Type: {issue_type}")
                        logger.debug(f"     Summary: {summary}...")
                
                if not issues:
                    logger.info("📄 JIRA FETCH - No more issues to fetch")
                    break
                
                # Log status breakdown for this page
                status_counts = {}
                priority_counts = {}
                type_counts = {}
                
                for issue in issues:
                    fields = issue.get("fields", {})
                    status = fields.get("status", {}).get("name", "Unknown")
                    priority = fields.get("priority", {}).get("name", "Unknown")
                    issue_type = fields.get("issuetype", {}).get("name", "Unknown")
                    
                    status_counts[status] = status_counts.get(status, 0) + 1
                    priority_counts[priority] = priority_counts.get(priority, 0) + 1
                    type_counts[issue_type] = type_counts.get(issue_type, 0) + 1
                
                logger.info(f"📊 JIRA FETCH - Page {page_count} Breakdown:")
                logger.info(f"   - Status Counts: {status_counts}")
                logger.info(f"   - Priority Counts: {priority_counts}")
                logger.info(f"   - Type Counts: {type_counts}")
                
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
            
            # Final comprehensive summary
            final_status_counts = {}
            final_priority_counts = {}
            final_type_counts = {}
            
            for issue in all_issues:
                fields = issue.get("fields", {})
                status = fields.get("status", {}).get("name", "Unknown")
                priority = fields.get("priority", {}).get("name", "Unknown")
                issue_type = fields.get("issuetype", {}).get("name", "Unknown")
                
                final_status_counts[status] = final_status_counts.get(status, 0) + 1
                final_priority_counts[priority] = final_priority_counts.get(priority, 0) + 1
                final_type_counts[issue_type] = final_type_counts.get(issue_type, 0) + 1
            
            logger.info("🎯 JIRA FETCH COMPLETE - FINAL SUMMARY:")
            logger.info(f"   - Total Pages Fetched: {page_count}")
            logger.info(f"   - Total Issues Fetched: {len(all_issues)}")
            logger.info(f"   - Final Status Breakdown: {final_status_counts}")
            logger.info(f"   - Final Priority Breakdown: {final_priority_counts}")
            logger.info(f"   - Final Type Breakdown: {final_type_counts}")
            
            return all_issues
                
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR in JIRA fetch: {e}")
            logger.exception("Full error traceback:")
            return []
    
    # ... keep existing code (update_ticket_status method)
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
        """Format JIRA issue data for our system with enhanced debugging"""
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
        issue_type = fields.get("issuetype", {}).get("name", "Unknown")
        
        ticket_data = {
            "jira_id": jira_issue.get("key"),
            "title": fields.get("summary", ""),
            "description": description,
            "priority": priority,
            "error_trace": self._extract_error_trace(description)
        }
        
        logger.debug(f"🎫 FORMATTED TICKET DEBUG:")
        logger.debug(f"   - JIRA ID: {ticket_data['jira_id']}")
        logger.debug(f"   - Status: {status}")
        logger.debug(f"   - Priority: {priority}")
        logger.debug(f"   - Type: {issue_type}")
        logger.debug(f"   - Title Length: {len(ticket_data['title'])}")
        logger.debug(f"   - Description Length: {len(description)}")
        logger.debug(f"   - Error Trace Present: {'Yes' if ticket_data['error_trace'] else 'No'}")
        
        return ticket_data
    
    # ... keep existing code (_extract_description_text and _extract_error_trace methods)
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
