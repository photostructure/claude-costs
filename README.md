# Claude Costs Calculator

A Python script to analyze Claude Code usage costs and statistics from local metadata files.

## Features

- 💰 **Cost Analysis**: Shows actual costs with cache savings
- 📊 **Session Statistics**: Sessions per day, cost per session, active days
- 🔤 **Token Usage**: Total tokens with cache efficiency breakdown
- 📈 **Project Breakdown**: Detailed costs and usage by project
- 📉 **Activity Patterns**: Hourly and daily usage visualizations
- ✅ **Tool Use Stats**: Acceptance, modification, and interruption rates

## ⚠️ Caution

This script relies on **undocumented and unsupported** file structures used by Claude Code. It works as of Claude Code v1.0.18, but expect it to break at any time in the future without warning as Anthropic may change these internal file formats without notice.

## Installation

1. [Install `uv`](https://docs.astral.sh/uv/getting-started/installation/)

2. Make the script executable and run:

```bash
chmod +x claude-costs.py
./claude-costs.py
```

Dependencies will be automatically installed on first run.

## Usage

```bash
# Analyze last 30 days (default)
./claude-costs.py

# Analyze last 7 days
./claude-costs.py -d 7

# Show all projects (not just top 10)
./claude-costs.py -v

# Use a different Claude directory
./claude-costs.py -c ~/backup/.claude

# Combine options
./claude-costs.py -d 14 -v
```

## Options

- `-d, --days INTEGER`: Number of days to analyze (default: 30)
- `-v, --verbose`: Show detailed breakdown of all projects
- `-c, --claude-dir PATH`: Path to Claude directory (default: ~/.claude)
- `--help`: Show help message

## Output Sections

### Cost Summary

- **Actual cost**: What you paid after cache discounts
- **Cache savings**: Amount saved due to 90% cache read discount
- **Without cache cost**: What it would have cost without caching

### Token Breakdown

Shows total tokens used with percentages for:

- **Cached**: Tokens read from cache (90% discount)
- **Cache write**: Tokens written to cache (25% premium)
- **Output**: Generated tokens (most expensive)

### Project Breakdown

Table showing for each project:

- Total cost
- Number of sessions
- Active days
- Total tokens
- Cache efficiency percentage

### Activity Patterns

- **Hourly sparkline**: 24-hour activity distribution
- **Daily bar chart**: Activity by day of week

### Tool Use Stats

Shows how often Claude's suggestions were:

- ✓ Accepted
- ✗ Rejected/cancelled

## Pricing

The script includes pricing for Claude models as of 2025:

- **Claude 4 Opus**: $15/M input, $75/M output
- **Claude 4 Sonnet**: $3/M input, $15/M output
- **Claude 3.5 Sonnet**: $3/M input, $15/M output
- **Claude 3.5 Haiku**: $0.80/M input, $4/M output
- **Claude 3 Haiku**: $0.25/M input, $1.25/M output

Cache pricing:

- **Cache write**: 25% more than input price
- **Cache read**: 90% discount from input price

## Requirements

- Python 3.9+
- Access to `~/.claude/projects/*.jsonl` files
- [`uv` package manager](https://docs.astral.sh/uv/getting-started/installation/) (or manually install `rich` and `typer`)

## Notes

- Inspired by https://gist.github.com/esc5221/df0a0c3c068b8dd92282837389addb35 (which stopped working many days ago)
- Project names are automatically cleaned (removes $HOME prefix)
- Handles both old (costUSD) and new (usage tokens) metadata formats
- Only shows projects with costs > $0.01
- Activity patterns only shown if data exists for the period

## Example Output

```
💰 $123.45 actual cost (7 days)
💸 $456.78 saved from caching ($580.23 without cache)
📊 42 sessions • $2.94/session • 6 active days
🔤 89.1M tokens (91% cached / 9% cache write)

Project Breakdown:
  Project                       Cost   Sessions   Days   Tokens   Cache%
 ────────────────────────────────────────────────────────────────────────
  my-web-app                  $45.67         18      5    38.5M      92%
  backend-api                 $32.15         12      4    27.3M      89%
  data-analysis               $28.91          8      3    15.2M      94%
  ...

Activity Patterns:
Hourly:  ▁▁▁▁▁▂▄▅▇█▇▅▄▃▂▃▄▅▆▇▅▃▂▁ (24h)
         ↑     ↑     ↑     ↑
         0     6     12    18

Daily distribution:
  Mon: ████████████████          32%
  Tue: █████████████████████     42%
  Wed: ████████                  16%
  ...

Tool Use Stats:
  Total tool uses: 567
  ✓ Accepted: 542 (95.6%)
  ✗ Rejected: 25 (4.4%)
```
