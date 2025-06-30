import requests
from typing import Dict, Any, Optional, List
import os
import base64
import logging
from core.config import config

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
        logger.info(f"GitHub Configuration - Target branch: {config.github_target_branch}")
        if not self._is_configured():
            logger.warning("GitHub client is not properly configured - will operate in degraded mode")
    
    async def get_repository_tree(self, branch: str = None, recursive: bool = True) -> List[Dict[str, Any]]:
        """Get repository tree structure from GitHub API"""
        if not self._is_configured():
            logger.warning("GitHub not configured - cannot get repository tree")
            return []
        
        # Use configured branch if not specified
        if branch is None:
            branch = config.github_target_branch
        
        try:
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/trees/{branch}"
            params = {"recursive": "1"} if recursive else {}
            
            logger.info(f"Fetching repository tree from branch: {branch}")
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                tree_items = data.get("tree", [])
                logger.info(f"Successfully fetched repository tree: {len(tree_items)} items")
                return tree_items
            elif response.status_code == 404:
                logger.warning(f"Repository tree not found for branch: {branch}")
                return []
            else:
                logger.error(f"Failed to get repository tree: HTTP {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting repository tree: {e}")
            return []

    async def get_file_content(self, file_path: str, branch: str = None) -> Optional[str]:
        """Get file content from repository with better error handling"""
        if not self._is_configured():
            logger.warning(f"GitHub not configured - cannot fetch {file_path}")
            return None
        
        # Use configured branch if not specified
        if branch is None:
            branch = config.github_target_branch
        
        try:
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{file_path}"
            response = requests.get(url, headers=self.headers, params={"ref": branch})
            
            if response.status_code == 200:
                data = response.json()
                content = base64.b64decode(data["content"]).decode("utf-8")
                logger.info(f"Successfully fetched file: {file_path} from branch: {branch}")
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
    
    async def create_branch(self, branch_name: str, base_branch: str = None) -> bool:
        """Create a new branch"""
        if not self._is_configured():
            logger.warning("GitHub not configured - cannot create branch")
            return False
        
        # Use configured branch if not specified
        if base_branch is None:
            base_branch = config.github_target_branch
        
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
    
    async def commit_file(self, file_path: str, content: str, commit_message: str, branch: str = None) -> bool:
        """Commit file changes to repository"""
        if not self._is_configured():
            logger.warning("GitHub not configured - cannot commit file")
            return False
        
        # Use configured branch if not specified
        if branch is None:
            branch = config.github_target_branch
        
        try:
            logger.info(f"🔧 Starting commit for {file_path} to branch {branch}")
            
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
                logger.info(f"📝 File {file_path} exists, updating with SHA")
            else:
                logger.info(f"📝 File {file_path} does not exist, creating new file")
            
            logger.info(f"🔧 Sending commit request for {file_path}")
            response = requests.put(file_url, headers=self.headers, json=commit_data)
            
            logger.info(f"🔧 Commit response status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ Successfully committed file: {file_path} to branch: {branch}")
                return True
            else:
                logger.error(f"❌ Failed to commit file {file_path}: HTTP {response.status_code}")
                logger.error(f"❌ Response text: {response.text}")
                return False
            
        except Exception as e:
            logger.error(f"❌ Error committing file {file_path}: {e}")
            return False
    
    async def create_pull_request(self, title: str, body: str, head_branch: str, base_branch: str = None) -> Optional[Dict]:
        """Create a pull request"""
        if not self._is_configured():
            logger.warning("GitHub not configured - cannot create pull request")
            return None
        
        # Use configured branch if not specified
        if base_branch is None:
            base_branch = config.github_target_branch
        
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
            "repo_full_name": f"{self.repo_owner}/{self.repo_name}" if self.repo_owner and self.repo_name else None,
            "target_branch": config.github_target_branch
        }
