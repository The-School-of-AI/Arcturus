"""
Structured Decision Traces

Queryable structured records (not just logs) containing:
- Goal, page snapshot, elements considered (with scores)
- Element selected, reasoning, confidence, action, outcome, duration
- Filterable and visualizable dashboards

Example query: "Show all decisions where confidence < 0.7"
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class DecisionStatus(Enum):
    """Outcome of decision"""
    SUCCESSFUL = "successful"
    FAILED = "failed"
    PENDING = "pending"
    REVERTED = "reverted"


@dataclass
class ElementScore:
    """Score for an element considered in decision"""
    element_id: str
    element_text: str
    element_type: str
    relevance_score: float
    confidence_score: float
    ranking: int  # Position in consideration order


@dataclass
class StructuredDecisionTrace:
    """
    Structured, queryable decision record.
    
    Not a log string - structured data for analytics and visualization.
    """
    id: str
    timestamp: datetime
    workflow_id: str
    session_id: str
    step_number: int
    
    # Goal and context
    goal: str
    page_url: str
    page_title: str
    page_snapshot_id: Optional[str] = None
    
    # Elements analysis
    elements_considered: List[ElementScore] = field(default_factory=list)
    element_selected_id: str = ""
    element_selected_text: str = ""
    
    # Reasoning
    reasoning: str = ""
    reasoning_steps: List[str] = field(default_factory=list)
    
    # Metrics
    overall_confidence: float = 0.0
    decision_latency_ms: int = 0
    tokens_used: int = 0
    
    # Action and outcome
    action_type: str = ""
    action_parameters: Dict[str, Any] = field(default_factory=dict)
    outcome: str = ""
    status: DecisionStatus = DecisionStatus.SUCCESSFUL
    
    # Recovery
    was_retried: bool = False
    retry_count: int = 0
    was_backtracked: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/querying"""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'workflow_id': self.workflow_id,
            'session_id': self.session_id,
            'step_number': self.step_number,
            'goal': self.goal,
            'page_url': self.page_url,
            'page_title': self.page_title,
            'elements_considered_count': len(self.elements_considered),
            'element_selected_id': self.element_selected_id,
            'reasoning_summary': self.reasoning[:200],
            'overall_confidence': self.overall_confidence,
            'decision_latency_ms': self.decision_latency_ms,
            'tokens_used': self.tokens_used,
            'action_type': self.action_type,
            'outcome': self.outcome[:100],
            'status': self.status.value,
            'was_retried': self.was_retried,
            'retry_count': self.retry_count,
            'was_backtracked': self.was_backtracked,
        }


class DecisionTracer:
    """
    Captures and stores structured decision traces.
    
    Enables powerful querying: "Show decisions where confidence < 0.7 for site X"
    """
    
    def __init__(self):
        self.traces: List[StructuredDecisionTrace] = []
        self.traces_by_workflow: Dict[str, List[StructuredDecisionTrace]] = {}
        self.traces_by_session: Dict[str, List[StructuredDecisionTrace]] = {}
    
    def record_decision(
        self,
        workflow_id: str,
        session_id: str,
        step_number: int,
        goal: str,
        page_url: str,
        page_title: str,
        elements_considered: List[ElementScore],
        element_selected_id: str,
        element_selected_text: str,
        reasoning: str,
        reasoning_steps: List[str],
        confidence: float,
        action_type: str,
        action_parameters: Dict[str, Any],
        latency_ms: int,
        tokens_used: int,
    ) -> str:
        """
        Record a structured decision trace.
        
        Returns:
            Decision trace ID
        """
        trace_id = f"dt_{len(self.traces)}"
        
        trace = StructuredDecisionTrace(
            id=trace_id,
            timestamp=datetime.utcnow(),
            workflow_id=workflow_id,
            session_id=session_id,
            step_number=step_number,
            goal=goal,
            page_url=page_url,
            page_title=page_title,
            elements_considered=elements_considered,
            element_selected_id=element_selected_id,
            element_selected_text=element_selected_text,
            reasoning=reasoning,
            reasoning_steps=reasoning_steps,
            overall_confidence=confidence,
            action_type=action_type,
            action_parameters=action_parameters,
            decision_latency_ms=latency_ms,
            tokens_used=tokens_used,
        )
        
        # Store
        self.traces.append(trace)
        
        # Index by workflow and session
        if workflow_id not in self.traces_by_workflow:
            self.traces_by_workflow[workflow_id] = []
        self.traces_by_workflow[workflow_id].append(trace)
        
        if session_id not in self.traces_by_session:
            self.traces_by_session[session_id] = []
        self.traces_by_session[session_id].append(trace)
        
        return trace_id
    
    def update_decision_outcome(
        self,
        trace_id: str,
        outcome: str,
        status: DecisionStatus,
        was_retried: bool = False,
        was_backtracked: bool = False,
    ):
        """Update decision with outcome information"""
        for trace in self.traces:
            if trace.id == trace_id:
                trace.outcome = outcome
                trace.status = status
                trace.was_retried = was_retried
                trace.was_backtracked = was_backtracked
                return
    
    def query_traces(
        self,
        workflow_id: Optional[str] = None,
        session_id: Optional[str] = None,
        min_confidence: Optional[float] = None,
        max_confidence: Optional[float] = None,
        action_type: Optional[str] = None,
        status: Optional[DecisionStatus] = None,
        page_url: Optional[str] = None,
    ) -> List[StructuredDecisionTrace]:
        """
        Query traces with filters.
        
        Example: traces.query_traces(min_confidence=0.0, max_confidence=0.7)
                 -> all low-confidence decisions
        """
        results = self.traces
        
        if workflow_id:
            results = [t for t in results if t.workflow_id == workflow_id]
        
        if session_id:
            results = [t for t in results if t.session_id == session_id]
        
        if min_confidence is not None:
            results = [t for t in results if t.overall_confidence >= min_confidence]
        
        if max_confidence is not None:
            results = [t for t in results if t.overall_confidence <= max_confidence]
        
        if action_type:
            results = [t for t in results if t.action_type == action_type]
        
        if status:
            results = [t for t in results if t.status == status]
        
        if page_url:
            results = [t for t in results if page_url in t.page_url]
        
        return results
    
    def get_low_confidence_decisions(self, threshold: float = 0.7) -> List[Dict]:
        """Get all decisions below confidence threshold"""
        traces = self.query_traces(max_confidence=threshold)
        return [t.to_dict() for t in traces]
    
    def get_failed_decisions(self) -> List[Dict]:
        """Get all decisions that resulted in failure"""
        traces = self.query_traces(status=DecisionStatus.FAILED)
        return [t.to_dict() for t in traces]
    
    def get_retry_statistics(self) -> Dict[str, Any]:
        """Get statistics on retries"""
        retried = [t for t in self.traces if t.was_retried]
        
        return {
            'total_decisions': len(self.traces),
            'retried_decisions': len(retried),
            'retry_rate': len(retried) / len(self.traces) if self.traces else 0,
            'total_retries': sum(t.retry_count for t in retried),
            'avg_retry_count': sum(t.retry_count for t in retried) / len(retried) if retried else 0,
        }
    
    def get_confidence_histogram(self, bins: int = 10) -> Dict[str, int]:
        """Get distribution of confidence scores"""
        histogram = {f"{i}-{i+10}%": 0 for i in range(0, 100, 10)}
        
        for trace in self.traces:
            bin_label = f"{int(trace.overall_confidence * 100) // 10 * 10}-{int(trace.overall_confidence * 100) // 10 * 10 + 10}%"
            if bin_label in histogram:
                histogram[bin_label] += 1
        
        return histogram
    
    def get_action_type_distribution(self) -> Dict[str, int]:
        """Get distribution of action types"""
        distribution = {}
        
        for trace in self.traces:
            action = trace.action_type
            distribution[action] = distribution.get(action, 0) + 1
        
        return distribution
    
    def get_site_failure_analysis(self) -> Dict[str, Any]:
        """Analyze which sites/pages cause most failures"""
        failures_by_site = {}
        
        for trace in self.traces:
            if trace.status == DecisionStatus.FAILED:
                site = trace.page_url.split('/')[2]  # Extract domain
                if site not in failures_by_site:
                    failures_by_site[site] = 0
                failures_by_site[site] += 1
        
        return sorted(failures_by_site.items(), key=lambda x: x[1], reverse=True)
    
    def export_traces_csv(self, traces: Optional[List[StructuredDecisionTrace]] = None) -> str:
        """Export traces as CSV"""
        import csv
        from io import StringIO
        
        traces = traces or self.traces
        output = StringIO()
        
        writer = csv.DictWriter(output, fieldnames=[
            'id', 'timestamp', 'workflow_id', 'step_number', 'goal',
            'page_url', 'elements_considered', 'confidence', 'action_type',
            'status', 'was_retried', 'decision_latency_ms',
        ])
        
        writer.writeheader()
        for trace in traces:
            writer.writerow({
                'id': trace.id,
                'timestamp': trace.timestamp.isoformat(),
                'workflow_id': trace.workflow_id,
                'step_number': trace.step_number,
                'goal': trace.goal,
                'page_url': trace.page_url,
                'elements_considered': len(trace.elements_considered),
                'confidence': trace.overall_confidence,
                'action_type': trace.action_type,
                'status': trace.status.value,
                'was_retried': trace.was_retried,
                'decision_latency_ms': trace.decision_latency_ms,
            })
        
        return output.getvalue()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics"""
        successful = [t for t in self.traces if t.status == DecisionStatus.SUCCESSFUL]
        failed = [t for t in self.traces if t.status == DecisionStatus.FAILED]
        
        return {
            'total_traces': len(self.traces),
            'successful': len(successful),
            'failed': len(failed),
            'success_rate': len(successful) / len(self.traces) if self.traces else 0,
            'avg_confidence': sum(t.overall_confidence for t in self.traces) / len(self.traces) if self.traces else 0,
            'avg_latency_ms': sum(t.decision_latency_ms for t in self.traces) / len(self.traces) if self.traces else 0,
            'total_tokens_used': sum(t.tokens_used for t in self.traces),
        }
