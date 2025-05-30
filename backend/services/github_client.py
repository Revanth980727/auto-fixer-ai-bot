
import requests
from typing import Dict, Any, Optional
import os
import base64
import logging

logger = logging.getLogger(__name__)

class GitHubClient:
    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        self.repo_owner = os.getenv("GITHUB_REPO_OWNER")
        self.repo_name = os.getenv("GITHUB_REPO_NAME")
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.base_url = "https://api.github.com"
        self._log_configuration()
    
    def _log_configuration(self):
        """Log GitHub configuration status"""
        logger.info(f"GitHub Configuration - Token present: {'Yes' if self.token else 'No'}")
        logger.info(f"GitHub Configuration - Repo owner: {self.repo_owner or 'Not set'}")
        logger.info(f"GitHub Configuration - Repo name: {self.repo_name or 'Not set'}")
        if not self._is_configured():
            logger.warning("GitHub client is not properly configured - will operate in degraded mode")
    
    async def get_file_content(self, file_path: str, branch: str = "main") -> Optional[str]:
        """Get file content from repository with better error handling"""
        if not self._is_configured():
            logger.warning(f"GitHub not configured - cannot fetch {file_path}")
            return None
        
        try:
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{file_path}"
            response = requests.get(url, headers=self.headers, params={"ref": branch})
            
            if response.status_code == 200:
                data = response.json()
                content = base64.b64decode(data["content"]).decode("utf-8")
                logger.info(f"Successfully fetched file: {file_path}")
                return content
            elif response.status_code == 404:
                logger.warning(f"File not found in repository: {file_path}")
                return None
            else:
                logger.error(f"Failed to get file {file_path}: HTTP {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting file content for {file_path}: {e}")
            return None
    
    async def create_branch(self, branch_name: str, base_branch: str = "main") -> bool:
        """Create a new branch"""
        if not self._is_configured():
            logger.warning("GitHub not configured - cannot create branch")
            return False
        
        try:
            # Get base branch SHA
            ref_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/ref/heads/{base_branch}"
            ref_response = requests.get(ref_url, headers=self.headers)
            
            if ref_response.status_code != 200:
                logger.error(f"Failed to get base branch {base_branch}: {ref_response.status_code}")
                return False
            
            base_sha = ref_response.json()["object"]["sha"]
            
            # Create new branch
            create_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/refs"
            create_data = {
                "ref": f"refs/heads/{branch_name}",
                "sha": base_sha
            }
            
            response = requests.post(create_url, headers=self.headers, json=create_data)
            if response.status_code == 201:
                logger.info(f"Successfully created branch: {branch_name}")
                return True
            else:
                logger.error(f"Failed to create branch {branch_name}: {response.status_code}")
                return False
            
        except Exception as e:
            logger.error(f"Error creating branch {branch_name}: {e}")
            return False
    
    async def commit_file(self, file_path: str, content: str, commit_message: str, branch: str) -> bool:
        """Commit file changes to repository"""
        if not self._is_configured():
            logger.warning("GitHub not configured - cannot commit file")
            return False
        
        try:
            # Get current file SHA if it exists
            file_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{file_path}"
            file_response = requests.get(file_url, headers=self.headers, params={"ref": branch})
            
            commit_data = {
                "message": commit_message,
                "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
                "branch": branch
            }
            
            if file_response.status_code == 200:
                # File exists, include SHA for update
                commit_data["sha"] = file_response.json()["sha"]
            
            response = requests.put(file_url, headers=self.headers, json=commit_data)
            if response.status_code in [200, 201]:
                logger.info(f"Successfully committed file: {file_path}")
                return True
            else:
                logger.error(f"Failed to commit file {file_path}: {response.status_code}")
                return False
            
        except Exception as e:
            logger.error(f"Error committing file {file_path}: {e}")
            return False
    
    async def create_pull_request(self, title: str, body: str, head_branch: str, base_branch: str = "main") -> Optional[Dict]:
        """Create a pull request"""
        if not self._is_configured():
            logger.warning("GitHub not configured - cannot create pull request")
            return None
        
        try:
            pr_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls"
            pr_data = {
                "title": title,
                "body": body,
                "head": head_branch,
                "base": base_branch
            }
            
            response = requests.post(pr_url, headers=self.headers, json=pr_data)
            
            if response.status_code == 201:
                logger.info(f"Successfully created pull request: {title}")
                return response.json()
            else:
                logger.error(f"Failed to create PR: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating pull request: {e}")
            return None
    
    def _is_configured(self) -> bool:
        """Check if GitHub client is properly configured"""
        return bool(self.token and self.repo_owner and self.repo_name)
    
    def get_configuration_status(self) -> Dict[str, Any]:
        """Get configuration status for debugging"""
        return {
            "configured": self._is_configured(),
            "has_token": bool(self.token),
            "has_repo_owner": bool(self.repo_owner),
            "has_repo_name": bool(self.repo_name),
            "repo_full_name": f"{self.repo_owner}/{self.repo_name}" if self.repo_owner and self.repo_name else None
        }
