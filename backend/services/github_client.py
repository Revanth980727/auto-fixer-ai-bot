
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
    
    async def get_file_content(self, file_path: str, branch: str = "main") -> Optional[str]:
        """Get file content from repository"""
        if not self._is_configured():
            return None
        
        try:
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{file_path}"
            response = requests.get(url, headers=self.headers, params={"ref": branch})
            
            if response.status_code == 200:
                data = response.json()
                content = base64.b64decode(data["content"]).decode("utf-8")
                return content
            else:
                logger.error(f"Failed to get file {file_path}: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting file content: {e}")
            return None
    
    async def create_branch(self, branch_name: str, base_branch: str = "main") -> bool:
        """Create a new branch"""
        if not self._is_configured():
            return False
        
        try:
            # Get base branch SHA
            ref_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/ref/heads/{base_branch}"
            ref_response = requests.get(ref_url, headers=self.headers)
            
            if ref_response.status_code != 200:
                return False
            
            base_sha = ref_response.json()["object"]["sha"]
            
            # Create new branch
            create_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/refs"
            create_data = {
                "ref": f"refs/heads/{branch_name}",
                "sha": base_sha
            }
            
            response = requests.post(create_url, headers=self.headers, json=create_data)
            return response.status_code == 201
            
        except Exception as e:
            logger.error(f"Error creating branch {branch_name}: {e}")
            return False
    
    async def commit_file(self, file_path: str, content: str, commit_message: str, branch: str) -> bool:
        """Commit file changes to repository"""
        if not self._is_configured():
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
            return response.status_code in [200, 201]
            
        except Exception as e:
            logger.error(f"Error committing file {file_path}: {e}")
            return False
    
    async def create_pull_request(self, title: str, body: str, head_branch: str, base_branch: str = "main") -> Optional[Dict]:
        """Create a pull request"""
        if not self._is_configured():
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
                return response.json()
            else:
                logger.error(f"Failed to create PR: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating pull request: {e}")
            return None
    
    def _is_configured(self) -> bool:
        """Check if GitHub client is properly configured"""
        return bool(self.token and self.repo_owner and self.repo_name)
