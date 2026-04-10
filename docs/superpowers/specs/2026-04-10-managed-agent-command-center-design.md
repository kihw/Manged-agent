# Managed Agent Command Center Design

Date: 2026-04-10
Status: Proposed and user-approved at the design level

## Goal

Redesign the current dashboard into a Windows-friendly SPA that combines:

- a clear executive cockpit for global monitoring
- a production workspace for launching and following tasks
- progressive disclosure for technical investigation

The product should feel like a daily command center rather than an internal admin screen. The interface must stay calm and readable at first glance, while still exposing deep operational detail on demand.

## Product Direction

The chosen direction is a hybrid `Command Center`:

- the top of the app is a stable monitoring surface
- the center of the app is a work queue for the active project
- technical detail is hidden behind drawers, collapses, bottom panels, and modals

This intentionally avoids a fully fixed dashboard layout. The UI should prioritize what matters now and reveal the rest only when the operator asks for it.

## Constraints

- Windows desktop distribution remains the primary target
- the first release should work with the current backend capabilities
- project organization is a UI-level grouping for now, derived from `workspace_path` and orchestration metadata
- the current API is instance-centric for run creation, so the UI can become a strong control surface before the backend becomes a full operator control plane

## Information Hierarchy

The SPA is organized in three levels:

### Level 1: Always Visible

These elements stay visible or easy to regain at all times:

- top application bar
- executive status strip
- active project context
- main work queue
- urgent action column

The level 1 goal is reassurance and orientation. A user should understand system health in seconds.

### Level 2: Contextual and Actionable

These elements appear when a run, approval, workflow, or error is selected:

- run drawer
- project-specific filters
- action buttons for relaunch, approve, deny, inspect
- short investigation summaries

The level 2 goal is fast decision-making without navigating away from the main screen.

### Level 3: Hidden Until Requested

These elements are collapsed or otherwise secondary:

- raw event payloads
- full tool execution detail
- workflow signatures
- long error samples
- policy metadata
- low-priority diagnostics

The level 3 goal is to keep the interface clean while preserving technical depth.

## Target Layout

### 1. Top Bar

The top bar is sticky and always visible. It contains:

- project switcher
- quick search
- local runtime state
- LAN exposure state when enabled
- health indicator
- primary `New Task` action

This bar anchors the app and prevents disorientation during navigation.

### 2. Executive Strip

Directly below the top bar is a compact executive strip with fixed metrics:

- active runs
- blocked runs
- pending approvals
- recent errors
- connected agents

Each metric acts as both summary and navigation shortcut. Clicking a tile applies a focused view in the workspace below.

### 3. Project Rail

A collapsible left rail shows derived projects. Each project entry includes:

- project name derived from workspace or orchestration grouping
- active run count
- blocked count
- approval count
- error badge when needed

The rail is collapsible because it is useful but not always primary.

### 4. Main Workspace

The center of the app is the main operational surface. It is permanently visible and grouped by project and status.

Default sections:

- `In Progress`
- `Blocked`
- `Needs Attention`
- `Recently Completed`

Each run appears as a compact card with:

- task title
- orchestration name or identifier
- current step when known
- last meaningful update
- badges for approval, error, workflow recurrence, and status
- quick actions when allowed

### 5. Urgent Action Column

A right-side column stays visible on desktop. It contains:

- pending approvals
- critical errors
- recent blocked runs
- launch and relaunch shortcuts

This area is intentionally narrow and high-signal. It surfaces the next thing the operator should decide.

## Hidden and Revealed Panels

### Run Drawer

A right drawer opens when a run is selected. It replaces full-page detail navigation as the default interaction.

The drawer shows:

- run summary
- orchestration
- instance
- step progress
- current status
- linked workflow fingerprint
- recent tool activity
- pending or resolved policy decisions

### Bottom Investigation Panel

A bottom panel opens from the run drawer or workspace. It supports deeper analysis while preserving main context.

Tabs:

- timeline
- tool executions
- policy decisions
- errors
- raw events

The bottom panel should be resizable and closable. It is not open by default.

### Launch Modal

Launching a task is handled in a modal rather than a separate page.

Fields:

- project
- orchestration
- title
- goal
- workspace
- trigger

If the backend still requires an instance identity, the UI must either:

- use the active registered Windows instance context
- or clearly explain that launch is limited to the local registered desktop instance in V1

### Approval Modal

Approvals should not force a navigation change. The modal includes:

- action requested
- reason
- target
- run context
- approve and deny actions
- optional comment

### Collapsible Sections

The following sections should be collapsed by default:

- raw payloads
- long event tables
- full tool inputs and outputs
- historical diagnostics
- extended workflow signatures

## Exact User Flows

### Launch

1. The user clicks `New Task`
2. The launch modal opens with the active project preselected
3. The user chooses orchestration and fills title, goal, workspace, and trigger
4. Submission creates the run
5. The run appears immediately in `In Progress`
6. The UI opens the run drawer automatically or offers a `View Run` transition

### Follow

1. The user watches the main workspace and executive strip
2. Selecting a run opens the run drawer
3. The drawer shows the current step, summary, and recent activity
4. If deeper detail is needed, the user opens the bottom investigation panel
5. The app refreshes via polling in V1

### Approve

1. A pending approval appears in the urgent action column and on the affected run card
2. The user opens the approval modal
3. The modal shows the requested action and reason with minimal but sufficient context
4. The user approves or denies
5. The run state updates in place without losing surrounding context

### Investigate

1. The user clicks a run, error badge, or workflow badge
2. The run drawer opens on the relevant context
3. The user progressively reveals:
   - summary
   - errors
   - tools
   - decisions
   - raw events
4. The user can pivot to similar runs, related workflow fingerprints, or the error category view
5. The user closes the drawer or investigation panel and returns to the main queue instantly

## Component Model

The SPA should be built around a small number of durable components:

- `AppShell`
- `TopBar`
- `ExecutiveStrip`
- `ProjectRail`
- `RunWorkspace`
- `RunCard`
- `UrgentActionPanel`
- `RunDrawer`
- `InvestigationPanel`
- `LaunchTaskModal`
- `ApprovalModal`
- `FilterBar`

These components should separate visual structure from data access so the UI can evolve without repeatedly rewriting the shell.

## Data Model Mapping for V1

The first implementation should map the existing backend to the SPA without inventing unsupported concepts.

Available now:

- runs
- tasks
- instances
- orchestrations
- policy decisions
- workflow fingerprints
- error summaries and details
- dashboard overview metrics

Derived in UI for V1:

- project grouping from `workspace_path`
- project labels from orchestration naming and workspace patterns
- urgency ranking from status plus approval/error presence

Not yet first-class in the backend:

- project entity
- operator-owned run queue
- native relaunch action
- native real-time stream

## Technical Architecture

The new UI should move from server-rendered templates toward a packaged SPA.

V1 frontend architecture:

- SPA shell with client-side routing
- API data loading from existing `/v1` endpoints
- polling-based refresh for changing operational data
- desktop-friendly responsive layout optimized for laptop and desktop Windows use

Backend changes needed to support the SPA shell:

- static asset serving for built frontend files
- a clean SPA entry route
- compatibility with existing desktop packaging

## Error Handling and Empty States

The UI should actively reduce operator stress.

Required states:

- empty project
- no runs yet
- no approvals pending
- backend unavailable
- stale or disconnected local runtime
- invalid launch form
- missing run detail or deleted context

Principles:

- keep messages plain and non-alarming
- always offer the next sensible action
- never dump raw technical detail unless the user expands it

## Testing Expectations

The implementation plan should include:

- frontend component tests for drawer, modal, collapse, and filter behavior
- integration tests for launch, approval, and investigation flows
- API contract verification for data used by the SPA
- Windows desktop smoke validation that the packaged app still launches and serves the SPA correctly

## Scope Boundaries

Included in the first SPA redesign:

- hybrid command center shell
- project grouping in UI
- cockpit plus workspace plus hidden investigation surfaces
- launch, follow, approve, and investigate flows using current backend limits

Deferred to later backend evolution:

- first-class projects
- real queue ownership and assignment
- native relaunch endpoint
- WebSocket or SSE live updates
- richer operator scheduling and routing controls

## Recommended Implementation Order

1. Serve a packaged SPA shell from the Windows app
2. Build the application layout and navigation model
3. Implement the executive strip, project rail, workspace, and urgent action panel
4. Implement run drawer and investigation panel
5. Implement launch and approval modals
6. Add polling, loading states, and derived project grouping
7. Add higher-fidelity workflows such as relaunch and cross-run pivots

## Decision Summary

The target UI is not a prettier dashboard. It is a layered operational workspace:

- calm at first glance
- powerful at selection time
- technical only when expanded

That shape is both desirable for the product and feasible with the current system, as long as the first release accepts the current backend limits and treats true operator control as a second phase.
