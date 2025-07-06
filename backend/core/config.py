
import os
from typing import Dict, Any, List
import json
import logging

logger = logging.getLogger(__name__)

class Config:
    """Configuration management for the AI Agent System"""
    
    def __init__(self):
        logger.info("=== LOADING ENHANCED CONFIGURATION ===")
        self.load_config()
        logger.info("=== ENHANCED CONFIGURATION LOADED ===")
    
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
        self.github_target_branch = os.getenv("GITHUB_TARGET_BRANCH", "your_branch_name")
        
        # Enhanced Debug logging for critical values
        logger.info("🔧 ENHANCED CONFIGURATION DEBUG - API Keys & Tokens:")
        logger.info(f"   - OpenAI API Key: {'✅ Present' if self.openai_api_key else '❌ Missing'}")
        logger.info(f"   - JIRA API Token: {'✅ Present' if self.jira_api_token else '❌ Missing'}")
        if self.jira_api_token:
            logger.info(f"   - JIRA API Token Length: {len(self.jira_api_token)} chars")
        logger.info(f"   - GitHub Token: {'✅ Present' if self.github_token else '❌ Missing'}")
        
        logger.info("🔧 ENHANCED CONFIGURATION DEBUG - JIRA Settings:")
        logger.info(f"   - JIRA Base URL: {self.jira_base_url or '❌ Not set'}")
        logger.info(f"   - JIRA Project Key: {self.jira_project_key}")
        logger.info(f"   - JIRA Username: {self.jira_username or '❌ Not set'}")
        
        logger.info("🔧 ENHANCED CONFIGURATION DEBUG - GitHub Settings:")
        logger.info(f"   - GitHub Repo Owner: {self.github_repo_owner or '❌ Not set'}")
        logger.info(f"   - GitHub Repo Name: {self.github_repo_name or '❌ Not set'}")
        logger.info(f"   - GitHub Target Branch: {self.github_target_branch}")
        
        # Enhanced JIRA Configuration with detailed logging
        raw_issue_types = os.getenv("JIRA_ISSUE_TYPES", "Bug,Task,Story")
        raw_statuses = os.getenv("JIRA_STATUSES", "To Do,Selected for Development,In Progress,Backlog")
        
        logger.info("🔧 ENHANCED CONFIGURATION DEBUG - Raw Environment Variables:")
        logger.info(f"   - Raw JIRA_ISSUE_TYPES: '{raw_issue_types}'")
        logger.info(f"   - Raw JIRA_STATUSES: '{raw_statuses}'")
        
        self.jira_issue_types = self._parse_list(raw_issue_types)
        self.jira_statuses = self._parse_list(raw_statuses)
        
        logger.info("🔧 ENHANCED CONFIGURATION DEBUG - Parsed Lists:")
        logger.info(f"   - Parsed Issue Types: {self.jira_issue_types}")
        logger.info(f"   - Parsed Statuses: {self.jira_statuses}")
        logger.info(f"   - Issue Types Count: {len(self.jira_issue_types)}")
        logger.info(f"   - Statuses Count: {len(self.jira_statuses)}")
        
        # JIRA Pagination and Processing Settings
        self.jira_max_results = int(os.getenv("JIRA_MAX_RESULTS", "50"))
        self.jira_max_total_results = int(os.getenv("JIRA_MAX_TOTAL_RESULTS", "500"))
        self.jira_priority_field = os.getenv("JIRA_PRIORITY_FIELD", "priority")
        
        # Force reprocessing flag with detailed logging
        raw_force_reprocess = os.getenv("JIRA_FORCE_REPROCESS", "false")
        self.jira_force_reprocess = raw_force_reprocess.lower() == "true"
        
        logger.info("🔧 ENHANCED CONFIGURATION DEBUG - JIRA Processing Settings:")
        logger.info(f"   - Max Results Per Page: {self.jira_max_results}")
        logger.info(f"   - Max Total Results: {self.jira_max_total_results}")
        logger.info(f"   - Priority Field: {self.jira_priority_field}")
        logger.info(f"   - Raw Force Reprocess: '{raw_force_reprocess}'")
        logger.info(f"   - Parsed Force Reprocess: {self.jira_force_reprocess}")
        
        # Agent Configuration
        self.agent_max_retries = int(os.getenv("AGENT_MAX_RETRIES", "3"))
        self.agent_process_interval = int(os.getenv("AGENT_PROCESS_INTERVAL", "10"))
        self.agent_intake_interval = int(os.getenv("AGENT_INTAKE_INTERVAL", "60"))
        self.agent_poll_interval = int(os.getenv("AGENT_POLL_INTERVAL", "60"))
        
        logger.info("🔧 ENHANCED CONFIGURATION DEBUG - Agent Settings:")
        logger.info(f"   - Max Retries: {self.agent_max_retries}")
        logger.info(f"   - Process Interval: {self.agent_process_interval}s")
        logger.info(f"   - Intake Interval: {self.agent_intake_interval}s")
        logger.info(f"   - Poll Interval: {self.agent_poll_interval}s")
        
        # File Selection Configuration
        self.max_source_files = int(os.getenv("MAX_SOURCE_FILES", "5"))
        
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
        raw_urgent_keywords = os.getenv("URGENT_KEYWORDS", "crash,critical,urgent,blocking,outage,down")
        self.urgent_keywords = self._parse_list(raw_urgent_keywords)
        
        logger.info("🔧 ENHANCED CONFIGURATION DEBUG - Processing Settings:")
        logger.info(f"   - Priority Weights: {self.priority_weights}")
        logger.info(f"   - Urgent Keywords: {self.urgent_keywords}")
        logger.info(f"   - Complexity Threshold: {self.complexity_description_threshold}")
        
        # Generate and log the JQL for debugging
        jql = self.get_jira_jql()
        logger.info("🔧 ENHANCED CONFIGURATION DEBUG - Generated JQL:")
        logger.info(f"   - JQL Query: {jql}")
        logger.info(f"   - JQL Length: {len(jql)} characters")
        
        # Validate and warn about missing configurations
        self._validate_and_warn_configuration()
    
    def validate_required_config(self) -> List[str]:
        """Validate required configuration and return list of missing items"""
        missing = []
        
        if not self.openai_api_key:
            missing.append("OpenAI API Key")
        
        if not self.jira_api_token:
            missing.append("JIRA API Token")
            
        if not self.jira_base_url:
            missing.append("JIRA Base URL")
        
        # GitHub is optional but recommended
        github_incomplete = not (self.github_token and self.github_repo_owner and self.github_repo_name)
        if github_incomplete:
            missing.append("GitHub Configuration (optional but recommended)")
        
        return missing
    
    def _parse_list(self, value: str) -> List[str]:
        """Parse comma-separated environment variable into list with debug logging"""
        if not value:
            logger.warning(f"🔧 PARSE_LIST - Empty value provided")
            return []
        
        parsed = [item.strip() for item in value.split(',') if item.strip()]
        logger.debug(f"🔧 PARSE_LIST - Input: '{value}' -> Output: {parsed}")
        return parsed
    
    def _validate_and_warn_configuration(self):
        """Validate configuration and warn about missing required settings"""
        warnings = []
        critical_missing = []
        
        if not self.openai_api_key:
            critical_missing.append("OpenAI API key")
        
        if not self.jira_api_token or not self.jira_base_url:
            critical_missing.append("JIRA configuration (API token or base URL)")
        
        if not self.github_token or not self.github_repo_owner or not self.github_repo_name:
            warnings.append("GitHub configuration incomplete - PR creation and automated deployment will not work")
        
        # Log validation results
        if critical_missing:
            logger.error("❌ CRITICAL CONFIGURATION MISSING:")
            for missing in critical_missing:
                logger.error(f"   - {missing}")
        
        if warnings:
            logger.warning("⚠️ CONFIGURATION WARNINGS:")
            for warning in warnings:
                logger.warning(f"   - {warning}")
        
        if not critical_missing and not warnings:
            logger.info("✅ ENHANCED CONFIGURATION VALIDATION - All critical settings present")
    
    def get_jira_jql(self) -> str:
        """Generate JQL query for JIRA ticket polling with enhanced debugging"""
        issue_types = "','".join(self.jira_issue_types)
        statuses = "','".join(self.jira_statuses)
        
        logger.debug("🔧 JQL CONSTRUCTION DEBUG:")
        logger.debug(f"   - Issue Types List: {self.jira_issue_types}")
        logger.debug(f"   - Statuses List: {self.jira_statuses}")
        logger.debug(f"   - Issue Types String: '{issue_types}'")
        logger.debug(f"   - Statuses String: '{statuses}'")
        
        jql = f"""
        project = '{self.jira_project_key}' 
        AND issueType IN ('{issue_types}') 
        AND status IN ('{statuses}')
        ORDER BY priority DESC, created DESC
        """
        
        cleaned_jql = " ".join(jql.split())
        logger.debug(f"   - Final JQL: {cleaned_jql}")
        
        return cleaned_jql
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for API responses"""
        return {
            "jira_configured": bool(self.jira_base_url and self.jira_api_token),
            "github_configured": bool(self.github_token and self.github_repo_owner and self.github_repo_name),
            "openai_configured": bool(self.openai_api_key),
            "jira_project_key": self.jira_project_key,
            "jira_issue_types": self.jira_issue_types,
            "jira_statuses": self.jira_statuses,
            "github_status": self.get_github_status(),
            "max_source_files": self.max_source_files,
            "agent_intervals": {
                "process": self.agent_process_interval,
                "intake": self.agent_intake_interval,
                "poll": self.agent_poll_interval
            },
            "priority_weights": self.priority_weights,
            "complexity_settings": {
                "description_threshold": self.complexity_description_threshold,
                "default": self.complexity_default
            },
            "jira_pagination": {
                "max_results": self.jira_max_results,
                "max_total_results": self.jira_max_total_results,
                "force_reprocess": self.jira_force_reprocess
            },
            "enhanced_automation": True,
            "comprehensive_jira_integration": True
        }

    def get_github_status(self) -> Dict[str, Any]:
        """Get GitHub configuration status"""
        return {
            "configured": bool(self.github_token and self.github_repo_owner and self.github_repo_name),
            "has_token": bool(self.github_token),
            "has_repo_owner": bool(self.github_repo_owner), 
            "has_repo_name": bool(self.github_repo_name),
            "target_branch": self.github_target_branch,
            "repo_full_name": f"{self.github_repo_owner}/{self.github_repo_name}" if self.github_repo_owner and self.github_repo_name else None
        }

# Global configuration instance
config = Config()
