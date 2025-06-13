#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "rich>=13.0.0",
#   "typer>=0.9.0",
# ]
# ///
"""
Claude Code Cost Calculator

Analyzes Claude Code usage from .jsonl files and displays costs with token usage statistics.

Usage:
    claude-costs.py              # Analyze last 30 days
    claude-costs.py -d 7         # Analyze last 7 days
    claude-costs.py -v           # Show all projects
    claude-costs.py -c ~/backup/.claude  # Use alternate Claude directory

"""

__version__ = "1.0.0"

import os
import json
import glob
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple
import typer
from rich.console import Console
from rich.table import Table
from rich import box

# Pricing as of 2025 (per million tokens)
PRICING = {
    # Claude 4 models (May 2025)
    "claude-opus-4-20250514": {
        "input": 15.00,
        "output": 75.00,
        "cache_write": 18.75,  # 25% more than input
        "cache_read": 1.50,   # 90% discount
    },
    "claude-sonnet-4-20250514": {
        "input": 3.00,
        "output": 15.00,
        "cache_write": 3.75,  # 25% more than input
        "cache_read": 0.30,   # 90% discount
    },
    # Claude 3.5 models
    "claude-3-5-sonnet-20241022": {
        "input": 3.00,
        "output": 15.00,
        "cache_write": 3.75,  # 25% more than input
        "cache_read": 0.30,   # 90% discount
    },
    "claude-3-5-haiku-20241022": {
        "input": 0.80,
        "output": 4.00,
        "cache_write": 1.00,  # 25% more than input
        "cache_read": 0.08,   # 90% discount
    },
    # Legacy Claude 3 Haiku
    "claude-3-haiku-20240307": {
        "input": 0.25,
        "output": 1.25,
        "cache_write": 0.3125,  # 25% more than input
        "cache_read": 0.025,   # 90% discount
    }
}

# Default to Sonnet 4 pricing if model not found
DEFAULT_PRICING = PRICING["claude-sonnet-4-20250514"]

console = Console()
app = typer.Typer()


def calculate_token_cost(usage: dict, model: str) -> Tuple[float, float]:
    """Calculate cost from token usage data. Returns (actual_cost, savings_from_cache)."""
    pricing = PRICING.get(model, DEFAULT_PRICING)
    
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cache_creation = usage.get("cache_creation_input_tokens", 0)
    cache_read = usage.get("cache_read_input_tokens", 0)
    
    # Calculate costs (prices are per million tokens)
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    cache_write_cost = (cache_creation / 1_000_000) * pricing["cache_write"]
    cache_read_cost = (cache_read / 1_000_000) * pricing["cache_read"]
    
    # Calculate what cache reads would have cost as regular input
    cache_read_full_cost = (cache_read / 1_000_000) * pricing["input"]
    cache_savings = cache_read_full_cost - cache_read_cost
    
    actual_cost = input_cost + output_cost + cache_write_cost + cache_read_cost
    
    return actual_cost, cache_savings


def parse_jsonl_files(project_dir: Path, cutoff_date: datetime.date = None) -> Tuple[Dict, Dict, Dict, Dict, Dict, float, Dict, Dict, Dict, List[float], Dict, Dict]:
    """Parse all JSONL files and extract cost/usage data."""
    jsonl_files = glob.glob(str(project_dir / "**/*.jsonl"), recursive=True)
    
    daily_costs = defaultdict(float)
    session_data = defaultdict(lambda: {
        "cost": 0.0,
        "tokens": {"input": 0, "output": 0, "cache_create": 0, "cache_read": 0},
        "start": None,
        "end": None,
        "messages": 0
    })
    project_costs = defaultdict(float)
    project_stats = defaultdict(lambda: {
        "cost": 0.0,
        "sessions": set(),
        "tokens": {"input": 0, "output": 0, "cache_create": 0, "cache_read": 0},
        "days": set(),
        "messages": 0,
        "response_times": []  # Track response times per project
    })
    
    total_tokens = {"input": 0, "output": 0, "cache_create": 0, "cache_read": 0}
    total_cache_savings = 0.0
    
    # Time-based analytics
    hourly_activity = defaultdict(int)
    daily_activity = defaultdict(int)
    daily_message_counts = defaultdict(int)  # Messages per calendar day
    
    # Tool use metrics
    tool_use_stats = {
        "total": 0,
        "accepted": 0,
        "interrupted": 0
    }
    
    # Response time tracking
    response_times = []  # Global response times
    daily_response_times = defaultdict(list)  # Response times by date for sparkline
    
    for file_path in jsonl_files:
        # Extract project name
        parts = Path(file_path).parts
        project_name = "unknown"
        for i, part in enumerate(parts):
            if part == "projects" and i + 1 < len(parts):
                # Get the encoded project name
                encoded_name = parts[i + 1]
                
                # Try to find the actual directory by matching the encoded pattern
                # The encoded format is like: -home-mrm-src-node-sqlite
                if encoded_name.startswith("-"):
                    # Remove leading dash and split
                    path_parts = encoded_name[1:].split("-")
                    
                    # Try to reconstruct the path and check if it exists
                    # Start from root and build up
                    if len(path_parts) > 2 and path_parts[0] == "home":
                        # Build the full path
                        test_path = "/" + "/".join(path_parts)
                        
                        # If the exact path doesn't exist, try with hyphens in the last part
                        if not Path(test_path).exists() and len(path_parts) > 3:
                            # Try combining the last parts with hyphens
                            for split_point in range(len(path_parts) - 1, 2, -1):
                                base_path = "/" + "/".join(path_parts[:split_point])
                                name_part = "-".join(path_parts[split_point:])
                                test_path = base_path + "/" + name_part
                                if Path(test_path).exists():
                                    break
                        
                        project_name = test_path
                else:
                    # Fallback to simple replacement
                    project_name = encoded_name.replace("-", "/")
                
                # Remove $HOME prefix
                home = str(Path.home())
                if project_name.startswith(home):
                    project_name = project_name[len(home):].lstrip("/")
                break
        
        session_id = Path(file_path).stem
        
        # First pass: collect all messages by uuid for response time calculation
        messages_by_uuid = {}
        with open(file_path, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    uuid = entry.get("uuid")
                    if uuid:
                        messages_by_uuid[uuid] = entry
                except (json.JSONDecodeError, KeyError):
                    continue
        
        # Second pass: process messages
        with open(file_path, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    
                    # Track tool use results from user messages
                    if entry.get("type") == "user":
                        message = entry.get("message", {})
                        content = message.get("content", [])
                        
                        # Look for tool_result entries
                        for item in content if isinstance(content, list) else []:
                            if isinstance(item, dict) and item.get("type") == "tool_result":
                                tool_use_stats["total"] += 1
                                
                                # Check toolUseResult first for the most accurate info
                                tool_use_result = entry.get("toolUseResult", {})
                                if isinstance(tool_use_result, dict):
                                    if tool_use_result.get("interrupted", False):
                                        tool_use_stats["interrupted"] += 1
                                    else:
                                        # Check the content for rejection messages as fallback
                                        tool_content = item.get("content", "")
                                        if isinstance(tool_content, str):
                                            if "user doesn't want to proceed" in tool_content or "tool use was rejected" in tool_content:
                                                tool_use_stats["interrupted"] += 1
                                            elif item.get("is_error", False):
                                                tool_use_stats["interrupted"] += 1
                                            else:
                                                tool_use_stats["accepted"] += 1
                                        else:
                                            tool_use_stats["accepted"] += 1
                                else:
                                    # Fallback to checking content for rejection messages
                                    tool_content = item.get("content", "")
                                    if isinstance(tool_content, str):
                                        if "user doesn't want to proceed" in tool_content or "tool use was rejected" in tool_content:
                                            tool_use_stats["interrupted"] += 1
                                        elif item.get("is_error", False):
                                            tool_use_stats["interrupted"] += 1
                                        else:
                                            tool_use_stats["accepted"] += 1
                                    else:
                                        tool_use_stats["accepted"] += 1
                    
                    # Calculate response time for assistant messages
                    if entry.get("type") == "assistant":
                        parent_uuid = entry.get("parentUuid")
                        if parent_uuid and parent_uuid in messages_by_uuid:
                            parent_msg = messages_by_uuid[parent_uuid]
                            if parent_msg.get("type") == "user":
                                # Calculate response time
                                try:
                                    user_time = datetime.fromisoformat(parent_msg["timestamp"].replace('Z', '+00:00'))
                                    assistant_time = datetime.fromisoformat(entry["timestamp"].replace('Z', '+00:00'))
                                    response_time = (assistant_time - user_time).total_seconds()
                                    
                                    if 0 < response_time < 300:  # Sanity check: between 0 and 5 minutes
                                        response_times.append(response_time)
                                        project_stats[project_name]["response_times"].append(response_time)
                                        # Track by date for sparkline
                                        response_date = assistant_time.date()
                                        if not cutoff_date or response_date >= cutoff_date:
                                            daily_response_times[response_date].append(response_time)
                                except:
                                    pass
                    
                    # Skip non-assistant messages for cost calculation
                    if entry.get("type") != "assistant":
                        continue
                    
                    timestamp_str = entry.get("timestamp")
                    if not timestamp_str:
                        continue
                    
                    # Parse timestamp and convert to local time
                    timestamp_utc = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    # Convert UTC to local time properly
                    timestamp_local = timestamp_utc.replace(tzinfo=timezone.utc).astimezone()
                    timestamp = timestamp_local.replace(tzinfo=None)
                    date = timestamp.date()
                    
                    # Skip entries before cutoff date if specified
                    if cutoff_date and date < cutoff_date:
                        continue
                    
                    # Track session times
                    if session_data[session_id]["start"] is None:
                        session_data[session_id]["start"] = timestamp
                    session_data[session_id]["end"] = timestamp
                    session_data[session_id]["messages"] += 1
                    
                    # Track project stats
                    project_stats[project_name]["sessions"].add(session_id)
                    project_stats[project_name]["days"].add(date)
                    project_stats[project_name]["messages"] += 1
                    
                    # Track time-based activity
                    hourly_activity[timestamp.hour] += 1
                    daily_activity[timestamp.weekday()] += 1
                    daily_message_counts[date] += 1
                    
                    # Check for old format (costUSD)
                    if "costUSD" in entry:
                        cost = entry["costUSD"]
                        daily_costs[date] += cost
                        session_data[session_id]["cost"] += cost
                        project_costs[project_name] += cost
                        project_stats[project_name]["cost"] += cost
                    
                    # Check for new format (usage with tokens)
                    elif "message" in entry and isinstance(entry["message"], dict):
                        msg = entry["message"]
                        if "usage" in msg and isinstance(msg["usage"], dict):
                            usage = msg["usage"]
                            model = msg.get("model", "claude-3-5-sonnet-20241022")
                            
                            # Skip synthetic/error messages
                            if model == "<synthetic>":
                                continue
                            
                            cost, savings = calculate_token_cost(usage, model)
                            daily_costs[date] += cost
                            session_data[session_id]["cost"] += cost
                            project_costs[project_name] += cost
                            project_stats[project_name]["cost"] += cost
                            total_cache_savings += savings
                            
                            # Track tokens
                            session_data[session_id]["tokens"]["input"] += usage.get("input_tokens", 0)
                            session_data[session_id]["tokens"]["output"] += usage.get("output_tokens", 0)
                            session_data[session_id]["tokens"]["cache_create"] += usage.get("cache_creation_input_tokens", 0)
                            session_data[session_id]["tokens"]["cache_read"] += usage.get("cache_read_input_tokens", 0)
                            
                            # Track project tokens
                            project_stats[project_name]["tokens"]["input"] += usage.get("input_tokens", 0)
                            project_stats[project_name]["tokens"]["output"] += usage.get("output_tokens", 0)
                            project_stats[project_name]["tokens"]["cache_create"] += usage.get("cache_creation_input_tokens", 0)
                            project_stats[project_name]["tokens"]["cache_read"] += usage.get("cache_read_input_tokens", 0)
                            
                            total_tokens["input"] += usage.get("input_tokens", 0)
                            total_tokens["output"] += usage.get("output_tokens", 0)
                            total_tokens["cache_create"] += usage.get("cache_creation_input_tokens", 0)
                            total_tokens["cache_read"] += usage.get("cache_read_input_tokens", 0)
                
                except (json.JSONDecodeError, KeyError) as e:
                    continue
    
    return (daily_costs, session_data, project_costs, total_tokens, project_stats, 
            total_cache_savings, hourly_activity, daily_activity, tool_use_stats, response_times, 
            daily_response_times, daily_message_counts)


def format_tokens(num: int) -> str:
    """Format token count with appropriate units."""
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}k"
    return str(num)


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes}m"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        if minutes > 0:
            return f"{hours}h{minutes}m"
        return f"{hours}h"


def create_sparkline(values: List[float], width: int = 20) -> str:
    """Create a sparkline chart using Unicode block characters."""
    if not values or all(v == 0 for v in values):
        return "─" * width
    
    blocks = " ▁▂▃▄▅▆▇█"
    min_val = min(values)
    max_val = max(values)
    
    if max_val == min_val:
        return "▄" * width
    
    # Normalize values to 0-8 range
    normalized = []
    for v in values:
        norm = int((v - min_val) / (max_val - min_val) * 8)
        normalized.append(blocks[norm])
    
    # Resample if needed
    if len(normalized) > width:
        # Simple resampling - take evenly spaced samples
        step = len(normalized) / width
        result = []
        for i in range(width):
            idx = int(i * step)
            result.append(normalized[idx])
        return "".join(result)
    
    return "".join(normalized)


def create_bar_chart(values: List[float], labels: List[str], max_width: int = 30) -> List[str]:
    """Create a horizontal bar chart."""
    if not values or all(v == 0 for v in values):
        return []
    
    max_val = max(values)
    lines = []
    
    for label, value in zip(labels, values):
        if max_val > 0:
            bar_length = int((value / max_val) * max_width)
            bar = "█" * bar_length
            percentage = (value / sum(values)) * 100
            lines.append(f"{label:>3}: {bar:<{max_width}} {percentage:4.0f}%")
        else:
            lines.append(f"{label:>3}: {'':<{max_width}}   0%")
    
    return lines


@app.command()
def main(
    days: int = typer.Option(90, "--days", "-d", help="Number of days to analyze"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed breakdown"),
    claude_dir: Path = typer.Option(None, "--claude-dir", "-c", help="Path to Claude directory", show_default="~/.claude"),
    show_cache: bool = typer.Option(False, "--cache", help="Show cache statistics"),
):
    """Calculate Claude Code usage costs and statistics."""
    
    # Use provided claude_dir or default to ~/.claude
    if claude_dir is None:
        claude_dir = Path.home() / ".claude"
    
    project_dir = claude_dir / "projects"
    if not project_dir.exists():
        console.print(f"[red]Error: {project_dir} does not exist[/red]")
        console.print("[yellow]Make sure you're pointing to the correct Claude directory.[/yellow]")
        raise typer.Exit(1)
    
    # Show which directory we're analyzing
    console.print(f"\n[dim]Analyzing: {claude_dir}[/dim]")
    
    # Calculate cutoff date
    cutoff_date = datetime.now().date() - timedelta(days=days)
    
    # Parse data with cutoff date
    (daily_costs, session_data, project_costs, total_tokens, project_stats, 
     total_cache_savings, hourly_activity, daily_activity, tool_use_stats, response_times, 
     daily_response_times, daily_message_counts) = parse_jsonl_files(project_dir, cutoff_date)
    
    if not daily_costs:
        console.print("[yellow]No cost data found in JSONL files[/yellow]")
        console.print("[dim]Make sure there are .jsonl files in the projects/ subdirectory[/dim]")
        raise typer.Exit(0)
    
    # Calculate statistics (data is already filtered by date)
    total_cost = sum(daily_costs.values())
    
    # All sessions are already filtered by date
    recent_sessions = session_data
    
    # Calculate session statistics
    num_sessions = len(recent_sessions)
    active_days = len(set(data["start"].date() for data in recent_sessions.values() if data["start"]))
    
    avg_sessions_per_day = num_sessions / days if days > 0 else 0
    avg_cost_per_session = total_cost / num_sessions if num_sessions > 0 else 0
    
    # Calculate average session duration
    session_durations = []
    for session in recent_sessions.values():
        if session["start"] and session["end"]:
            duration = (session["end"] - session["start"]).total_seconds()
            if duration > 0:  # Only count sessions with actual duration
                session_durations.append(duration)
    
    avg_duration = sum(session_durations) / len(session_durations) if session_durations else 0
    
    # Calculate response time statistics
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0
    if response_times:
        sorted_times = sorted(response_times)
        median_response_time = sorted_times[len(sorted_times)//2]
        p95_response_time = sorted_times[int(len(sorted_times) * 0.95)]
        p99_response_time = sorted_times[int(len(sorted_times) * 0.99)]
    else:
        median_response_time = p95_response_time = p99_response_time = 0
    
    # Calculate token percentages
    total_all_tokens = sum(total_tokens.values())
    if total_all_tokens > 0:
        cache_percent = (total_tokens["cache_read"] / total_all_tokens) * 100
        output_percent = (total_tokens["output"] / total_all_tokens) * 100
        cache_create_percent = (total_tokens["cache_create"] / total_all_tokens) * 100
    else:
        cache_percent = output_percent = cache_create_percent = 0
    
    # Display summary
    console.print()
    console.print(f"💰 ${total_cost:.2f} API value (last {days} days, {active_days} with activity)")
    if show_cache and total_cache_savings > 0.01:
        console.print(f"💸 ${total_cache_savings:.2f} saved from caching (${total_cost + total_cache_savings:.2f} without cache)")
    avg_cost_per_day = total_cost / active_days if active_days > 0 else 0
    console.print(f"📊 {num_sessions} sessions • ${avg_cost_per_session:.2f}/session • ${avg_cost_per_day:.2f}/day")
    console.print(f"[dim]Note: This shows API value, not your actual subscription cost[/dim]")
    
    # Build token display
    if show_cache:
        # Show detailed breakdown with cache info
        token_parts = []
        if cache_percent > 0.5:
            token_parts.append(f"{cache_percent:.0f}% cached")
        if cache_create_percent > 0.5:
            token_parts.append(f"{cache_create_percent:.0f}% cache write")
        if output_percent > 0.5:
            token_parts.append(f"{output_percent:.0f}% output")
        
        token_breakdown = " / ".join(token_parts) if token_parts else "no token breakdown available"
        console.print(f"🔤 {format_tokens(total_all_tokens)} tokens ({token_breakdown})", highlight=False)
    else:
        # Simple token count
        console.print(f"🔤 {format_tokens(total_all_tokens)} tokens total")
    
    # Always show project breakdown
    console.print("\n[bold]Project Breakdown:[/bold]")
    table = Table(box=box.SIMPLE)
    table.add_column("Project", style="cyan")
    table.add_column("Cost", justify="right", style="green")
    table.add_column("Sessions", justify="right", style="yellow")
    table.add_column("Days", justify="right", style="magenta")
    table.add_column("Resp Time", justify="right", style="cyan")
    table.add_column("Tokens", justify="right", style="blue")
    if show_cache:
        table.add_column("Cache%", justify="right", style="dim")
    
    # Filter and sort projects by cost
    sorted_projects = []
    for project_name, stats in project_stats.items():
        if stats["cost"] > 0.01:  # Only show projects with meaningful costs
            # Calculate total tokens for this project
            project_total_tokens = sum(stats["tokens"].values())
            cache_percent = (stats["tokens"]["cache_read"] / project_total_tokens * 100) if project_total_tokens > 0 else 0
            
            # Calculate average session duration for this project
            project_durations = []
            for session_id in stats["sessions"]:
                if session_id in session_data:
                    session = session_data[session_id]
                    if session["start"] and session["end"]:
                        duration = (session["end"] - session["start"]).total_seconds()
                        if duration > 0:
                            project_durations.append(duration)
            
            avg_project_duration = sum(project_durations) / len(project_durations) if project_durations else 0
            
            # Calculate average response time for this project
            avg_project_response_time = sum(stats["response_times"]) / len(stats["response_times"]) if stats["response_times"] else 0
            
            sorted_projects.append((
                project_name,
                stats["cost"],
                len(stats["sessions"]),
                len(stats["days"]),
                avg_project_response_time,
                project_total_tokens,
                cache_percent
            ))
    
    sorted_projects.sort(key=lambda x: x[1], reverse=True)
    
    # Show top projects (or all if verbose)
    limit = None if verbose else 10
    for project, cost, sessions, project_days, resp_time, tokens, cache_pct in sorted_projects[:limit]:
        row_data = [
            project,
            f"${cost:.2f}",
            str(sessions),
            str(project_days),
            f"{resp_time:.1f}s" if resp_time > 0 else "-",
            format_tokens(tokens)
        ]
        if show_cache:
            row_data.append(f"{cache_pct:.0f}%")
        table.add_row(*row_data)
    
    console.print(table)
    
    if not verbose and len(sorted_projects) > 10:
        console.print(f"\n[dim]Showing top 10 projects. Use --verbose to see all {len(sorted_projects)} projects.[/dim]")
    
    # Activity patterns
    console.print("\n[bold]Activity Patterns:[/bold]")
    
    # Hourly activity sparkline
    hours = list(range(24))
    hourly_values = [hourly_activity.get(h, 0) for h in hours]
    if any(hourly_values):
        sparkline = create_sparkline(hourly_values, width=24)
        console.print(f"Hourly:  {sparkline} (24h)")
        console.print(f"         {''.join(['↑' if h % 6 == 0 else ' ' for h in range(24)])}")
        console.print(f"         {'0':>1}{'6':>6}{'12':>6}{'18':>6}")
    
    # Daily activity sparkline
    if daily_message_counts:
        # Get dates for the period
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days-1)
        
        # Create values for each day in the period
        daily_values = []
        current_date = start_date
        while current_date <= end_date:
            daily_values.append(daily_message_counts.get(current_date, 0))
            current_date += timedelta(days=1)
        
        if any(daily_values):
            # Use fixed width for consistent display
            sparkline_width = min(len(daily_values), 30)
            sparkline = create_sparkline(daily_values, width=sparkline_width)
            console.print(f"\nDaily:   {sparkline} (last {days} days, {sum(1 for v in daily_values if v > 0)} active)")
            # Add markers for start, middle and end
            if sparkline_width >= 20:
                # Three markers for longer sparklines
                mid_pos = sparkline_width // 2
                console.print(f"         ↑{' ' * (mid_pos-1)}↑{' ' * (sparkline_width-mid_pos-2)}↑")
                start_label = f"{days}d ago"
                mid_label = f"{days//2}d"
                console.print(f"         {start_label:<{mid_pos}}{mid_label:^{sparkline_width-mid_pos-5}}{'today':>5}")
            else:
                # Two markers for shorter sparklines
                console.print(f"         ↑{' ' * (sparkline_width-2)}↑")
                start_label = f"{days}d"
                console.print(f"         {start_label:<{sparkline_width//2}}{'today':>{sparkline_width-sparkline_width//2}}")
    
    # Response time distribution sparkline
    if response_times:
        # Create buckets for response times (0-30s in 1s intervals)
        response_buckets = defaultdict(int)
        max_bucket = 30  # Cap at 30 seconds for display
        
        for resp_time in response_times:
            bucket = min(int(resp_time), max_bucket - 1)
            response_buckets[bucket] += 1
        
        # Create values for each bucket
        bucket_values = [response_buckets.get(i, 0) for i in range(max_bucket)]
        
        # Find the last non-zero bucket for better display
        last_bucket = max_bucket
        for i in range(max_bucket - 1, -1, -1):
            if bucket_values[i] > 0:
                last_bucket = min(i + 3, max_bucket)  # Show a bit past the last value
                break
        
        # Trim to meaningful range
        bucket_values = bucket_values[:last_bucket]
        
        if any(bucket_values):
            sparkline = create_sparkline(bucket_values, width=min(len(bucket_values), 30))
            console.print(f"\nResponse: {sparkline} (p50: {median_response_time:.0f}s, p95: {p95_response_time:.0f}s, p99: {p99_response_time:.0f}s)")
            console.print(f"          {'↑':>1}{'↑':>{len(sparkline)//2}}{'↑':>{len(sparkline)-len(sparkline)//2-1}}")
            console.print(f"          {'0s':>2}{f'{last_bucket//2}s':>{len(sparkline)//2}}{f'{last_bucket}s':>{len(sparkline)-len(sparkline)//2-2}}")
    
    # Day of week bar chart
    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    daily_values = [daily_activity.get(i, 0) for i in range(7)]
    if any(daily_values):
        console.print("\nDaily distribution:")
        bar_lines = create_bar_chart(daily_values, weekdays, max_width=25)
        for line in bar_lines:
            console.print(f"  {line}")
    
    # Tool use acceptance stats
    if tool_use_stats["total"] > 0:
        console.print("\n[bold]Tool Use Stats:[/bold]")
        total_tools = tool_use_stats["total"]
        accepted_pct = (tool_use_stats["accepted"] / total_tools) * 100
        interrupted_pct = (tool_use_stats["interrupted"] / total_tools) * 100
        
        console.print(f"  Total tool uses: {total_tools:,}")
        console.print(f"  ✓ Accepted: {tool_use_stats['accepted']:,} ({accepted_pct:.1f}%)")
        console.print(f"  ✗ Rejected: {tool_use_stats['interrupted']:,} ({interrupted_pct:.1f}%)")


if __name__ == "__main__":
    app()