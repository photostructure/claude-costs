# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Key Commands

- **Run the script**: `./claude-costs.py` (script is already executable)
- **Run with different options**: `./claude-costs.py -d 7` (analyze last 7 days), `./claude-costs.py -v` (verbose mode)
- **Dependencies**: Automatically installed via `uv` on first run (requires Python 3.9+)

## Code Architecture

This is a single-file Python CLI application that analyzes Claude Code usage costs from local metadata files:

- **Data Source**: Reads `.jsonl` files from `~/.claude/projects/` containing usage metadata
- **Cost Calculation**: Uses hardcoded pricing tables for different Claude models with cache discounts
- **Main Components**:
  - `parse_jsonl_files()`: Extracts usage data from JSONL files, handles both legacy `costUSD` and new token-based formats
  - `calculate_token_cost()`: Computes actual costs with cache savings based on model pricing
  - Display functions create sparklines and bar charts for activity visualization

## Important Notes

- The script relies on undocumented Claude Code file structures that may break without warning
- Pricing is hardcoded in the `PRICING` dictionary and needs manual updates when Claude pricing changes
- Uses `uv` script runner with inline dependencies (rich, typer) - no separate requirements file

## Claude Code Directory Structure Research (June 2025)

### ~/.claude Directory Layout
- **`/ide/`** - IDE integration lock files tracking active connections
- **`/local/`** - Claude Code installation (node_modules, ripgrep binaries)
- **`/projects/`** - Project conversation logs as .jsonl files
- **`/statsig/`** - Analytics and evaluation caches
- **`/todos/`** - Todo list JSON files for task tracking
- **`/.claude/`** - Local settings and permissions

### JSONL Format Evolution
Current format (v1.0.19) includes:
- `message` - Full Claude message with content and usage stats
- `sessionId` - Unique session identifier
- `timestamp` - ISO timestamp
- `version` - Claude Code version
- `userType` - "external" for CLI users
- `cwd` - Current working directory

### Token Usage Tracking
Usage objects contain these fields:
- `input_tokens` - Regular input tokens
- `output_tokens` - Generated output tokens  
- `cache_creation_input_tokens` - Tokens for cache writes (25% premium)
- `cache_read_input_tokens` - Cached tokens (90% discount)
- `service_tier` - Usually "standard"

**Note**: Thinking tokens are NOT currently tracked separately in Claude Code v1.0.19, despite models like Opus 4 using internal reasoning.