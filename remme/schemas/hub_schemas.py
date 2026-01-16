"""
Pydantic Schemas for UserModel Hubs

Defines the data models for:
- PreferencesHub (behavioral policies)
- OperatingContextHub (environment facts)
- SoftIdentityHub (personalization signals)
- EvidenceLog (audit trail)
- BeliefUpdateEngine (confidence/decay config)
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


# =============================================================================
# Common Types
# =============================================================================

class ConfidenceField(BaseModel):
    """A field with confidence tracking."""
    value: Optional[Any] = None
    confidence: float = 0.0
    inferred_from: List[str] = Field(default_factory=list)
    last_seen_at: Optional[datetime] = None


class ScopedValue(BaseModel):
    """A value that can vary by scope/domain."""
    default: Optional[Any] = None
    by_scope: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    last_seen_at: Optional[datetime] = None


class HubMeta(BaseModel):
    """Common metadata for all hubs."""
    confidence: float = 0.0
    evidence_count: int = 0
    last_updated: Optional[datetime] = None
    created_at: Optional[datetime] = None


# =============================================================================
# PreferencesHub Schemas
# =============================================================================

class StableDefaults(BaseModel):
    """User's stable default preferences."""
    default_language: Optional[str] = "python"
    default_output_format: Optional[str] = "markdown"
    default_verbosity: Optional[str] = "concise"
    default_decision_style: Optional[str] = "single_best"
    default_iteration_style: Optional[str] = "fast_iterations"
    default_feedback_style: Optional[str] = "implicit_ok"


class EmojiPolicy(BaseModel):
    """Emoji usage preferences."""
    mode: Optional[str] = "minimal"
    allowed_when: List[str] = Field(default_factory=lambda: ["casual_chat"])
    disallowed_when: List[str] = Field(default_factory=lambda: ["work_artifacts"])


class ChunkingPolicy(BaseModel):
    """Code/content chunking preferences."""
    max_lines: int = 400
    prefer_full_files: bool = True
    chunk_strategy: Optional[str] = "logical_sections"


class CitationsPosture(BaseModel):
    """Citation style preferences."""
    default: Optional[str] = "minimal"
    by_scope: Dict[str, str] = Field(default_factory=dict)
    style: Optional[str] = "minimal_inline"


class QuestionsPolicy(BaseModel):
    """Clarification question preferences."""
    clarifications: Optional[str] = "minimize"
    ask_only_if_blocked: bool = True
    if_ambiguous: Optional[str] = "best_effort_assumptions"
    when_high_risk: Optional[str] = "ask_before_irreversible"
    batch_questions: bool = True


class OptionsPresentation(BaseModel):
    """How to present options/alternatives."""
    default: Optional[str] = "single_best"
    max_options: int = 3
    offer_options_when: List[str] = Field(default_factory=lambda: ["high_uncertainty"])


class OutputContract(BaseModel):
    """Output formatting and structure preferences."""
    verbosity: ScopedValue = Field(default_factory=lambda: ScopedValue(default="concise"))
    format_defaults: ScopedValue = Field(default_factory=lambda: ScopedValue(default="markdown"))
    structure_rules: List[str] = Field(default_factory=list)
    tone_constraints: List[str] = Field(default_factory=list)
    emoji_policy: EmojiPolicy = Field(default_factory=EmojiPolicy)
    chunking: ChunkingPolicy = Field(default_factory=ChunkingPolicy)
    citations_posture: CitationsPosture = Field(default_factory=CitationsPosture)
    questions_policy: QuestionsPolicy = Field(default_factory=QuestionsPolicy)
    options_presentation: OptionsPresentation = Field(default_factory=OptionsPresentation)


class AvoidPatterns(BaseModel):
    """Patterns to avoid in responses."""
    phrases: List[str] = Field(default_factory=list)
    moves: List[str] = Field(default_factory=list)


class NeverUse(BaseModel):
    """Words/phrases to never use."""
    words: List[str] = Field(default_factory=list)
    openings: List[str] = Field(default_factory=list)
    closings: List[str] = Field(default_factory=list)


class AntiPreferences(BaseModel):
    """Things to avoid."""
    avoid_patterns: AvoidPatterns = Field(default_factory=AvoidPatterns)
    never_use: NeverUse = Field(default_factory=NeverUse)


class FrameworkPrefs(BaseModel):
    """Framework preferences."""
    frontend: List[str] = Field(default_factory=list)
    backend: List[str] = Field(default_factory=list)
    testing: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class PackageManagerPrefs(BaseModel):
    """Package manager preferences."""
    python: Optional[str] = "uv"
    javascript: Optional[str] = "pnpm"
    confidence: float = 0.0


class StylePreferences(BaseModel):
    """Coding style preferences."""
    type_annotations: bool = True
    comment_density: Optional[str] = "low"
    docstring_style: Optional[str] = "google"
    line_length: int = 88
    import_style: Optional[str] = "absolute"


class ToolingDefaults(BaseModel):
    """Default tooling preferences."""
    frameworks: FrameworkPrefs = Field(default_factory=FrameworkPrefs)
    package_manager: PackageManagerPrefs = Field(default_factory=PackageManagerPrefs)
    validation: List[str] = Field(default_factory=lambda: ["pydantic"])
    testing: List[str] = Field(default_factory=lambda: ["pytest"])
    preferred_libraries: Dict[str, str] = Field(default_factory=dict)
    style_preferences: StylePreferences = Field(default_factory=StylePreferences)


class AutonomySettings(BaseModel):
    """What actions are allowed without confirmation."""
    create_files: Optional[str] = "allowed"
    modify_files: Optional[str] = "allowed"
    delete_files: Optional[str] = "confirm_first"
    run_shell: Optional[str] = "allowed"
    destructive_actions: Optional[str] = "confirm_first"
    web_browse: Optional[str] = "allowed"
    install_packages: Optional[str] = "allowed"
    git_operations: Optional[str] = "safe_only"


class RiskTolerance(BaseModel):
    """Risk tolerance by scope."""
    default: Optional[str] = "moderate"
    by_scope: Dict[str, str] = Field(default_factory=lambda: {"security": "conservative"})


class AutonomyAndRisk(BaseModel):
    """Autonomy and risk preferences."""
    autonomy: AutonomySettings = Field(default_factory=AutonomySettings)
    risk_tolerance: RiskTolerance = Field(default_factory=RiskTolerance)
    confirmation_gates: List[str] = Field(default_factory=list)


class CodingContracts(BaseModel):
    """Coding-specific preferences."""
    deliverable_preference: Optional[str] = "full_file"
    error_handling_style: Optional[str] = "explicit"
    async_preference: Optional[str] = "async_first"
    testing_expectations: Optional[str] = "unit_tests_required"


class PreferencesHubSchema(BaseModel):
    """Complete PreferencesHub schema."""
    hub_type: str = "PreferencesHub"
    schema_version: str = "1.0"
    stable_defaults: StableDefaults = Field(default_factory=StableDefaults)
    output_contract: OutputContract = Field(default_factory=OutputContract)
    anti_preferences: AntiPreferences = Field(default_factory=AntiPreferences)
    tooling_defaults: ToolingDefaults = Field(default_factory=ToolingDefaults)
    autonomy_and_risk: AutonomyAndRisk = Field(default_factory=AutonomyAndRisk)
    coding_contracts: CodingContracts = Field(default_factory=CodingContracts)
    meta: HubMeta = Field(default_factory=HubMeta)


# =============================================================================
# OperatingContextHub Schemas
# =============================================================================

class OSInfo(ConfidenceField):
    """Operating system information."""
    value: Optional[str] = None
    version: Optional[str] = None


class HardwareCPU(ConfidenceField):
    """CPU information."""
    architecture: Optional[str] = None
    brand: Optional[str] = None
    cores: Optional[int] = None


class HardwareRAM(ConfidenceField):
    """RAM information."""
    value: Optional[int] = None  # GB


class HardwareGPU(ConfidenceField):
    """GPU information."""
    value: Optional[str] = None
    vram_gb: Optional[int] = None


class HardwareInfo(BaseModel):
    """Hardware specs."""
    cpu: HardwareCPU = Field(default_factory=HardwareCPU)
    ram_gb: HardwareRAM = Field(default_factory=HardwareRAM)
    gpu: HardwareGPU = Field(default_factory=HardwareGPU)


class NetworkInfo(BaseModel):
    """Network constraints."""
    restricted: ConfidenceField = Field(default_factory=ConfidenceField)
    vpn_required: bool = False
    proxy_configured: bool = False


class EnvironmentInfo(BaseModel):
    """System environment."""
    os: OSInfo = Field(default_factory=OSInfo)
    shell: ConfidenceField = Field(default_factory=ConfidenceField)
    location_region: ConfidenceField = Field(default_factory=ConfidenceField)
    timezone: ConfidenceField = Field(default_factory=ConfidenceField)
    hardware: HardwareInfo = Field(default_factory=HardwareInfo)
    network: NetworkInfo = Field(default_factory=NetworkInfo)


class LanguagePrefs(ConfidenceField):
    """Programming language preferences."""
    ranked: List[str] = Field(default_factory=list)


class PackageManagerInfo(ConfidenceField):
    """Package manager info per language."""
    pass


class EditorInfo(BaseModel):
    """Editor/IDE info."""
    primary: Optional[str] = None
    extensions: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class VersionControlInfo(BaseModel):
    """Version control setup."""
    tool: Optional[str] = "git"
    hosting: Optional[str] = None
    workflow: Optional[str] = None
    confidence: float = 0.0


class DeveloperPosture(BaseModel):
    """Developer environment and preferences."""
    primary_languages: LanguagePrefs = Field(default_factory=LanguagePrefs)
    secondary_languages: List[str] = Field(default_factory=list)
    package_managers: Dict[str, ConfidenceField] = Field(default_factory=dict)
    editor_ide: EditorInfo = Field(default_factory=EditorInfo)
    version_control: VersionControlInfo = Field(default_factory=VersionControlInfo)


class RuntimeEnv(BaseModel):
    """Runtime environment info."""
    version: Optional[str] = None
    confidence: float = 0.0


class RuntimeEnvironments(BaseModel):
    """Available runtime environments."""
    python: RuntimeEnv = Field(default_factory=RuntimeEnv)
    node: RuntimeEnv = Field(default_factory=RuntimeEnv)
    docker: RuntimeEnv = Field(default_factory=RuntimeEnv)
    kubernetes: RuntimeEnv = Field(default_factory=RuntimeEnv)


class AssumptionLimits(BaseModel):
    """What to avoid assuming."""
    avoid_cuda_unless_confirmed: bool = True
    avoid_docker_unless_confirmed: bool = True
    avoid_cloud_cli_unless_confirmed: bool = True
    prefer_cross_platform_commands: bool = True


class ServiceAvailability(ConfidenceField):
    """Service availability status."""
    available: Optional[bool] = None


class ServiceAccess(BaseModel):
    """External service access."""
    cloud_providers: Dict[str, ServiceAvailability] = Field(default_factory=dict)
    databases: Dict[str, ServiceAvailability] = Field(default_factory=dict)
    ai_services: Dict[str, ServiceAvailability] = Field(default_factory=dict)


class OperatingContextHubSchema(BaseModel):
    """Complete OperatingContextHub schema."""
    hub_type: str = "OperatingContextHub"
    schema_version: str = "1.0"
    environment: EnvironmentInfo = Field(default_factory=EnvironmentInfo)
    developer_posture: DeveloperPosture = Field(default_factory=DeveloperPosture)
    runtime_environments: RuntimeEnvironments = Field(default_factory=RuntimeEnvironments)
    assumption_limits: AssumptionLimits = Field(default_factory=AssumptionLimits)
    service_access: ServiceAccess = Field(default_factory=ServiceAccess)
    meta: HubMeta = Field(default_factory=HubMeta)


# =============================================================================
# SoftIdentityHub Schemas
# =============================================================================

class DietaryStyle(ConfidenceField):
    """Dietary style preferences."""
    pass


class CuisineAffinities(BaseModel):
    """Cuisine preferences."""
    likes: List[str] = Field(default_factory=list)
    dislikes: List[str] = Field(default_factory=list)
    favorites: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    last_seen_at: Optional[datetime] = None


class FoodRestrictions(BaseModel):
    """Food restrictions."""
    medical: List[str] = Field(default_factory=list)
    religious: List[str] = Field(default_factory=list)
    ethical: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class FoodAndDining(BaseModel):
    """Food preferences."""
    dietary_style: DietaryStyle = Field(default_factory=DietaryStyle)
    cuisine_affinities: CuisineAffinities = Field(default_factory=CuisineAffinities)
    restrictions: FoodRestrictions = Field(default_factory=FoodRestrictions)


class PetAffinity(ConfidenceField):
    """Pet affinity."""
    specific_breeds: List[str] = Field(default_factory=list)


class PetOwnership(BaseModel):
    """Pet ownership status."""
    current: Optional[bool] = None
    past: Optional[bool] = None
    pet_names: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    last_seen_at: Optional[datetime] = None


class PetsAndAnimals(BaseModel):
    """Pet preferences."""
    affinity: PetAffinity = Field(default_factory=PetAffinity)
    ownership: PetOwnership = Field(default_factory=PetOwnership)


class ActivityLevel(ConfidenceField):
    """Activity level."""
    activities: List[str] = Field(default_factory=list)


class LifestyleAndWellness(BaseModel):
    """Lifestyle preferences."""
    activity_level: ActivityLevel = Field(default_factory=ActivityLevel)
    sleep_rhythm: ConfidenceField = Field(default_factory=ConfidenceField)
    travel_style: ConfidenceField = Field(default_factory=ConfidenceField)
    work_life_balance: ConfidenceField = Field(default_factory=ConfidenceField)


class MediaPrefs(BaseModel):
    """Media preferences."""
    genres: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class MediaAndEntertainment(BaseModel):
    """Media preferences."""
    music: MediaPrefs = Field(default_factory=MediaPrefs)
    books: MediaPrefs = Field(default_factory=MediaPrefs)
    movies_tv: MediaPrefs = Field(default_factory=MediaPrefs)
    podcasts: MediaPrefs = Field(default_factory=MediaPrefs)
    content_depth: ConfidenceField = Field(default_factory=ConfidenceField)


class CommunicationStyle(BaseModel):
    """Communication style preferences."""
    humor_tolerance: ConfidenceField = Field(default_factory=ConfidenceField)
    small_talk_tolerance: ConfidenceField = Field(default_factory=ConfidenceField)
    metaphor_preference: ConfidenceField = Field(default_factory=ConfidenceField)
    formality_preference: ConfidenceField = Field(default_factory=ConfidenceField)


class InterestsAndHobbies(BaseModel):
    """User interests."""
    professional_interests: List[str] = Field(default_factory=list)
    personal_hobbies: List[str] = Field(default_factory=list)
    learning_interests: List[str] = Field(default_factory=list)
    side_projects: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class ProfessionalContext(BaseModel):
    """Professional context."""
    industry: ConfidenceField = Field(default_factory=ConfidenceField)
    role_type: ConfidenceField = Field(default_factory=ConfidenceField)
    experience_level: ConfidenceField = Field(default_factory=ConfidenceField)
    team_size: ConfidenceField = Field(default_factory=ConfidenceField)


class SoftIdentityUsageRules(BaseModel):
    """Usage rules for soft identity data."""
    allowed_in: List[str] = Field(default_factory=lambda: ["examples", "casual_chat", "analogies"])
    never_affects: List[str] = Field(default_factory=lambda: ["tool_selection", "risk_decisions", "security_choices"])
    never_infer_identity: bool = True
    never_assume_values: bool = True
    never_use_for_persuasion: bool = True


class SoftIdentityHubSchema(BaseModel):
    """Complete SoftIdentityHub schema."""
    hub_type: str = "SoftIdentityHub"
    schema_version: str = "1.0"
    food_and_dining: FoodAndDining = Field(default_factory=FoodAndDining)
    pets_and_animals: PetsAndAnimals = Field(default_factory=PetsAndAnimals)
    lifestyle_and_wellness: LifestyleAndWellness = Field(default_factory=LifestyleAndWellness)
    media_and_entertainment: MediaAndEntertainment = Field(default_factory=MediaAndEntertainment)
    communication_style: CommunicationStyle = Field(default_factory=CommunicationStyle)
    interests_and_hobbies: InterestsAndHobbies = Field(default_factory=InterestsAndHobbies)
    professional_context: ProfessionalContext = Field(default_factory=ProfessionalContext)
    usage_rules: SoftIdentityUsageRules = Field(default_factory=SoftIdentityUsageRules)
    extras: Dict[str, Any] = Field(default_factory=dict)
    meta: HubMeta = Field(default_factory=HubMeta)


# =============================================================================
# EvidenceLog Schemas
# =============================================================================

class EvidenceSource(BaseModel):
    """Source of an evidence event."""
    type: str  # conversation|notes|browser|project|system|news|manual
    reference: Optional[str] = None  # session_id, file_path, or url
    context: Optional[str] = None


class SignalType(BaseModel):
    """Type and strength of a signal."""
    category: str  # explicit_preference|implicit_behavior|correction|rejection|acceptance|context_signal|system_observation
    strength: str = "medium"  # strong|medium|weak


class DerivedUpdate(BaseModel):
    """An update derived from evidence."""
    target_hub: str  # PreferencesHub|OperatingContextHub|SoftIdentityHub
    target_path: str  # dot-separated path like "output_contract.verbosity.by_scope.coding"
    operation: str  # set|increment|decrement|add_to_list|remove_from_list
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    confidence_delta: float = 0.1


class EvidenceEvent(BaseModel):
    """A single evidence event."""
    event_id: str
    timestamp: datetime
    source: EvidenceSource
    signal_type: SignalType
    raw_excerpt: str
    excerpt_hash: Optional[str] = None
    derived_updates: List[DerivedUpdate] = Field(default_factory=list)
    confidence_impact: float = 0.1
    decay_group: str = "recency_sensitive"  # stable|recency_sensitive|fast_decay


class SignalTypeTaxonomy(BaseModel):
    """Configuration for signal types."""
    description: str
    indicators: List[str] = Field(default_factory=list)
    base_confidence: float = 0.3
    decay_rate: str = "medium"


class RetentionPolicy(BaseModel):
    """Evidence retention policy."""
    store_full_excerpts: bool = False
    max_excerpt_length: int = 200
    max_events: int = 1000
    prune_strategy: str = "oldest_first"
    merge_similar_events: bool = True
    archive_after_days: int = 90


class EvidenceLogMeta(BaseModel):
    """Evidence log metadata."""
    total_events: int = 0
    events_by_source: Dict[str, int] = Field(default_factory=dict)
    events_by_type: Dict[str, int] = Field(default_factory=dict)
    last_pruned_at: Optional[datetime] = None


class EvidenceLogSchema(BaseModel):
    """Complete EvidenceLog schema."""
    hub_type: str = "EvidenceLog"
    schema_version: str = "1.0"
    events: List[EvidenceEvent] = Field(default_factory=list)
    signal_type_taxonomy: Dict[str, SignalTypeTaxonomy] = Field(default_factory=dict)
    retention_policy: RetentionPolicy = Field(default_factory=RetentionPolicy)
    meta: EvidenceLogMeta = Field(default_factory=EvidenceLogMeta)


# =============================================================================
# BeliefUpdateEngine Schemas
# =============================================================================

class PriorityLevel(BaseModel):
    """Priority level configuration."""
    weight: float = 0.6
    immune_to_decay: bool = False
    requires_explicit_override: bool = False


class ConfidenceConfig(BaseModel):
    """Confidence update configuration."""
    base: float = 0.3
    increment_per_evidence: float = 0.1
    decrement_on_contradiction: float = 0.15
    cap: float = 0.95
    floor: float = 0.1


class RecencyDecayConfig(BaseModel):
    """Recency decay configuration."""
    enabled: bool = True
    half_life_days: int = 90
    exclude_priorities: List[str] = Field(default_factory=list)
    minimum_after_decay: float = 0.2


class EvidenceThresholds(BaseModel):
    """Evidence thresholds for confidence levels."""
    tentative: int = 1
    established: int = 3
    confident: int = 5


class HubConfig(BaseModel):
    """Configuration for a specific hub."""
    confidence: ConfidenceConfig = Field(default_factory=ConfidenceConfig)
    recency_decay: RecencyDecayConfig = Field(default_factory=RecencyDecayConfig)
    evidence_thresholds: EvidenceThresholds = Field(default_factory=EvidenceThresholds)


class GlobalRules(BaseModel):
    """Global belief update rules."""
    conflict_resolution_order: List[str] = Field(default_factory=lambda: [
        "prefer_higher_priority",
        "prefer_more_specific_scope",
        "prefer_more_recent",
        "prefer_higher_confidence"
    ])
    default_priority: str = "soft"
    priority_levels: Dict[str, PriorityLevel] = Field(default_factory=lambda: {
        "hard": PriorityLevel(weight=1.0, immune_to_decay=True, requires_explicit_override=True),
        "soft": PriorityLevel(weight=0.6),
        "situational": PriorityLevel(weight=0.3)
    })
    minimum_evidence_to_persist: int = 1
    contradiction_handling: str = "create_scoped_variant"


class ScopeHierarchy(BaseModel):
    """Scope hierarchy configuration."""
    levels: List[str] = Field(default_factory=lambda: ["global", "domain", "project", "session"])
    inheritance: str = "narrower_overrides_broader"
    domains: List[str] = Field(default_factory=lambda: [
        "coding", "teaching", "planning", "research", "writing", "debugging", "ops"
    ])


class BeliefUpdateEngineSchema(BaseModel):
    """Complete BeliefUpdateEngine schema."""
    engine_type: str = "BeliefUpdateEngine"
    schema_version: str = "1.0"
    global_rules: GlobalRules = Field(default_factory=GlobalRules)
    per_hub_config: Dict[str, HubConfig] = Field(default_factory=lambda: {
        "PreferencesHub": HubConfig(
            confidence=ConfidenceConfig(base=0.5, cap=0.95, floor=0.2),
            recency_decay=RecencyDecayConfig(half_life_days=90, exclude_priorities=["hard"])
        ),
        "OperatingContextHub": HubConfig(
            confidence=ConfidenceConfig(base=0.4, increment_per_evidence=0.15, decrement_on_contradiction=0.25),
            recency_decay=RecencyDecayConfig(half_life_days=120)
        ),
        "SoftIdentityHub": HubConfig(
            confidence=ConfidenceConfig(base=0.3, cap=0.8),
            recency_decay=RecencyDecayConfig(half_life_days=60)
        )
    })
    scope_hierarchy: ScopeHierarchy = Field(default_factory=ScopeHierarchy)


# =============================================================================
# BrowsingHistoryStore Schemas
# =============================================================================

class BrowsingVisit(BaseModel):
    """A single browsing visit."""
    visit_id: str
    url: str
    title: Optional[str] = None
    domain: Optional[str] = None
    source: str = "direct_browse"  # news_feed|direct_browse|search_result|link_click
    timestamp: datetime
    dwell_time_seconds: Optional[int] = None
    scroll_depth: Optional[float] = None
    content_extracted: bool = False
    content_hash: Optional[str] = None


class ContentCacheItem(BaseModel):
    """Cached content from a visited page."""
    content_id: str
    visit_id: str
    url: str
    title: Optional[str] = None
    extracted_text: Optional[str] = None
    word_count: Optional[int] = None
    extracted_at: datetime
    categories: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    summary: Optional[str] = None


class BrowsingAggregations(BaseModel):
    """Aggregated browsing statistics."""
    domains_by_visit_count: Dict[str, int] = Field(default_factory=dict)
    categories_by_time_spent: Dict[str, int] = Field(default_factory=dict)
    reading_times_by_hour: Dict[int, int] = Field(default_factory=dict)
    content_depth_distribution: Dict[str, int] = Field(default_factory=dict)


class BrowsingRetentionPolicy(BaseModel):
    """Browsing history retention policy."""
    max_visits: int = 10000
    max_content_items: int = 500
    prune_visits_after_days: int = 90
    prune_content_after_days: int = 30


class BrowsingHistoryStoreSchema(BaseModel):
    """Complete BrowsingHistoryStore schema."""
    store_type: str = "BrowsingHistoryStore"
    schema_version: str = "1.0"
    visits: List[BrowsingVisit] = Field(default_factory=list)
    content_cache: List[ContentCacheItem] = Field(default_factory=list)
    aggregations: BrowsingAggregations = Field(default_factory=BrowsingAggregations)
    retention_policy: BrowsingRetentionPolicy = Field(default_factory=BrowsingRetentionPolicy)
