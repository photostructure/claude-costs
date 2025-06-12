#!/usr/bin/env python3
"""
Analyze Claude's response generation times from JSONL files.

This script looks at the time between a user message and Claude's first response
to determine how long it takes Claude to generate responses.
"""

import json
import glob
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple
import statistics

def parse_timestamp(ts_str: str) -> datetime:
    """Parse ISO timestamp string to datetime object."""
    return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))

def analyze_response_times(jsonl_file: Path) -> List[float]:
    """
    Analyze response times in a single JSONL file.
    Returns list of response times in seconds.
    """
    response_times = []
    entries = []
    
    # Read all entries
    with open(jsonl_file, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError:
                continue
    
    # Sort by timestamp to ensure chronological order
    entries.sort(key=lambda x: x.get('timestamp', ''))
    
    # Find user messages followed by assistant responses
    for i in range(len(entries) - 1):
        current = entries[i]
        next_entry = entries[i + 1]
        
        # Look for user message followed by assistant response
        if (current.get('type') == 'user' and 
            next_entry.get('type') == 'assistant' and
            current.get('message', {}).get('role') == 'user' and
            next_entry.get('message', {}).get('role') == 'assistant' and
            next_entry.get('parentUuid') == current.get('uuid')):
            
            try:
                user_time = parse_timestamp(current['timestamp'])
                assistant_time = parse_timestamp(next_entry['timestamp'])
                
                # Calculate response time in seconds
                response_time = (assistant_time - user_time).total_seconds()
                
                # Filter out unrealistic times (< 0.1s or > 300s)
                if 0.1 <= response_time <= 300:
                    response_times.append(response_time)
            except (KeyError, ValueError):
                continue
    
    return response_times

def main():
    """Main function to analyze all JSONL files."""
    claude_dir = Path.home() / '.claude' / 'projects'
    
    if not claude_dir.exists():
        print(f"Claude directory not found: {claude_dir}")
        return
    
    all_response_times = []
    files_analyzed = 0
    
    # Analyze all JSONL files
    for jsonl_file in claude_dir.glob('*/*.jsonl'):
        response_times = analyze_response_times(jsonl_file)
        if response_times:
            all_response_times.extend(response_times)
            files_analyzed += 1
    
    if not all_response_times:
        print("No response times found in JSONL files.")
        return
    
    # Calculate statistics
    all_response_times.sort()
    
    print(f"\n📊 Claude Response Time Analysis")
    print(f"{'='*50}")
    print(f"Files analyzed: {files_analyzed}")
    print(f"Total responses: {len(all_response_times)}")
    print(f"\n⏱️  Response Time Statistics (seconds):")
    print(f"  Min:     {min(all_response_times):.2f}s")
    print(f"  Max:     {max(all_response_times):.2f}s")
    print(f"  Mean:    {statistics.mean(all_response_times):.2f}s")
    print(f"  Median:  {statistics.median(all_response_times):.2f}s")
    
    # Calculate percentiles
    percentiles = [25, 50, 75, 90, 95, 99]
    print(f"\n📈 Percentiles:")
    for p in percentiles:
        idx = int(len(all_response_times) * p / 100)
        value = all_response_times[min(idx, len(all_response_times) - 1)]
        print(f"  {p}th:    {value:.2f}s")
    
    # Show distribution
    print(f"\n📊 Response Time Distribution:")
    buckets = [(0, 1), (1, 2), (2, 5), (5, 10), (10, 20), (20, 30), (30, 60), (60, 300)]
    
    for low, high in buckets:
        count = sum(1 for t in all_response_times if low <= t < high)
        percentage = (count / len(all_response_times)) * 100
        bar = '█' * int(percentage / 2)
        print(f"  {low:3d}-{high:3d}s: {bar:<50} {percentage:5.1f}% ({count})")

if __name__ == "__main__":
    main()