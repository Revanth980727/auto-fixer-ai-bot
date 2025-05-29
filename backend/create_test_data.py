
"""
Script to create test data for development
"""
import asyncio
import sys
import os

# Add the parent directory to sys.path to import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.database import get_sync_db, init_db
from core.models import Ticket, TicketStatus

async def create_test_tickets():
    """Create some test tickets for development"""
    
    # Initialize database
    await init_db()
    
    test_tickets = [
        {
            "jira_id": "BUG-001",
            "title": "Application crashes when processing large files",
            "description": "Users report that the application crashes when they try to process files larger than 100MB. This happens consistently across different file types.",
            "error_trace": """
Traceback (most recent call last):
  File "/app/file_processor.py", line 45, in process_file
    data = file.read()
  File "/usr/lib/python3.9/io.py", line 322, in read
    return self._readall()
MemoryError: Unable to allocate 134217728 bytes
            """,
            "priority": "high",
            "status": TicketStatus.TODO
        },
        {
            "jira_id": "BUG-002", 
            "title": "Login fails with special characters in password",
            "description": "Users cannot log in when their password contains special characters like @, #, or &. The login form returns an 'Invalid credentials' error.",
            "error_trace": """
2024-01-15 10:30:25 ERROR: Authentication failed for user 'john@example.com'
2024-01-15 10:30:25 DEBUG: Password hash comparison failed
2024-01-15 10:30:25 INFO: SQL Query: SELECT * FROM users WHERE email = 'john@example.com' AND password = 'hashed_password'
            """,
            "priority": "medium",
            "status": TicketStatus.TODO
        },
        {
            "jira_id": "BUG-003",
            "title": "Database connection timeout in production",
            "description": "The application intermittently loses database connection in production environment, causing 500 errors for users.",
            "error_trace": """
pymysql.err.OperationalError: (2013, 'Lost connection to MySQL server during query ([Errno 110] Connection timed out)')
  File "/app/database.py", line 78, in execute_query
    cursor.execute(query, params)
            """,
            "priority": "critical",
            "status": TicketStatus.TODO
        }
    ]
    
    with next(get_sync_db()) as db:
        for ticket_data in test_tickets:
            # Check if ticket already exists
            existing = db.query(Ticket).filter(Ticket.jira_id == ticket_data["jira_id"]).first()
            if not existing:
                ticket = Ticket(**ticket_data)
                db.add(ticket)
                print(f"Created test ticket: {ticket_data['jira_id']}")
        
        db.commit()
        print("Test data creation completed!")

if __name__ == "__main__":
    asyncio.run(create_test_tickets())
