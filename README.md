# Personal AI Agent 🤖

A powerful, extensible personal AI assistant that connects to your Google services (Calendar, Gmail, Drive, Docs, Sheets, Maps, YouTube) to help you manage your digital life. Built with FastAPI, React, and Claude/OpenAI for intelligent task automation.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![React](https://img.shields.io/badge/react-18+-61DAFB.svg)

## 🌟 Features

### Current Capabilities

**🔍 Intelligent Research Agent**
- Web search with Tavily API integration
- Content extraction and summarization
- Hybrid memory system (vector similarity + keyword search)
- Multi-step reasoning with visible thought process
- Automatic source citation

**📅 Google Calendar Integration**
- Create, read, update, and delete events
- Recurring events (daily, weekly, weekdays, monthly)
- Smart scheduling with availability checking
- Find free time slots automatically
- Morning briefing with today's schedule
- Event reminders and timezone support
- Multi-attendee meeting coordination

**📧 Gmail Management**
- List and filter emails (unread, search queries)
- Read full email content
- Send emails with rich formatting
- Mark emails as read/unread
- Gmail query syntax support

**📁 Google Drive & Docs**
- List and search files/folders
- Read Google Docs content
- Create new Google Docs
- Update existing docs (append, prepend, replace)
- File metadata and sharing information

**📊 Google Sheets**
- Read spreadsheet data with range selection
- Create new spreadsheets
- Update cell values with JSON arrays
- Append rows to existing sheets
- Multi-row batch operations

**🗺️ Google Maps**
- Calculate distance and travel time between locations
- Support for multiple travel modes (driving, walking, bicycling, transit)
- Search for places and points of interest
- Geocoding (address to coordinates)

**📺 YouTube**
- Search videos by keyword or topic
- Get detailed video information (views, likes, description)
- View trending videos
- Access personal watch history (liked videos)
- View subscriptions
- Access playlists (Watch Later, etc.)

### 🏗️ Architecture

**Backend (FastAPI)**
- Modular tool registry system for easy extension
- Dynamic system prompt generation
- Multi-turn conversation with agent loop
- Supabase PostgreSQL database with pgvector for semantic search
- OAuth 2.0 integration for secure Google API access
- OpenAI GPT-4 for reasoning and tool selection

**Frontend (React + TypeScript)**
- Real-time agent reasoning display
- Step-by-step action visualization
- Memory panel showing past related research
- Source citation with clickable links
- Conversation threading
- Settings panel for customization

**Database (Supabase)**
- Agent run history with embeddings
- Conversation threads
- Vector similarity search with pgvector extension
- Automatic timestamp tracking

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Google Cloud Project with APIs enabled
- Supabase account
- OpenAI API key
- Tavily API key

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/shivpatel0812/PersonalAIAgent.git
cd PersonalAIAgent
```

2. **Backend setup**
```bash
cd backend
pip install -r requirements.txt
```

3. **Frontend setup**
```bash
cd frontend
npm install
```

4. **Environment configuration**

Create a `.env` file in the root directory:

```env
# Frontend
VITE_API_URL=http://localhost:8001
VITE_SUPABASE_URL=your_supabase_url
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key

# Backend
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_key
SUPABASE_ANON_KEY=your_supabase_anon_key
CORS_ORIGINS=http://localhost:5173,http://localhost:5174

# OpenAI
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini

# Tavily (web search)
TAVILY_API_KEY=your_tavily_api_key

# Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8001/auth/google/callback

# Google Maps
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
```

5. **Database setup**

Run Supabase migrations:
```bash
cd supabase
supabase db push
```

Or apply migrations manually to your Supabase project.

### Running the Application

**Development mode:**

```bash
# Terminal 1 - Backend
cd backend
uvicorn app.main:app --reload --port 8001

# Terminal 2 - Frontend
cd frontend
npm run dev
```

Access the application at `http://localhost:5173`

### Google Services Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project
3. Enable the following APIs:
   - Google Calendar API
   - Gmail API
   - Google Drive API
   - Google Docs API
   - Google Sheets API
   - Google Maps API
   - YouTube Data API v3
4. Create OAuth 2.0 credentials (Web application)
5. Add authorized redirect URI: `http://localhost:8001/auth/google/callback`
6. Create an API key for Google Maps
7. Add credentials to `.env` file

## 📖 Usage

### Research Mode

Ask any question and the agent will:
1. Search the web for relevant information
2. Extract content from top sources
3. Synthesize a comprehensive answer
4. Remember context for follow-up questions

Example: "What are the latest developments in AI safety research?"

### Calendar Management

Natural language calendar interactions:
- "Schedule a meeting with John tomorrow at 3pm"
- "What's on my calendar today?"
- "Find me a free 30-minute slot next week"
- "Create a daily standup at 9am Monday through Friday"

### Email Operations

- "List my unread emails from yesterday"
- "Read the email about the project proposal"
- "Send an email to john@example.com about the meeting"

### Document Management

- "Search my Drive for the quarterly report"
- "Create a new doc called 'Meeting Notes'"
- "Read the contents of my project plan doc"
- "Update the team doc by appending today's decisions"

### Location & Travel

- "How long does it take to drive from San Francisco to Los Angeles?"
- "Find coffee shops near me"
- "What are the coordinates of the Eiffel Tower?"

## 🎯 Future Agentic Goals

The roadmap focuses on transforming this from a reactive assistant into a proactive, autonomous agent that anticipates needs and takes initiative.

### Phase 1: Proactive Intelligence (Q3 2026)

**🔮 Predictive Scheduling**
- Analyze calendar patterns and suggest optimal meeting times
- Auto-detect scheduling conflicts before they happen
- Intelligent reminder timing based on travel time and traffic
- "Smart blocks" that protect focus time based on work patterns

**📊 Daily Intelligence Briefing**
- Morning summary combining calendar, emails, and relevant news
- Traffic alerts for scheduled meetings with locations
- Email priority ranking (what needs immediate attention)
- Task suggestions based on free time blocks

**🤝 Context-Aware Assistance**
- Detect when you're in a meeting and auto-silence notifications
- Suggest relevant documents before meetings
- Pre-fetch information related to upcoming events
- Draft email responses based on conversation context

### Phase 2: Autonomous Task Execution (Q4 2026)

**⚡ Background Automation**
- Auto-file emails into folders based on learned preferences
- Schedule recurring tasks without explicit instruction
- Send follow-up emails automatically after meetings
- Update shared documents with meeting notes

**🔗 Multi-Tool Workflows**
- "Plan my week": Check calendar → Find conflicts → Search for free time → Suggest rescheduling
- "Prepare for meeting": Read related emails → Pull up relevant docs → Summarize key points
- "Travel planning": Calculate route → Check traffic → Update calendar with travel time → Send ETA to attendees

**🧠 Learning & Personalization**
- Learn preferred meeting times and durations
- Adapt email response style to match your tone
- Remember document organization preferences
- Build a knowledge graph of your work relationships

### Phase 3: Advanced Agent Capabilities (2027)

**🎭 Role-Based Personas**
- Work mode: Focus on productivity, strict calendar management
- Personal mode: Flexible scheduling, entertainment recommendations
- Travel mode: Location-aware assistance, offline capabilities
- Meeting mode: Automatic note-taking and action item extraction

**🔄 Inter-Agent Collaboration**
- Coordinate with other users' agents for meeting scheduling
- Negotiate optimal times across multiple calendars
- Share context (with permission) for collaborative tasks
- Agent-to-agent communication for information gathering

**🛡️ Privacy-First Intelligence**
- Local embeddings for sensitive data
- Granular permission controls per tool
- Audit logs for all agent actions
- "Explain why" feature for every decision

**🌐 Extended Integrations**
- Slack/Teams for workplace communication
- GitHub for code and project management
- Notion/Obsidian for knowledge management
- Spotify for contextual music recommendations
- Smart home integration (control based on schedule)

**💡 Advanced Reasoning**
- Multi-step planning with subtask decomposition
- "What if" scenario simulation
- Decision trees for complex choices
- Cost-benefit analysis for time management

### Phase 4: True Autonomy (2027+)

**🤖 Self-Improvement**
- Agent analyzes its own performance metrics
- A/B tests different approaches to tasks
- Proposes new tool integrations based on usage patterns
- Identifies gaps in capabilities and suggests solutions

**🎯 Goal-Oriented Behavior**
- Set long-term goals (e.g., "Reduce meeting time by 20%")
- Agent autonomously works toward goals
- Weekly progress reports with suggestions
- Learns from successes and failures

**🌟 Emergent Capabilities**
- Discovers novel tool combinations
- Creates custom workflows without programming
- Teaches users better productivity patterns
- Becomes a true "second brain" that grows with you

## 🛠️ Adding New Tools

The architecture makes it easy to extend with new capabilities:

1. Create a new tool class inheriting from `Tool` in `backend/app/ai/tools/`
2. Implement `name`, `description`, `parameters_schema`, and `execute()` method
3. Register the tool in `backend/app/ai/tools/registry.py`
4. Update the system prompt with usage guidelines

See `backend/app/ai/tools/ADDING_TOOLS.md` for detailed instructions.

## 📊 Technology Stack

**Backend**
- FastAPI - Modern Python web framework
- OpenAI GPT-4 - Language model for reasoning
- Supabase/PostgreSQL - Database with pgvector
- Google APIs - Calendar, Gmail, Drive, Docs, Sheets, Maps, YouTube
- Tavily API - Web search and content extraction
- Pydantic - Data validation
- OAuth 2.0 - Secure authentication

**Frontend**
- React 18 - UI framework
- TypeScript - Type-safe JavaScript
- Vite - Fast build tool
- Tailwind CSS - Utility-first styling
- React Query - Server state management

**Infrastructure**
- Railway - Cloud deployment
- Supabase - Hosted PostgreSQL
- GitHub - Version control

## 🤝 Contributing

Contributions are welcome! Areas where help is needed:

- New tool integrations (Slack, Notion, GitHub, etc.)
- UI/UX improvements
- Performance optimizations
- Documentation and examples
- Testing and bug fixes

## 📝 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- OpenAI for GPT-4 API
- Anthropic for Claude API support
- Supabase for database infrastructure
- Google for comprehensive API ecosystem
- Tavily for web search capabilities

## 📧 Contact

Shiv Patel - [@shivpatel0812](https://github.com/shivpatel0812)

Project Link: [https://github.com/shivpatel0812/PersonalAIAgent](https://github.com/shivpatel0812/PersonalAIAgent)

---

**Note:** This is a personal project built for learning and experimentation with AI agents. Use responsibly and ensure you comply with all API terms of service and data privacy regulations.
