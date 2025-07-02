import logging
from typing import Dict, Any, List, Optional
from services.semantic_patcher import SemanticPatcher
from services.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

class SemanticFileHandler:
    """Handles large files using semantic analysis and surgical patching."""
    
    def __init__(self):
        self.semantic_patcher = SemanticPatcher()
        self.openai_client = OpenAIClient()
    
    async def process_file_semantically(self, file_info: Dict[str, Any], ticket: Any) -> Optional[Dict[str, Any]]:
        """Process a file using semantic analysis and surgical patching."""
        try:
            logger.info(f"🎯 Starting semantic processing for {file_info['path']}")
            
            content = file_info['content']
            file_path = file_info['path']
            
            # Extract issue description from ticket
            issue_description = self._extract_issue_description(ticket)
            
            # Identify target nodes for fixing
            targets = self.semantic_patcher.identify_target_nodes(content, issue_description)
            
            if not targets:
                logger.warning(f"⚠️ No semantic targets identified for {file_path}")
                return None
            
            logger.info(f"🎯 Found {len(targets)} potential targets for {file_path}")
            
            # Generate surgical fixes for each target
            successful_patches = []
            for target in targets:
                patch_result = await self._generate_and_apply_surgical_fix(
                    content, target, issue_description, file_path
                )
                
                if patch_result and patch_result['success']:
                    successful_patches.append(patch_result)
                    logger.info(f"✅ Successfully applied surgical patch to {target['name']}")
                    
                    # For now, apply the first successful patch
                    # In future, we could combine multiple successful patches
                    break
            
            if not successful_patches:
                logger.warning(f"⚠️ No successful surgical patches for {file_path}")
                return None
            
            # Return the best patch
            best_patch = successful_patches[0]
            
            return {
                'patch_content': best_patch['patch_diff'],
                'patched_code': best_patch['patched_content'],
                'confidence_score': 0.9,  # High confidence for surgical patches
                'commit_message': f"Apply surgical fix to {best_patch['target_name']} in {file_path}",
                'explanation': f"Applied targeted fix to {best_patch['target_name']} ({best_patch['lines_changed']} lines changed)",
                'patch_type': 'semantic_surgical',
                'target_name': best_patch['target_name'],
                'lines_changed': best_patch['lines_changed'],
                'addresses_issue': True
            }
            
        except Exception as e:
            logger.error(f"💥 Error in semantic file processing: {e}")
            return None
    
    def _extract_issue_description(self, ticket: Any) -> str:
        """Extract issue description from ticket."""
        try:
            # Try different ways to get issue description
            if hasattr(ticket, 'description') and ticket.description:
                return ticket.description
            elif hasattr(ticket, 'summary') and ticket.summary:
                return ticket.summary
            elif hasattr(ticket, 'title') and ticket.title:
                return ticket.title
            else:
                return "Fix code issues"
        except Exception:
            return "Fix code issues"
    
    async def _generate_and_apply_surgical_fix(self, content: str, target: Dict[str, Any], 
                                             issue_description: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Generate and apply a surgical fix for a specific target."""
        try:
            # Generate surgical fix prompt
            fix_info = self.semantic_patcher.generate_surgical_fix(target, issue_description, file_path)
            
            if not fix_info:
                return None
            
            # Get AI-generated fix
            prompt = fix_info['prompt']
            
            try:
                response = await self.openai_client.complete_chat(
                    messages=[{"role": "user", "content": prompt}],
                    model="gpt-4o-mini"
                )
                
                fixed_content = response.choices[0].message.content.strip()
                
                # Remove code block markers if present
                if fixed_content.startswith('```'):
                    lines = fixed_content.split('\n')
                    if lines[0].startswith('```'):
                        lines = lines[1:]
                    if lines and lines[-1].strip() == '```':
                        lines = lines[:-1]
                    fixed_content = '\n'.join(lines)
                
            except Exception as e:
                logger.error(f"❌ Error getting AI fix for {target['name']}: {e}")
                return None
            
            # Apply the surgical patch
            patch_result = self.semantic_patcher.apply_surgical_patch(
                content, 
                {**fix_info, 'file_path': file_path}, 
                fixed_content
            )
            
            return patch_result
            
        except Exception as e:
            logger.error(f"❌ Error in surgical fix generation: {e}")
            return None
    
    def should_use_semantic_approach(self, file_info: Dict[str, Any]) -> bool:
        """Determine if semantic approach should be used for this file."""
        content = file_info.get('content', '')
        file_path = file_info.get('path', '')
        
        # Use semantic approach for Python files over 5000 characters
        if file_path.endswith('.py') and len(content) > 5000:
            return True
            
        # Use for files with complex structure (many functions/classes)
        if file_path.endswith('.py'):
            function_count = content.count('def ')
            class_count = content.count('class ')
            if function_count + class_count > 8:
                return True
        
        return False