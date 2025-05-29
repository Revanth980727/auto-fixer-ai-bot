
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from core.database import get_sync_db
from core.models import Ticket, TicketStatus
from services.jira_client import JIRAClient
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/jira")
async def jira_webhook(request: Request, db: Session = Depends(get_sync_db)):
    """Handle JIRA webhook notifications"""
    try:
        payload = await request.json()
        
        # Handle different JIRA events
        webhook_event = payload.get("webhookEvent")
        issue = payload.get("issue", {})
        
        if webhook_event == "jira:issue_created":
            await handle_issue_created(issue, db)
        elif webhook_event == "jira:issue_updated":
            await handle_issue_updated(issue, db)
        
        return {"status": "processed", "event": webhook_event}
        
    except Exception as e:
        logger.error(f"Error processing JIRA webhook: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/github")
async def github_webhook(request: Request, db: Session = Depends(get_sync_db)):
    """Handle GitHub webhook notifications"""
    try:
        payload = await request.json()
        
        # Handle different GitHub events
        action = payload.get("action")
        pull_request = payload.get("pull_request", {})
        
        if action == "closed" and pull_request.get("merged"):
            await handle_pr_merged(pull_request, db)
        
        return {"status": "processed", "action": action}
        
    except Exception as e:
        logger.error(f"Error processing GitHub webhook: {e}")
        raise HTTPException(status_code=400, detail=str(e))

async def handle_issue_created(issue: dict, db: Session):
    """Handle new JIRA issue creation"""
    fields = issue.get("fields", {})
    issue_type = fields.get("issuetype", {}).get("name", "")
    
    # Only process bug issues
    if issue_type.lower() != "bug":
        return
    
    jira_client = JIRAClient()
    ticket_data = jira_client.format_ticket_data(issue)
    
    # Check if ticket already exists
    existing = db.query(Ticket).filter(Ticket.jira_id == ticket_data["jira_id"]).first()
    if not existing:
        ticket = Ticket(**ticket_data)
        db.add(ticket)
        db.commit()
        logger.info(f"Created ticket from webhook: {ticket.jira_id}")

async def handle_issue_updated(issue: dict, db: Session):
    """Handle JIRA issue updates"""
    jira_id = issue.get("key")
    
    # Find existing ticket and update if needed
    ticket = db.query(Ticket).filter(Ticket.jira_id == jira_id).first()
    if ticket:
        fields = issue.get("fields", {})
        ticket.title = fields.get("summary", ticket.title)
        ticket.updated_at = datetime.utcnow()
        db.add(ticket)
        db.commit()

async def handle_pr_merged(pull_request: dict, db: Session):
    """Handle merged pull request"""
    # Extract ticket information from PR title or branch
    pr_title = pull_request.get("title", "")
    
    # Simple extraction - look for JIRA ticket ID in title
    import re
    jira_match = re.search(r'([A-Z]+-\d+)', pr_title)
    
    if jira_match:
        jira_id = jira_match.group(1)
        ticket = db.query(Ticket).filter(Ticket.jira_id == jira_id).first()
        
        if ticket:
            ticket.status = TicketStatus.COMPLETED
            ticket.updated_at = datetime.utcnow()
            db.add(ticket)
            db.commit()
            logger.info(f"Marked ticket {jira_id} as completed due to merged PR")
