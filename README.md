
# AI Agent System - Autonomous Bug Fixing Platform

A complete autonomous AI system that monitors JIRA for bug tickets, generates code fixes using GPT-4, tests them automatically, and creates pull requests on GitHub.

## 🚀 Features

### Backend (Python/FastAPI)
- **Autonomous Ticket Processing**: Polls JIRA every 2 minutes for new bug tickets
- **AI Agent Pipeline**: 5 specialized agents (Intake, Planner, Developer, QA, Communicator)
- **GPT-4 Integration**: Smart code analysis and patch generation
- **Automated Testing**: Isolated Docker environments for safe testing
- **GitHub Integration**: Automatic PR creation and management
- **Real-time WebSocket**: Live updates and monitoring
- **Retry Logic**: Exponential backoff with automatic escalation

### Frontend (React/TypeScript)
- **Real-time Dashboard**: Live monitoring of all system components
- **Ticket Management**: Search, filter, and manage tickets
- **Agent Control**: Enable/disable agents and view performance metrics
- **Live Logs**: Real-time log streaming from agent executions
- **Analytics**: Success rates, performance metrics, and trends
- **Responsive Design**: Works on desktop and mobile devices

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   JIRA API      │    │   GitHub API    │    │   OpenAI API    │
│   (Polling)     │    │   (PR Creation) │    │   (GPT-4)       │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AI Agent System (FastAPI)                    │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │ Intake  │ │Planner  │ │Developer│ │   QA    │ │Communi- │  │
│  │ Agent   │ │ Agent   │ │ Agent   │ │ Agent   │ │ cator   │  │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘  │
└─────────────────────┬───────────────────────────────────────────┘
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
    ┌─────────┐ ┌─────────┐ ┌─────────┐
    │PostgreSQL│ │  Redis  │ │Frontend │
    │Database │ │ Queue   │ │Dashboard│
    └─────────┘ └─────────┘ └─────────┘
```

## 🛠️ Quick Start

### Prerequisites
- Docker and Docker Compose
- OpenAI API key
- JIRA API token
- GitHub personal access token

### 1. Clone and Setup
```bash
git clone <repository-url>
cd ai-agent-system
cp .env.example .env
# Edit .env with your API keys
```

### 2. Start the System
```bash
docker-compose up -d
```

### 3. Access the Dashboard
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## 📊 Agent Workflow

### 1. Intake Agent
- Polls JIRA API every 2 minutes
- Filters for new "To-Do" bug tickets
- Extracts error traces and file information
- Queues tickets for processing

### 2. Planner Agent
- Analyzes bug descriptions and error traces
- Uses GPT-4 to infer root causes
- Predicts likely affected files
- Creates execution plan for Developer Agent

### 3. Developer Agent
- Generates code patches using GPT-4
- Creates unit tests for fixes
- Provides confidence scores
- Saves patch attempts to database

### 4. QA Agent
- Applies patches in isolated Docker containers
- Runs existing and new tests
- Validates code syntax and functionality
- Reports test results and success/failure

### 5. Communicator Agent
- Creates GitHub branches and commits
- Opens pull requests with detailed descriptions
- Updates JIRA tickets with progress
- Handles escalation for failed fixes

## 🔧 Configuration

### Environment Variables
```bash
# Core APIs
OPENAI_API_KEY=sk-...
JIRA_API_TOKEN=ATATT...
JIRA_BASE_URL=https://company.atlassian.net
GITHUB_TOKEN=ghp_...

# Database
DATABASE_URL=postgresql://postgres:password@postgres:5432/ai_agents

# Redis
REDIS_URL=redis://redis:6379
```

### Agent Configuration
Agents can be enabled/disabled via the dashboard or API:
```bash
curl -X POST http://localhost:8000/api/agents/developer/toggle
```

## 📈 Monitoring & Analytics

### Dashboard Features
- **System Overview**: Total tickets, success rates, resolution times
- **Ticket Management**: Search, filter, retry, and escalate tickets
- **Agent Status**: Real-time agent health and performance
- **Live Logs**: Streaming logs from agent executions
- **Analytics**: Charts and metrics for system performance

### Key Metrics
- **Success Rate**: Percentage of tickets automatically resolved
- **Resolution Time**: Average time from ticket creation to PR
- **Agent Performance**: Individual agent success rates and response times
- **Escalation Rate**: Percentage of tickets requiring human intervention

## 🔒 Security

- **API Authentication**: JWT tokens for API access
- **Environment Isolation**: Docker containers for safe testing
- **Input Validation**: Sanitization of all external inputs
- **Rate Limiting**: Protection against API abuse
- **Secure Storage**: Encrypted storage of API keys and secrets

## 🚀 Deployment

### Production Deployment
1. Set up production environment variables
2. Configure reverse proxy (Nginx)
3. Set up SSL certificates
4. Configure monitoring and logging
5. Set up backup procedures

### Scaling
- **Horizontal Scaling**: Add more agent instances
- **Load Balancing**: Distribute workload across instances
- **Database Optimization**: Connection pooling and indexing
- **Caching**: Redis for improved performance

## 📝 API Documentation

### Main Endpoints
- `GET /api/tickets` - List all tickets
- `GET /api/tickets/{id}` - Get ticket details
- `POST /api/tickets/{id}/retry` - Retry failed ticket
- `GET /api/agents/status` - Get agent status
- `POST /api/agents/{type}/toggle` - Enable/disable agent
- `GET /api/metrics/system` - Get system metrics

### WebSocket Events
- `ticket_update` - Ticket status changes
- `agent_status` - Agent activity updates
- `system_alert` - Important system notifications

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the documentation
2. Search existing issues
3. Create a new issue with detailed information
4. Include logs and configuration details

---

**Note**: This system is designed for autonomous operation. Monitor the dashboard regularly and review escalated tickets that require human intervention.
