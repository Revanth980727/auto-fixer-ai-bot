
import os
from typing import Dict, Any, List
import json
import logging

logger = logging.getLogger(__name__)

class Config:
    """Configuration management for the AI Agent System"""
    
    def __init__(self):
        logger.info("=== LOADING CONFIGURATION ===")
        self.load_config()
        logger.info("=== CONFIGURATION LOADED ===")
    
    def load_config(self):
        """Load configuration from environment variables"""
        # API Configuration
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.jira_api_token = os.getenv("JIRA_API_TOKEN")
        self.jira_base_url = os.getenv("JIRA_BASE_URL")
        self.jira_project_key = os.getenv("JIRA_PROJECT_KEY", "PROJECT")
        self.jira_username = os.getenv("JIRA_USERNAME")
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.github_repo_owner = os.getenv("GITHUB_REPO_OWNER")
        self.github_repo_name = os.getenv("GITHUB_REPO_NAME")
        
        # Debug logging for critical values
        logger.info(f"Config loaded - JIRA_BASE_URL: {self.jira_base_url}")
        logger.info(f"Config loaded - JIRA_PROJECT_KEY: {self.jira_project_key}")
        logger.info(f"Config loaded - JIRA_USERNAME: {self.jira_username}")
        logger.info(f"Config loaded - JIRA_API_TOKEN present: {'Yes' if self.jira_api_token else 'No'}")
        if self.jira_api_token:
            logger.info(f"Config loaded - JIRA_API_TOKEN length: {len(self.jira_api_token)}")
        
        # JIRA Configuration
        self.jira_issue_types = self._parse_list(os.getenv("JIRA_ISSUE_TYPES", "Bug"))
        self.jira_statuses = self._parse_list(os.getenv("JIRA_STATUSES", "To Do,Open,New"))
        self.jira_poll_hours = int(os.getenv("JIRA_POLL_HOURS", "24"))
        self.jira_max_results = int(os.getenv("JIRA_MAX_RESULTS", "50"))
        self.jira_priority_field = os.getenv("JIRA_PRIORITY_FIELD", "priority")
        
        # Agent Configuration
        self.agent_max_retries = int(os.getenv("AGENT_MAX_RETRIES", "3"))
        self.agent_process_interval = int(os.getenv("AGENT_PROCESS_INTERVAL", "10"))
        self.agent_intake_interval = int(os.getenv("AGENT_INTAKE_INTERVAL", "60"))
        self.agent_poll_interval = int(os.getenv("AGENT_POLL_INTERVAL", "60"))
        
        logger.info(f"Config loaded - AGENT_POLL_INTERVAL: {self.agent_poll_interval}")
        
        # Priority Scoring Configuration
        self.priority_weights = {
            "critical": float(os.getenv("PRIORITY_CRITICAL_WEIGHT", "1.0")),
            "high": float(os.getenv("PRIORITY_HIGH_WEIGHT", "0.8")),
            "medium": float(os.getenv("PRIORITY_MEDIUM_WEIGHT", "0.5")),
            "low": float(os.getenv("PRIORITY_LOW_WEIGHT", "0.2"))
        }
        self.priority_error_trace_boost = float(os.getenv("PRIORITY_ERROR_TRACE_BOOST", "0.2"))
        self.priority_urgent_keyword_boost = float(os.getenv("PRIORITY_URGENT_KEYWORD_BOOST", "0.3"))
        
        # Complexity Configuration
        self.complexity_description_threshold = int(os.getenv("COMPLEXITY_DESCRIPTION_THRESHOLD", "100"))
        self.complexity_default = os.getenv("COMPLEXITY_DEFAULT", "medium")
        
        # Test Data Configuration
        self.create_test_data = os.getenv("CREATE_TEST_DATA", "false").lower() == "true"
        self.test_data_config_file = os.getenv("TEST_DATA_CONFIG_FILE", "test_data.json")
        
        # Urgent keywords for priority calculation
        self.urgent_keywords = self._parse_list(os.getenv("URGENT_KEYWORDS", "crash,critical,urgent,blocking,outage,down"))
        
        # Log the generated JQL for debugging
        jql = self.get_jira_jql()
        logger.info(f"Generated JQL query: {jql}")
    
    def _parse_list(self, value: str) -> List[str]:
        """Parse comma-separated string into list"""
        if not value:
            return []
        return [item.strip() for item in value.split(',') if item.strip()]
    
    def get_jira_jql(self) -> str:
        """Generate JQL query based on configuration"""
        issue_types = "','".join(self.jira_issue_types)
        statuses = "','".join(self.jira_statuses)
        
        jql = f"project = {self.jira_project_key}"
        
        if issue_types:
            jql += f" AND issuetype IN ('{issue_types}')"
        
        if statuses:
            jql += f" AND status IN ('{statuses}')"
        
        jql += f" AND created >= -{self.jira_poll_hours}h"
        
        return jql
    
    def validate_required_config(self) -> List[str]:
        """Validate that required configuration is present"""
        missing = []
        
        if not self.openai_api_key:
            missing.append("OPENAI_API_KEY")
        
        if not self.jira_base_url:
            missing.append("JIRA_BASE_URL")
        
        if not self.jira_project_key:
            missing.append("JIRA_PROJECT_KEY")
        
        return missing
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for API responses"""
        return {
            "jira_configured": bool(self.jira_base_url and self.jira_api_token),
            "github_configured": bool(self.github_token and self.github_repo_owner and self.github_repo_name),
            "openai_configured": bool(self.openai_api_key),
            "jira_project_key": self.jira_project_key,
            "jira_issue_types": self.jira_issue_types,
            "jira_statuses": self.jira_statuses,
            "agent_intervals": {
                "process": self.agent_process_interval,
                "intake": self.agent_intake_interval,
                "poll": self.agent_poll_interval
            },
            "priority_weights": self.priority_weights,
            "complexity_settings": {
                "description_threshold": self.complexity_description_threshold,
                "default": self.complexity_default
            }
        }

# Global configuration instance
config = Config()
