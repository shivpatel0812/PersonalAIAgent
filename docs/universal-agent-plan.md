# Universal Agent Architecture — Implementation Plan

**Last Updated**: July 7, 2025
**Status**: Planning / Not Started
**Goal**: One engine that handles email, trading, flights, shopping, etc. — without FlightAgent.py, ShoppingAgent.py, and dozens of one-off agents.

---

## 📊 Current State (What You Already Have)

You're not starting from zero. You have **two mature but separate systems**:

| Capability | Research Agent (`backend/app/ai/`) | Email Agent (`backend/app/agents/email_agent/`) |
|------------|-----------------------------------|------------------------------------------------|
| **Tool execution** | ✅ JSON loop, 25 iterations | ❌ Hardcoded pipeline |
| **Human approval** | ❌ Acts until answer | ✅ draft_ready → approved → sent |
| **Context gathering** | Memory from agent_runs | Thread, sender, calendar, attachments |
| **Learning** | Vector recall only | sender_priorities, ratings, reply events |
| **User preferences** | Per-page PAGE_CONTEXT | user_email_profiles |
| **Background jobs** | — | Async |
| **Integration pattern** | Manual registry.py list | OAuth + domain service |

**Reusable core**:
- `Tool` / `ToolRegistry` (base.py)
- Agent loop (loop.py)
- Robinhood's OAuth → MCP → dynamic Tool proxy

**Biggest gap**: No shared orchestration layer. Email has the workflow you want to generalize; research has the tool loop you want to extend.

---

## 🎯 Target Architecture

One engine with **domain-specific tools and data**, **domain-agnostic logic**:

```
backend/app/universal/
├── intent.py              # LLM: task_type, domain, entities, constraints
├── engine.py              # Runs workflow steps
├── workflows/
│   ├── schema.py          # WorkflowStep, WorkflowTemplate models
│   ├── loader.py          # Load from DB/YAML
│   └── templates/         # search_and_compare.{email,flights,shopping}.yaml
├── context/
│   ├── base.py            # ContextProvider ABC
│   ├── registry.py        # domain → providers
│   └── providers/         # email, user_profile, memory, integrations
├── approval/
│   └── policies.py        # requires_approval(tool, action)
├── learning/
│   ├── feedback.py        # Record choice → update prefs
│   └── patterns.py        # Cross-domain trait detection
├── profile/
│   └── unified.py         # global + domain_preferences JSON
└── tools/
    ├── discovery.py       # Auto-register by user connections
    └── mcp_bridge.py      # Generic MCP → Tool (extract from Robinhood)
```

**Principle**: Email agent becomes the first workflow implementation, not a separate architecture. Research agent becomes a workflow (task_type: research, domain: general).

---

## 📋 Prerequisites Before Starting

**Recommended before Phase 1:**

### ✅ Prerequisite #1: Email Agent Test Coverage
**Why needed**: Safety net before touching email internals
**What to do**:
- Test sender intelligence lookup
- Test draft generation
- Test thread matching
- Test calendar integration

**Timeline**: 3 days
**Impact**: Prevents breaking production email during migration

### ✅ Prerequisite #2: Two Working Approval Workflows
**Why needed**: Can't extract universal pattern from one example
**What to do**: Have 2 domains with complete workflows (context → generate → approve → learn)

**Current state**:
- ✅ Email: Complete workflow
- ⚠️ Research/Tools: No approval workflow yet

**Options**:
- Add approval to existing research agent for dangerous tools
- Build second simple domain (weather, reminders, etc.) with approval
- Or accept extracting from email only (riskier)

**Timeline**: 1-2 weeks
**Impact**: Without two examples, abstraction might not fit new domains

---

## 🚀 Recommended Phasing (Modified from Original)

### **Phase 0: Prove the Pattern** ⚠️ **START HERE**
**Timeline**: 2-3 weeks
**Goal**: Validate universal architecture works before migrating email

#### Week 1-2: Build Tiny Universal Proof
**Pick simplest possible domain** (NOT email, trading, or flights):

**Option A: Weather Reminders** (recommended)
- [ ] Build one YAML workflow: `monitor.weather.yaml`
- [ ] Build minimal `UniversalEngine` that only handles this workflow
- [ ] Test: "Remind me if it rains tomorrow" → queues notification
- [ ] Compare: Lines of code vs specialized implementation

**Option B: Daily Digest**
- [ ] Build workflow: `summarize.news.yaml`
- [ ] Test: "Summarize tech news daily at 9am" → scheduled job
- [ ] Compare: Complexity vs cron + script

**Option C: Simple Automation**
- [ ] Build workflow: `track.package.yaml`
- [ ] Test: "Track my Amazon order" → monitors status
- [ ] Compare: Universal vs dedicated tracker

**Deliverable**: Working proof-of-concept with low stakes domain

#### Week 3: Evaluate & Decide
**Measure**:
- Lines of code: Universal engine + YAML vs specialized script
- Development time: How long did it take?
- Debuggability: Was it easier or harder to understand?
- Extensibility: Would adding domain #2 be easier?

**Go/No-Go Decision**:
- ✅ **GO**: Universal is clearly simpler → Proceed to Phase 1
- ❌ **NO-GO**: Specialized is fine → Keep domain-specific code, no universal migration

---

### **Phase 1: Extract Universal Primitives** ⚠️ **Only if Phase 0 = GO**
**Timeline**: 6 weeks (realistic, not 2-3)
**Goal**: Pull shared pieces from email into universal, have email call them

#### 1.1 Intent Extraction
**New**: `backend/app/universal/intent.py`

```python
class TaskIntent(BaseModel):
    task_type: str   # search_and_compare | draft_and_send | monitor | execute
    domain: str      # email | flights | shopping | trading
    entities: dict   # Extracted from user input
    constraints: dict
    raw_input: str
```

**Reuse from email**:
- `drafter.classify_needs_reply()` already does intent detection
- `scheduling.detect_scheduling()` extracts entities
- Consolidate into one LLM call with shared JSON schema

**Wire in**:
- Chat input on ConversationPage
- Email scan (optional enrichment)

**Timeline**: 3 days (LLM prompts need iteration)

---

#### 1.2 Workflow Schema + Loader
**New**: `backend/app/universal/workflows/`

Store workflows as **data**, not Python:

```yaml
# workflows/templates/search_and_compare.email.yaml
task_type: search_and_compare
domain: email
steps:
  - type: extract_parameters
  - type: gather_context
    providers: [email_thread, sender_intelligence, user_profile, calendar]
  - type: generate_draft
  - type: queue_for_review
    format: email_draft
  - type: learn_from_choice
    on: approved
    update: [sender_priorities, domain_preferences.email]
```

**Map email pipeline → steps**:

| Email today (service.py) | Universal step |
|-------------------------|----------------|
| `scan_for_reply_candidates()` | discover + filter |
| `_build_draft_prompt_context()` | gather_context |
| `generate_initial_draft()` | generate |
| `adjust_item_draft()` | refine (chat loop) |
| `approve_and_send_item()` | execute + learn_from_choice |

**Migration**: Email `service.py` keeps public API; internals call `UniversalEngine.run_workflow("email", intent)`.

**Timeline**: 4 days (schema design, loader, validator)

---

#### 1.3 Context Provider System
**New**: `backend/app/universal/context/`

Extract from email into **pluggable providers**:

| Provider | Source today | File to extract from |
|----------|-------------|---------------------|
| `EmailThreadProvider` | `fetch_item_conversation()` | mail_context.py |
| `SenderIntelligenceProvider` | `get_sender_context()` | sender_intelligence.py |
| `UserProfileProvider` | `get_profile_block_with_defaults()` | user_profile.py |
| `CalendarProvider` | `build_calendar_availability_block()` | scheduling.py |
| `MemoryProvider` | `find_related_runs()` | memory.py |
| `IntegrationProvider` | OAuth connection status | *_connections DB modules |

```python
class ContextProvider(ABC):
    domain: str
    async def gather(self, intent: TaskIntent, state: WorkflowState) -> dict: ...
```

Engine calls `gather_context` by listing providers for the workflow step — same pattern as tool registry.

**Timeline**: 5 days (testing each one, edge cases)

---

#### 1.4 Generic Approval Queue
**New**: `supabase/migrations/017_universal_actions.sql`

```sql
CREATE TABLE universal_actions (
  id UUID PRIMARY KEY,
  user_id TEXT NOT NULL,
  domain TEXT NOT NULL,           -- email | trading | flights
  task_type TEXT NOT NULL,        -- search_and_compare | draft_and_send
  status TEXT NOT NULL,           -- pending_review | approved | rejected | executed | expired
  payload JSONB NOT NULL,         -- domain-specific (draft, flight options, trade order)
  format TEXT,                    -- UI renderer key
  workflow_id TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  executed_at TIMESTAMPTZ
);
```

**New**: `backend/app/universal/approval/queue.py`

**Reuse UI pattern from**: `EmailAgentPanel.tsx` — three columns (queue / detail / chat).

**Email migration**: `email_agent_items` stays for now; add adapter `EmailActionAdapter` that reads/writes both tables, OR migrate items → universal_actions with domain: email.

**Timeline**: 2 days (migration + adapter)

---

#### 1.5 Unified User Profile
**New**: `supabase/migrations/018_user_profiles.sql`

```jsonc
{
  "global_preferences": {
    "price_sensitivity": "medium",
    "timezone": "America/Los_Angeles"
  },
  "domain_preferences": {
    "email": { /* from user_email_profiles */ },
    "trading": { "avoid": ["crypto"], "hold_period": "long-term" }
  },
  "cross_domain_patterns": {
    "values_time_over_money": 0.8,  // Learned from choices
    "prefers_quality": 0.9
  }
}
```

**Migration**: `user_email_profiles` → `domain_preferences.email`; keep old table + sync during transition.

**Timeline**: 3 days (data migration is always slow)

---

#### 1.6 Learning Loop
**New**: `backend/app/universal/learning/feedback.py`

| Event | Today | Universal |
|-------|-------|-----------|
| Email approved/sent | `email_events` | `record_feedback(domain, choice, alternatives)` |
| Digest star rating | `email_ratings` → RPC | Same RPC, called via learning module |
| Draft chat adjust | Not persisted | Store as negative/partial signal |
| Research "helpful?" | Missing | Add thumbs on chat messages |

**Cross-domain**: `patterns.py` runs nightly job — if user picks non-stop flights + fast shipping + urgent email replies → bump `values_time_over_money`.

**Timeline**: 3 days (patterns detection is subtle)

---

### **Phase 1 Deliverables**

- [ ] `UniversalEngine` runs email workflow end-to-end (parity with current behavior)
- [ ] `EmailAgentPanel` unchanged externally (adapter layer)
- [ ] Intent + context providers tested in isolation
- [ ] `universal_actions` table + basic API routes

**Total Timeline**: 20 days (~4 weeks) + 2 weeks integration/debugging = **6 weeks**

---

### **Phase 2: Unify Research Agent + Approval Policies**
**Timeline**: 2 weeks
**Goal**: Research agent respects approval for dangerous tools

#### 2.1 Tool Metadata
Extend `Tool` in `base.py`:

```python
class Tool(ABC):
    domain: str = "general"
    side_effect: bool = False      # mutates external state
    requires_approval: bool = False
    risk_level: Literal["read", "write", "financial"] = "read"
```

Tag existing tools:
- Gmail send = `requires_approval=True`
- Web search = `requires_approval=False`
- Robinhood place_order = `requires_approval=True, risk_level="financial"`

---

#### 2.2 Approval-Aware Loop
**Modify**: `backend/app/ai/agent/loop.py`

When LLM picks a tool with `requires_approval`:

1. Don't execute immediately
2. Create `universal_actions` row with proposed params
3. Return to user: "I prepared X — approve?"
4. On approval → resume loop with pre-approved execution

Email already does this outside the loop — now it's one mechanism.

---

#### 2.3 Tool Discovery (Replace Manual Registry)
**New**: `backend/app/universal/tools/discovery.py`

```python
def build_registry(user_id, intent: TaskIntent) -> ToolRegistry:
    registry = ToolRegistry()
    register_core_tools(registry)                    # search, scrape, answer
    for conn in get_user_connections(user_id):
        registry.merge(tools_for_connection(conn))  # google, robinhood, ...
    registry.merge(load_tools_for_domain(intent.domain))
    return registry
```

**Shrink**: `registry.py` from 200-line manual list → discovery + domain manifests.

---

#### 2.4 Generic MCP Bridge
**Extract from**: `mcp/manager.py` + `robinhood_tool.py`

```python
class MCPBridge:
    def __init__(self, server_config: MCPServerConfig): ...
    def discover_tools(self) -> list[Tool]: ...
    def call(self, name, args): ...
```

Robinhood becomes **config**:

```yaml
mcp_servers:
  robinhood:
    url: agent.robinhood.com/mcp/trading
    connection_table: robinhood_connections
    tool_prefix: robinhood_
```

---

### **Phase 2 Deliverables**

- [ ] Research chat can propose calendar events / emails / trades → approval queue
- [ ] `get_tool_registry()` replaced by `build_registry(user_id, intent)`
- [ ] One `ApprovalPanel` component (email is first format renderer)

---

### **Phase 3: Prove Generalization — Second Domain**
**Timeline**: 2 weeks
**Goal**: Second domain works through UniversalEngine

#### Option A: Trading ⚠️ (Lower lift, but risky)
You already have tools. Add workflow:

```yaml
task_type: analyze_and_execute
domain: trading
steps:
  - extract_parameters      # ticker, action, amount
  - gather_context          # portfolio (MCP), user trading prefs
  - analyze                 # robinhood_* tools
  - rank                    # risk-adjusted scoring using cross_domain_patterns
  - queue_for_review        # show order preview
  - learn_from_choice       # update domain_preferences.trading
```

**New files**:
- `workflows/templates/analyze_and_execute.trading.yaml`
- `TradingActionRenderer.tsx` (or extend RobinhoodPanel)

**Test**: "Should I buy more AAPL?" → analysis → optional order queued for approval.

---

#### Option B: Flights ✅ (Proves true new domain - RECOMMENDED)
- Register tools: `search_flights` (SerpAPI/Google Flights), `track_flight_price`
- Workflow template (same 7-step structure)
- `domain_preferences.flights` in unified profile
- `FlightsActionRenderer.tsx` — ranked options card

**Success criterion**: Adding flights = 1 YAML + 2 tool files + 1 UI renderer, no agent class.

---

### **Phase 3 Deliverables**

- [ ] Second domain works through UniversalEngine
- [ ] Time to add domain measured: target **< 1 day** after Phase 3
- [ ] Cross-domain pattern influences ranking (e.g. `prefers_quality` affects flight filters)

---

### **Phase 4: Self-Extending Workflows** 🔮 (Later)
**Only after Phases 1–3 are stable.**

When `(task_type, domain)` has no template:

1. LLM proposes workflow from similar templates (`search_and_compare.*`)
2. User sees proposed steps → confirm
3. Store in `workflow_templates` table (versioned)
4. Reuse on similar requests

**Guardrails**:
- New workflows can only use registered tools
- Execute steps always require approval for `side_effect` tools

**Example**: "Find a tax accountant in SF" → agent clones `search_and_compare.restaurants` pattern, swaps tools to Yelp/Google Places.

---

## 🎨 Frontend Plan

| Component | Action |
|-----------|--------|
| `ConversationPage.tsx` | Default shell; route by `intent.domain` |
| `EmailAgentPanel.tsx` | Becomes `format=email_draft` renderer over `universal_actions` |
| **New** `ApprovalQueue.tsx` | Generic sidebar: queued actions across domains |
| **New** `ActionRenderer.tsx` | Switch on `action.format` → Email / Trading / Flights / Generic |
| `RobinhoodPanel.tsx` | Connection management only; actions move to approval queue |
| Chat (`useConversation.ts`) | Resume loop after approval via `action_id` |

**UX goal**: One "Personal" page with tabs or smart routing — not a new panel per domain.

---

## 💾 Database Migrations (Ordered)

| Migration | Purpose |
|-----------|---------|
| `017_universal_actions.sql` | Approval queue |
| `018_user_profiles.sql` | Unified profile (JSONB) |
| `019_workflow_templates.sql` | Stored workflows |
| `020_feedback_events.sql` | Structured learning events |
| `021_cross_domain_patterns.sql` | Computed traits (or JSONB on profile) |

**Keep existing tables during migration**; use adapters, not big-bang rewrites.

---

## 🚫 What NOT to Build Yet

- ❌ Self-writing workflows (Phase 4) — too early
- ❌ Shopping scrapers / visual similarity — prove pattern with trading or flights first
- ❌ Full multi-user auth — fix `user_id = "default"` incrementally when you add auth
- ❌ Replacing email agent UI — adapter first, migrate later
- ❌ 100 domains — ever

---

## 📅 Recommended Build Order (First 3 Weeks)

### **Week 1-2: Phase 0 - Build Proof**
- [ ] Pick simplest domain (weather, news digest, or package tracking)
- [ ] Build minimal `UniversalEngine` for that domain only
- [ ] Build one YAML workflow template
- [ ] Test: Does YAML workflow simplify or complicate?
- [ ] Measure: Lines of code vs specialized implementation

### **Week 3: Evaluate & Decide**
- [ ] Compare: Universal vs specialized complexity
- [ ] Measure: Development time
- [ ] Ask: Would adding domain #2 be easier with universal?
- [ ] **Go/No-Go Decision**: Proceed to Phase 1 or keep specialized?

### **Week 4+ (Optional): Prerequisites Before Phase 1**
**Only if Go decision from Week 3:**
- [ ] Write email agent tests (safety net before migration)
- [ ] Optional: Build second simple domain to prove pattern
- [ ] Document rollback plan if email breaks

### **Week 5+: Phase 1 (Only if Go)**
- [ ] Week 1: `intent.py` + workflow schema + email workflow YAML
- [ ] Week 2: ContextProvider extraction (4 email providers)
- [ ] Week 3: `universal_actions` migration + API
- [ ] Week 4: UniversalEngine + email adapter
- [ ] Week 5-6: Integration, testing, debugging

---

## ✅ Success Criteria (Measurable)

| Criterion | How You'll Know |
|-----------|-----------------|
| New domain < 1 day | Trading or flights added with YAML + tools only |
| Cross-domain learning | `values_time_over_money` changes flight + email ranking |
| Any request works | "Find ergonomic chair" uses `search_and_compare` with web tools |
| Gets smarter | Approval choices shift `domain_preferences` within 5 interactions |

---

## 🔑 Key Design Decisions to Make Now

1. **Email migration strategy**:
   - **Adapter** (safer, recommended) vs
   - **Migrate** `email_agent_items` → `universal_actions` (cleaner, riskier)
   - **Decision**: Adapter first

2. **Workflow storage**:
   - **Git YAML** (git-reviewed, recommended for Phase 1-3) vs
   - **Database** (agent-writable in Phase 4)
   - **Decision**: Start YAML, move to DB in Phase 4

3. **Second proof domain**:
   - **Trading** (fast, already integrated) vs
   - **Flights** (cleaner generalization story)
   - **Decision**: Flights first for proof (safer than trading with real money)

4. **Chat vs background**:
   - Email scans stay scheduled
   - Chat triggers on-demand workflows
   - Both use same engine

---

## ⚠️ Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Email regression during migration | **High** | **Critical** | Tests + adapter + rollback plan |
| Universal system is slower | Medium | High | Build in parallel, compare perf |
| Takes 3x longer than estimated | **High** | Medium | Cut scope or triple estimates |
| Abandon mid-way (sunk cost) | Medium | High | Phase 0 proves value first |
| Trading without approval during dev | **High** | **Critical** | Fix in Phase 0, dry-run mode |
| Over-abstraction (harder to debug) | Medium | Medium | Measure complexity, compare to specialized |

---

## 🎯 Bottom Line

You're not building a new agent — you're **extracting the pattern email already proves** (context → generate → approve → learn) into `backend/app/universal/`, then teaching the research loop to respect approval, then adding domains as config.

**The email agent is your reference implementation.**
**Robinhood is your integration template.**
**The research loop is your execution runtime.**

Merge those three and you get the Jarvis architecture.

---

## 🚦 Start Here

**If you want to begin implementation**:

1. ✅ **Phase 0** (Week 1-2): Build simple proof domain (weather, news digest, or package tracking)
2. ✅ **Evaluate** (Week 3): Is universal simpler than specialized? Go/No-Go decision
3. ⚠️ **Phase 1** (Only if Go): Extract universal primitives (6 weeks)
4. ⚠️ **Phase 2** (If Phase 1 works): Add approval policies (2 weeks)
5. ⚠️ **Phase 3** (If Phase 2 works): Second domain proof (2 weeks)

**Highest-leverage first slice**: Phase 0 with simplest domain — proves the concept before touching email.

**Alternative**: Skip universal, keep specialized agents for each domain. That's totally fine too!

---

## 📝 Change Log

| Date | Author | Changes |
|------|--------|---------|
| 2025-07-07 | Initial | Created plan based on terminal session |
| 2025-07-07 | Claude Review | Added Phase 0, risk register, realistic timelines, prerequisites |

---

## 🚨 Known Issues (Domain-Specific, Not Universal Architecture)

These are current problems with specific domains that should be fixed independently:

### ⚠️ Issue #1: Research Agent - No Approval for Dangerous Tools
**Domain**: Research/Chat agent
**Problem**: Tools like `send_email`, `create_calendar_event` execute immediately
**Impact**: Could send unwanted emails or modify calendar without permission
**Fix**: Add tool metadata (`requires_approval=True`) and hook into approval queue
**Status**: Blocking Phase 2 (approval-aware loop)

### ⚠️ Issue #2: Robinhood - No Trade Approval
**Domain**: Trading/Robinhood integration
**Problem**: `robinhood_place_order` executes real trades without confirmation
**Impact**: Could place wrong orders, lose money
**Fix**: Build approval workflow (queue → review → approve → execute)
**Status**: Should fix before using as Phase 3 proof domain
**Note**: This is NOT a blocker for Phase 0-1 (universal architecture is domain-agnostic)

### ⚠️ Issue #3: Email Recap - Just Improved
**Domain**: Email recap/digest
**Problem**: Summaries were vague, duplicates appeared
**Fix**: ✅ COMPLETED (July 7, 2025) - Enhanced summaries, deduplication, sender intelligence
**Status**: Ready to use as reference implementation

---

## 📎 Related Documents

- [Session Summary](./2025-07-07-session-summary.md) - Full context from planning session
- [Robinhood Integration Analysis](./2025-07-07-session-summary.md#3-robinhood-mcp-integration-analysis) - Current state
- [Email Agent Context Analysis](./2025-07-07-session-summary.md#1-email-agent-context-analysis) - Reference implementation
