# Claude Costs Enhancement TODO

This file tracks potential enhancements to the claude-costs.py script based on analysis of Claude Code v1.0.21 metadata.

## High Priority Enhancements

### 1. Response Time Analysis (`durationMs`, `ttftMs`)
**Context**: JSONL entries now include `durationMs` (total request time) and sometimes `ttftMs` (time to first token).
**Implementation**: 
- Add performance metrics to the main summary table
- Show average/median response times by model
- Track slowest requests and identify patterns
- Create sparkline charts for response time trends over time
**Files to modify**: claude-costs.py (add to `parse_jsonl_files()` and display functions)
**Data location**: `message.durationMs`, `message.ttftMs` in JSONL entries

### 2. Session Analysis (`sessionId`, `parentUuid`)
**Context**: Each conversation has a `sessionId` and messages are threaded via `parentUuid`.
**Implementation**:
- Track conversation lengths (number of messages per session)
- Calculate cost per conversation session
- Identify longest/most expensive conversations
- Show session-based usage patterns (short vs long conversations)
**Files to modify**: claude-costs.py (enhance data collection and add session-based reporting)
**Data location**: `sessionId`, `parentUuid` fields in JSONL entries

### 3. Request Success Rate Analysis
**Context**: Some entries have `isApiErrorMessage: true` or error content, others are successful.
**Implementation**:
- Track success vs error rates by model and time period
- Calculate cost of failed requests (still charged for tokens)
- Identify error patterns and common failure modes
- Show reliability metrics alongside cost metrics
**Files to modify**: claude-costs.py (add error detection in `parse_jsonl_files()`)
**Data location**: `isApiErrorMessage` field, `message.content` error patterns

## Medium Priority Enhancements

### 4. Todo Completion Tracking
**Context**: `~/.claude/todos/` contains JSON files tracking task completion across projects.
**Implementation**:
- Parse todo JSON files to track productivity metrics
- Calculate task completion rates over time
- Correlate todo activity with Claude usage costs
- Show productivity ROI (tasks completed per dollar spent)
**Files to create**: New function to parse `~/.claude/todos/*.json`
**Data location**: `~/.claude/todos/` directory with JSON files containing task arrays

### 5. Tool Usage Pattern Analysis
**Context**: Can analyze bash commands in JSONL and permissions in `settings.local.json`.
**Implementation**:
- Track which tools/commands are used most frequently
- Correlate tool usage with costs and response times
- Identify expensive tool usage patterns
- Show development workflow insights
**Files to modify**: claude-costs.py (analyze `message.content` for tool usage patterns)
**Data location**: Tool usage in message content, permissions in `~/.claude/settings.local.json`

### 6. Model Switching Pattern Analysis
**Context**: `settings.json` tracks current model, JSONL shows historical model usage.
**Implementation**:
- Track when users switch between models (Opus 4, Sonnet 4, etc.)
- Calculate cost impact of model choices
- Show model usage patterns and preferences over time
- Recommend optimal model selection based on usage patterns
**Files to modify**: claude-costs.py (track model changes over time)
**Data location**: `message.model` in JSONL, current model in `~/.claude/settings.json`

## Low Priority But Interesting

### 7. IDE vs CLI Usage Tracking
**Context**: `~/.claude/ide/*.lock` files show active IDE integrations.
**Implementation**:
- Detect when IDE integrations are active vs pure CLI usage
- Compare costs and usage patterns between IDE and CLI
- Track productivity differences between interfaces
**Files to analyze**: `~/.claude/ide/*.lock` files for timestamps and PID tracking
**Data location**: Lock files in `~/.claude/ide/` directory

### 8. Feature Flag and A/B Test Analysis
**Context**: `~/.claude/statsig/` contains feature flag evaluations and experimental feature usage.
**Implementation**:
- Show which experimental features are enabled
- Track usage of beta features and their impact on costs
- Analyze A/B test participation and outcomes
**Files to analyze**: `~/.claude/statsig/statsig.cached.evaluations.*` files
**Data location**: Statsig cache files contain feature flag states

### 9. Cache Efficiency Deep Dive
**Context**: Current script shows cache savings, but could provide more detailed analysis.
**Implementation**:
- Track cache hit/miss rates over time
- Show which projects/sessions benefit most from caching
- Identify optimal conversation patterns for cache efficiency
- Calculate cache ROI (savings per conversation)
**Files to modify**: claude-costs.py (enhance existing cache analysis)
**Data location**: `cache_read_input_tokens`, `cache_creation_input_tokens` in usage objects

## Implementation Notes

### Version Tracking Enhancement
**Current**: Script tracks Claude Code version from JSONL
**Enhancement**: Compare features/costs across Claude Code versions (currently seeing 0.2.x, 1.0.x versions)
**Implementation**: Add version-based analysis to show how usage patterns change with Claude Code updates

### Data Structure Changes Needed
For most enhancements, the main data collection loop in `parse_jsonl_files()` will need to collect additional fields:
```python
# New fields to collect per entry:
entry_data = {
    'duration_ms': data.get('durationMs'),
    'ttft_ms': data.get('message', {}).get('ttftMs'),
    'session_id': data.get('sessionId'),
    'parent_uuid': data.get('parentUuid'),
    'is_error': data.get('isApiErrorMessage', False),
    'request_id': data.get('requestId'),
    'is_sidechain': data.get('isSidechain', False),
}
```

### Display Enhancements
Most features will need new display functions similar to existing sparkline/bar chart functions:
- `show_performance_metrics()`
- `show_session_analysis()`
- `show_error_rates()`
- `show_todo_productivity()`

### Configuration Options
Add command-line flags for new analyses:
- `--performance` / `-p`: Show response time analysis
- `--sessions` / `-s`: Show session-based analysis  
- `--errors` / `-e`: Show error rate analysis
- `--todos` / `-t`: Show todo/productivity analysis
- `--tools` / `--tool-usage`: Show tool usage patterns