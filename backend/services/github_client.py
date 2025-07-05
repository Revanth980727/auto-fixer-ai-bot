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
        logger.info(f"🔧 GitHub Configuration - Token present: {'Yes' if self.token else 'No'}")
        logger.info(f"🔧 GitHub Configuration - Repo owner: {self.repo_owner or 'Not set'}")
        logger.info(f"🔧 GitHub Configuration - Repo name: {self.repo_name or 'Not set'}")
        logger.info(f"🔧 GitHub Configuration - Target branch: {config.github_target_branch}")
        if not self._is_configured():
            logger.warning("⚠️ GitHub client is not properly configured - will operate in degraded mode")
            logger.warning(f"⚠️ Missing: Token={not bool(self.token)}, Owner={not bool(self.repo_owner)}, Repo={not bool(self.repo_name)}")
        else:
            logger.info(f"✅ GitHub client fully configured for {self.repo_owner}/{self.repo_name}")
    
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
            logger.info(f"🔧 Repository: {self.repo_owner}/{self.repo_name}")
            logger.info(f"🔧 Commit message: {commit_message}")
            
            # Get current file SHA if it exists
            file_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{file_path}"
            logger.info(f"🔍 Checking if file exists: {file_url}")
            
            file_response = requests.get(file_url, headers=self.headers, params={"ref": branch})
            logger.info(f"🔍 File check response: {file_response.status_code}")
            
            commit_data = {
                "message": commit_message,
                "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
                "branch": branch
            }
            
            if file_response.status_code == 200:
                # File exists, include SHA for update
                file_data = file_response.json()
                commit_data["sha"] = file_data["sha"]
                logger.info(f"📝 File {file_path} exists, updating with SHA: {file_data['sha'][:8]}...")
            elif file_response.status_code == 404:
                logger.info(f"📝 File {file_path} does not exist, creating new file")
            else:
                logger.warning(f"⚠️ Unexpected response when checking file existence: {file_response.status_code}")
                logger.warning(f"⚠️ Response: {file_response.text}")
            
            logger.info(f"🔧 Sending commit request for {file_path} to {self.base_url}")
            response = requests.put(file_url, headers=self.headers, json=commit_data)
            
            logger.info(f"🔧 Commit response status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                response_data = response.json()
                commit_sha = response_data.get('commit', {}).get('sha', 'unknown')
                logger.info(f"✅ Successfully committed file: {file_path} to branch: {branch}")
                logger.info(f"✅ Commit SHA: {commit_sha[:8]}...")
                logger.info(f"✅ GitHub URL: https://github.com/{self.repo_owner}/{self.repo_name}/commit/{commit_sha}")
                return True
            else:
                logger.error(f"❌ Failed to commit file {file_path}: HTTP {response.status_code}")
                logger.error(f"❌ Response headers: {dict(response.headers)}")
                logger.error(f"❌ Response text: {response.text}")
                # Try to parse error details
                try:
                    error_data = response.json()
                    if 'message' in error_data:
                        logger.error(f"❌ GitHub API Error: {error_data['message']}")
                    if 'errors' in error_data:
                        for error in error_data['errors']:
                            logger.error(f"❌ GitHub API Error Detail: {error}")
                except:
                    pass
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
