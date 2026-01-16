"""
Metrics Aggregator - Fleet-Level Telemetry for Dashboard Analytics
Provides observatory-level insights across 400+ runs.
"""
import json
import statistics
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict, Counter


class MetricsAggregator:
    """Aggregate session data into fleet-level telemetry metrics"""
    
    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or Path(__file__).parent.parent
        self.sessions_dir = self.base_dir / "data" / "conversation_history"
        self.cache_dir = self.base_dir / "memory" / "metrics"
        self.cache_file = self.cache_dir / "dashboard_cache.json"
    
    def scan_sessions(self) -> List[Dict[str, Any]]:
        """Walk all session files and extract data"""
        sessions = []
        
        if not self.sessions_dir.exists():
            return sessions
        
        for session_file in self.sessions_dir.rglob("session_*.json"):
            try:
                data = json.loads(session_file.read_text(encoding="utf-8"))
                sessions.append({
                    "file": str(session_file),
                    "data": data
                })
            except Exception as e:
                print(f"⚠️ Error reading {session_file}: {e}")
        
        return sessions

    # =========================================================================
    # SECTION 1: FLEET OVERVIEW
    # =========================================================================
    
    def aggregate_fleet_overview(self, sessions: List[Dict]) -> Dict[str, Any]:
        """Core volume, outcome, cost, and efficiency metrics"""
        total_runs = len(sessions)
        costs = []
        tokens = []
        durations = []
        queries = set()
        
        # Outcome counts
        outcomes = {"success": 0, "partial": 0, "failed": 0, "aborted": 0, "running": 0}
        
        for session in sessions:
            data = session.get("data", {})
            nodes = data.get("nodes", [])
            
            # Unique queries
            query = data.get("original_query", "")
            if query:
                queries.add(query.strip().lower()[:100])
            
            # Per-run aggregates
            run_cost = sum(n.get("cost", 0) or 0 for n in nodes)
            run_tokens = sum(n.get("total_tokens", 0) or 0 for n in nodes)
            costs.append(run_cost)
            tokens.append(run_tokens)
            
            # Duration
            created = data.get("created_at")
            updated = data.get("updated_at")
            if created and updated:
                try:
                    start = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    end = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    durations.append((end - start).total_seconds())
                except:
                    pass
            
            # Determine run outcome from nodes
            statuses = [n.get("status") for n in nodes]
            if "failed" in statuses:
                outcomes["failed"] += 1
            elif "stopped" in statuses:
                outcomes["aborted"] += 1
            elif "running" in statuses:
                outcomes["running"] += 1
            elif all(s in ("completed", "skipped") for s in statuses if s):
                outcomes["success"] += 1
            else:
                outcomes["partial"] += 1
        
        # Calculate percentiles
        def safe_percentile(data: List[float], p: int) -> float:
            if not data:
                return 0.0
            sorted_data = sorted(data)
            idx = int(len(sorted_data) * p / 100)
            return round(sorted_data[min(idx, len(sorted_data) - 1)], 4)
        
        return {
            "total_runs": total_runs,
            "unique_queries": len(queries),
            "total_cost": round(sum(costs), 4),
            "total_tokens": sum(tokens),
            "avg_cost": round(statistics.mean(costs), 4) if costs else 0,
            "median_cost": round(statistics.median(costs), 4) if costs else 0,
            "p95_cost": safe_percentile(costs, 95),
            "avg_duration_sec": round(statistics.mean(durations), 1) if durations else 0,
            "p95_duration_sec": safe_percentile(durations, 95),
            "outcomes": outcomes,
            "success_rate": round(outcomes["success"] / max(total_runs, 1) * 100, 1)
        }

    # =========================================================================
    # SECTION 2: AGENT PERFORMANCE MATRIX
    # =========================================================================
    
    def aggregate_agent_matrix(self, sessions: List[Dict]) -> Dict[str, Any]:
        """Per-agent breakdown with reliability scores"""
        agent_stats = defaultdict(lambda: {
            "calls": 0,
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost": 0.0,
            "successes": 0,
            "failures": 0,
            "retries": 0,
            "durations": []
        })
        
        for session in sessions:
            data = session.get("data", {})
            nodes = data.get("nodes", [])
            
            for node in nodes:
                agent = node.get("agent")
                if not agent:
                    continue
                
                stats = agent_stats[agent]
                stats["calls"] += 1
                stats["total_tokens"] += node.get("total_tokens", 0) or 0
                stats["input_tokens"] += node.get("input_tokens", 0) or 0
                stats["output_tokens"] += node.get("output_tokens", 0) or 0
                stats["total_cost"] += node.get("cost", 0) or 0
                stats["retries"] += node.get("retries", 0) or 0
                
                status = node.get("status")
                if status == "completed":
                    stats["successes"] += 1
                elif status == "failed":
                    stats["failures"] += 1
        
        # Build matrix with derived metrics
        matrix = {}
        for agent, stats in agent_stats.items():
            calls = stats["calls"]
            success_rate = stats["successes"] / max(calls, 1)
            retry_rate = stats["retries"] / max(calls, 1)
            error_rate = stats["failures"] / max(calls, 1)
            
            # Reliability Score: (1 - error_rate) × (1 - retry_rate) × 100
            reliability = (1 - error_rate) * (1 - min(retry_rate, 1)) * 100
            
            matrix[agent] = {
                "calls": calls,
                "avg_tokens": round(stats["total_tokens"] / max(calls, 1)),
                "avg_cost": round(stats["total_cost"] / max(calls, 1), 5),
                "total_cost": round(stats["total_cost"], 4),
                "success_rate": round(success_rate * 100, 1),
                "retry_rate": round(retry_rate * 100, 1),
                "reliability_score": round(reliability, 1)
            }
        
        return matrix

    # =========================================================================
    # SECTION 3: TEMPORAL TRENDS
    # =========================================================================
    
    def aggregate_temporal(self, sessions: List[Dict]) -> Dict[str, Any]:
        """Time-series data for trend analysis"""
        by_day = defaultdict(lambda: {
            "runs": 0, "cost": 0.0, "tokens": 0, "successes": 0, "failures": 0
        })
        
        for session in sessions:
            data = session.get("data", {})
            created = data.get("created_at", "")
            nodes = data.get("nodes", [])
            
            if not created:
                continue
                
            try:
                date_str = created[:10]
                by_day[date_str]["runs"] += 1
                
                for node in nodes:
                    by_day[date_str]["cost"] += node.get("cost", 0) or 0
                    by_day[date_str]["tokens"] += node.get("total_tokens", 0) or 0
                    
                    status = node.get("status")
                    if status == "completed":
                        by_day[date_str]["successes"] += 1
                    elif status == "failed":
                        by_day[date_str]["failures"] += 1
            except:
                pass
        
        # Build sorted time series
        daily = []
        for date, stats in sorted(by_day.items(), reverse=True):
            total_nodes = stats["successes"] + stats["failures"]
            daily.append({
                "date": date,
                "runs": stats["runs"],
                "cost": round(stats["cost"], 4),
                "tokens": stats["tokens"],
                "success_rate": round(stats["successes"] / max(total_nodes, 1) * 100, 1)
            })
        
        return {
            "daily": daily[:30],
            "total_days": len(daily)
        }

    # =========================================================================
    # SECTION 4: RETRY & FAILURE ANALYTICS
    # =========================================================================
    
    def aggregate_retry_analytics(self, sessions: List[Dict]) -> Dict[str, Any]:
        """Retry distribution and failure patterns"""
        retry_counts = []
        retry_costs = 0.0
        failure_agents = Counter()
        
        for session in sessions:
            data = session.get("data", {})
            nodes = data.get("nodes", [])
            
            run_retries = 0
            for node in nodes:
                retries = node.get("retries", 0) or 0
                run_retries += retries
                
                if retries > 0:
                    retry_costs += node.get("cost", 0) or 0
                
                if node.get("status") == "failed":
                    agent = node.get("agent", "Unknown")
                    failure_agents[agent] += 1
            
            retry_counts.append(run_retries)
        
        # Retry distribution
        distribution = {"0": 0, "1": 0, "2": 0, "3+": 0}
        for count in retry_counts:
            if count == 0:
                distribution["0"] += 1
            elif count == 1:
                distribution["1"] += 1
            elif count == 2:
                distribution["2"] += 1
            else:
                distribution["3+"] += 1
        
        return {
            "avg_retries_per_run": round(statistics.mean(retry_counts), 2) if retry_counts else 0,
            "total_retry_cost": round(retry_costs, 4),
            "distribution": distribution,
            "top_failure_agents": dict(failure_agents.most_common(5))
        }

    # =========================================================================
    # SECTION 5: TOOL & MCP ANALYTICS
    # =========================================================================
    
    def aggregate_tool_usage(self, sessions: List[Dict]) -> Dict[str, Any]:
        """Extract MCP tool call statistics from iterations"""
        import re
        tool_stats = Counter()
        tool_successes = Counter()
        tool_failures = Counter()
        
        for session in sessions:
            data = session.get("data", {})
            nodes = data.get("nodes", [])
            
            for node in nodes:
                iterations = node.get("iterations", [])
                
                for iteration in iterations:
                    output = iteration.get("output", {})
                    
                    # Look for tool calls in output
                    if isinstance(output, dict):
                        tool_name = output.get("call_tool") or output.get("tool_name")
                        if tool_name:
                            tool_stats[tool_name] += 1
                            
                            # Check if tool succeeded
                            tool_result = iteration.get("tool_result", "")
                            if isinstance(tool_result, str):
                                if "error" in tool_result.lower() or "failed" in tool_result.lower():
                                    tool_failures[tool_name] += 1
                                else:
                                    tool_successes[tool_name] += 1
                            else:
                                tool_successes[tool_name] += 1
                    
                    # Also check for tool calls in execution_result
                    exec_result = iteration.get("execution_result", "")
                    if isinstance(exec_result, str):
                        # Extract tool names from patterns like "calling: tool_name"
                        matches = re.findall(r'calling[:\s]+(\w+)', exec_result, re.I)
                        for match in matches:
                            if match not in tool_stats:
                                tool_stats[match] += 1
        
        # Build results
        tools = []
        for tool, count in tool_stats.most_common(15):
            success = tool_successes.get(tool, count)
            fail = tool_failures.get(tool, 0)
            tools.append({
                "name": tool,
                "calls": count,
                "successes": success,
                "failures": fail,
                "success_rate": round(success / max(count, 1) * 100, 1)
            })
        
        return {
            "tools": tools,
            "total_calls": sum(tool_stats.values()),
            "unique_tools": len(tool_stats)
        }
    
    # =========================================================================
    # SECTION 6: URL/SOURCE ANALYTICS
    # =========================================================================
    
    def aggregate_url_sources(self, sessions: List[Dict]) -> Dict[str, Any]:
        """Extract internet sources and URLs accessed"""
        import re
        url_pattern = re.compile(r'https?://([a-zA-Z0-9.-]+)')
        
        domain_counts = Counter()
        domain_success = Counter()
        domain_failure = Counter()
        
        for session in sessions:
            data = session.get("data", {})
            nodes = data.get("nodes", [])
            
            for node in nodes:
                status = node.get("status", "")
                iterations = node.get("iterations", [])
                
                for iteration in iterations:
                    # Search for URLs in various fields
                    texts_to_search = []
                    
                    tool_result = iteration.get("tool_result", "")
                    if isinstance(tool_result, str):
                        texts_to_search.append(tool_result)
                    elif isinstance(tool_result, dict):
                        texts_to_search.append(json.dumps(tool_result))
                    
                    exec_result = iteration.get("execution_result", "")
                    if isinstance(exec_result, str):
                        texts_to_search.append(exec_result)
                    
                    for text in texts_to_search:
                        domains = url_pattern.findall(text)
                        for domain in domains:
                            domain = domain.lower()
                            domain_counts[domain] += 1
                            
                            if status == "completed":
                                domain_success[domain] += 1
                            elif status == "failed":
                                domain_failure[domain] += 1
        
        # Build results
        sources = []
        for domain, count in domain_counts.most_common(10):
            sources.append({
                "domain": domain,
                "hits": count,
                "success_context": domain_success.get(domain, 0),
                "failure_context": domain_failure.get(domain, 0)
            })
        
        return {
            "top_sources": sources,
            "total_urls": sum(domain_counts.values()),
            "unique_domains": len(domain_counts)
        }
    
    # =========================================================================
    # SECTION 7: TOKEN QUALITY ANALYSIS
    # =========================================================================
    
    def aggregate_token_quality(self, sessions: List[Dict]) -> Dict[str, Any]:
        """Analyze token efficiency - good tokens vs wasted tokens"""
        successful_tokens = 0
        failed_tokens = 0
        retry_tokens = 0
        
        input_tokens = 0
        output_tokens = 0
        
        for session in sessions:
            data = session.get("data", {})
            nodes = data.get("nodes", [])
            
            for node in nodes:
                tokens = node.get("total_tokens", 0) or 0
                status = node.get("status", "")
                retries = node.get("retries", 0) or 0
                
                input_tokens += node.get("input_tokens", 0) or 0
                output_tokens += node.get("output_tokens", 0) or 0
                
                if status == "completed":
                    successful_tokens += tokens
                elif status == "failed":
                    failed_tokens += tokens
                
                if retries > 0:
                    # Estimate tokens used in retries (rough approximation)
                    retry_tokens += tokens * (retries / (retries + 1))
        
        total = successful_tokens + failed_tokens
        
        return {
            "successful_tokens": successful_tokens,
            "failed_tokens": failed_tokens,
            "retry_tokens": round(retry_tokens),
            "total_input": input_tokens,
            "total_output": output_tokens,
            "io_ratio": round(output_tokens / max(input_tokens, 1), 2),
            "efficiency_pct": round(successful_tokens / max(total, 1) * 100, 1),
            "waste_pct": round(failed_tokens / max(total, 1) * 100, 1)
        }

    # =========================================================================
    # SECTION 8: AUTO-GENERATED INSIGHTS
    # =========================================================================
    
    def generate_insights(self, metrics: Dict[str, Any]) -> List[str]:
        """Generate human-readable insight sentences"""
        insights = []
        
        totals = metrics.get("totals", {})
        agents = metrics.get("agents", {})
        retries = metrics.get("retries", {})
        tools = metrics.get("tools", {})
        token_quality = metrics.get("token_quality", {})
        
        # Cost insight
        total_cost = totals.get("total_cost", 0)
        retry_cost = retries.get("total_retry_cost", 0)
        if total_cost > 0 and retry_cost > 0:
            retry_pct = round(retry_cost / total_cost * 100, 1)
            if retry_pct > 10:
                insights.append(f"⚠️ {retry_pct}% of your total cost comes from retries.")
        
        # Agent reliability insight
        if agents:
            worst_agent = min(agents.items(), key=lambda x: x[1].get("reliability_score", 100))
            if worst_agent[1].get("reliability_score", 100) < 80:
                insights.append(
                    f"🔧 {worst_agent[0]} has the lowest reliability score ({worst_agent[1]['reliability_score']}%)."
                )
            
            # Most expensive agent
            most_expensive = max(agents.items(), key=lambda x: x[1].get("total_cost", 0))
            if most_expensive[1].get("total_cost", 0) > total_cost * 0.3:
                pct = round(most_expensive[1]["total_cost"] / max(total_cost, 0.001) * 100, 1)
                insights.append(f"💰 {most_expensive[0]} accounts for {pct}% of total cost.")
        
        # Tool failure insight
        tool_list = tools.get("tools", [])
        if tool_list:
            high_fail_tools = [t for t in tool_list if t.get("failures", 0) > 3]
            if high_fail_tools:
                worst = max(high_fail_tools, key=lambda x: x["failures"])
                insights.append(f"🛠️ Tool '{worst['name']}' has failed {worst['failures']} times.")
        
        # Token efficiency insight
        waste_pct = token_quality.get("waste_pct", 0)
        if waste_pct > 15:
            insights.append(f"🔴 {waste_pct}% of tokens were wasted on failed runs.")
        
        io_ratio = token_quality.get("io_ratio", 1)
        if io_ratio < 0.3:
            insights.append(f"📊 Low output/input ratio ({io_ratio}x) - prompts may be too verbose.")
        
        # Success rate insight
        success_rate = totals.get("success_rate", 100)
        if success_rate < 90:
            insights.append(f"📉 Overall success rate is {success_rate}% - consider investigating failures.")
        
        # Top failure agents
        top_failures = retries.get("top_failure_agents", {})
        if top_failures:
            top_agent = list(top_failures.keys())[0]
            count = top_failures[top_agent]
            if count > 3:
                insights.append(f"🚨 {top_agent} has failed {count} times across sessions.")
        
        return insights if insights else ["✅ Fleet is running healthy with no major issues detected."]

    # =========================================================================
    # MAIN API
    # =========================================================================
    
    def get_dashboard_metrics(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get comprehensive fleet telemetry (cached for 5 min)"""
        # Check cache
        if not force_refresh and self.cache_file.exists():
            try:
                cached = json.loads(self.cache_file.read_text())
                updated = datetime.fromisoformat(cached.get("last_updated", "2000-01-01T00:00:00"))
                if (datetime.now() - updated).total_seconds() < 300:
                    return cached
            except:
                pass
        
        # Regenerate full telemetry
        sessions = self.scan_sessions()
        
        metrics = {
            "last_updated": datetime.now().isoformat(),
            "totals": self.aggregate_fleet_overview(sessions),
            "agents": self.aggregate_agent_matrix(sessions),
            "temporal": self.aggregate_temporal(sessions),
            "retries": self.aggregate_retry_analytics(sessions),
            "tools": self.aggregate_tool_usage(sessions),
            "sources": self.aggregate_url_sources(sessions),
            "token_quality": self.aggregate_token_quality(sessions),
        }
        
        # Generate insights based on computed metrics
        metrics["insights"] = self.generate_insights(metrics)
        
        # Legacy compatibility
        metrics["by_agent"] = metrics["agents"]
        metrics["by_day"] = metrics["temporal"].get("daily", [])
        
        self.save_to_cache(metrics)
        return metrics
    
    def save_to_cache(self, metrics: Dict[str, Any]):
        """Write metrics to cache file"""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(json.dumps(metrics, indent=2))
        print(f"💾 Metrics cached to {self.cache_file}")


# Singleton instance
_aggregator = None

def get_aggregator() -> MetricsAggregator:
    global _aggregator
    if _aggregator is None:
        _aggregator = MetricsAggregator()
    return _aggregator
