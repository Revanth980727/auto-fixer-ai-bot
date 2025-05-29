
"""
Script to create test data for development
"""
import asyncio
import sys
import os
import json

# Add the parent directory to sys.path to import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.database import get_sync_db, init_db
from core.models import Ticket, TicketStatus
from core.config import config

async def create_test_tickets():
    """Create test tickets based on configuration"""
    
    # Check if test data creation is enabled
    if not config.create_test_data:
        print("Test data creation is disabled in configuration")
        return
    
    # Initialize database
    await init_db()
    
    # Load test data from configuration file
    test_data_path = os.path.join(os.path.dirname(__file__), config.test_data_config_file)
    
    try:
        with open(test_data_path, 'r') as f:
            test_data = json.load(f)
    except FileNotFoundError:
        print(f"Test data file not found: {test_data_path}")
        return
    except json.JSONDecodeError as e:
        print(f"Error parsing test data file: {e}")
        return
    
    test_tickets = test_data.get("tickets", [])
    
    if not test_tickets:
        print("No test tickets found in configuration file")
        return
    
    with next(get_sync_db()) as db:
        created_count = 0
        for ticket_data in test_tickets:
            # Check if ticket already exists
            existing = db.query(Ticket).filter(Ticket.jira_id == ticket_data["jira_id"]).first()
            if not existing:
                # Add default status if not specified
                if "status" not in ticket_data:
                    ticket_data["status"] = TicketStatus.TODO
                
                ticket = Ticket(**ticket_data)
                db.add(ticket)
                created_count += 1
                print(f"Created test ticket: {ticket_data['jira_id']}")
        
        db.commit()
        print(f"Test data creation completed! Created {created_count} tickets")

async def clear_test_data():
    """Clear all test data from database"""
    await init_db()
    
    # Load test data to get IDs to remove
    test_data_path = os.path.join(os.path.dirname(__file__), config.test_data_config_file)
    
    try:
        with open(test_data_path, 'r') as f:
            test_data = json.load(f)
    except FileNotFoundError:
        print(f"Test data file not found: {test_data_path}")
        return
    
    test_tickets = test_data.get("tickets", [])
    jira_ids = [ticket["jira_id"] for ticket in test_tickets]
    
    with next(get_sync_db()) as db:
        deleted_count = 0
        for jira_id in jira_ids:
            ticket = db.query(Ticket).filter(Ticket.jira_id == jira_id).first()
            if ticket:
                db.delete(ticket)
                deleted_count += 1
                print(f"Deleted test ticket: {jira_id}")
        
        db.commit()
        print(f"Test data cleanup completed! Deleted {deleted_count} tickets")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Manage test data")
    parser.add_argument("action", choices=["create", "clear"], help="Action to perform")
    args = parser.parse_args()
    
    if args.action == "create":
        asyncio.run(create_test_tickets())
    elif args.action == "clear":
        asyncio.run(clear_test_data())
