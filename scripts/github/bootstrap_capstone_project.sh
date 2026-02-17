#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Usage: scripts/github/bootstrap_capstone_project.sh <owner> <owner/repo> [project_title]"
  echo "Example: scripts/github/bootstrap_capstone_project.sh theschoolofai theschoolofai/Arcturus \"Arcturus Capstone 15 Projects\""
  exit 1
fi

OWNER="$1"
REPO="$2"
TITLE="${3:-Arcturus Capstone 15 Projects}"

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) is required."
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "GitHub auth not configured. Run: gh auth login"
  exit 1
fi

TMP_CREATE="$(mktemp)"

gh project create --owner "$OWNER" --title "$TITLE" --format json > "$TMP_CREATE"

PROJECT_NUMBER="$(python - <<'PY' "$TMP_CREATE"
import json, sys
obj = json.load(open(sys.argv[1], 'r', encoding='utf-8'))
print(obj['number'])
PY
)"
PROJECT_URL="$(python - <<'PY' "$TMP_CREATE"
import json, sys
obj = json.load(open(sys.argv[1], 'r', encoding='utf-8'))
print(obj.get('url', ''))
PY
)"

echo "Created project #${PROJECT_NUMBER}: ${PROJECT_URL}"

# Link repository to the project
if gh project link "$PROJECT_NUMBER" --owner "$OWNER" --repo "$REPO" >/dev/null 2>&1; then
  echo "Linked project to repository ${REPO}"
else
  echo "Warning: could not link repository automatically. You can link it manually from the project UI."
fi

# Create core tracking fields
create_field() {
  local name="$1"
  local data_type="$2"
  local options="${3:-}"
  if [[ -n "$options" ]]; then
    gh project field-create "$PROJECT_NUMBER" --owner "$OWNER" --name "$name" --data-type "$data_type" --single-select-options "$options" >/dev/null
  else
    gh project field-create "$PROJECT_NUMBER" --owner "$OWNER" --name "$name" --data-type "$data_type" >/dev/null
  fi
  echo "Added field: $name"
}

create_field "Track" "SINGLE_SELECT" "P01,P02,P03,P04,P05,P06,P07,P08,P09,P10,P11,P12,P13,P14,P15"
create_field "Status" "SINGLE_SELECT" "Todo,In Progress,In Review,Blocked,Done"
create_field "Student IDs" "TEXT"
create_field "Lead" "TEXT"
create_field "Gate Check" "TEXT"
create_field "Start Date" "DATE"
create_field "Due Date" "DATE"

# Seed 15 draft items
add_item() {
  local title="$1"
  local body="$2"
  gh project item-create "$PROJECT_NUMBER" --owner "$OWNER" --title "$title" --body "$body" >/dev/null
  echo "Added item: $title"
}

add_item "P01 Nexus - Omni-Channel Gateway" "Owner team: TBD\nCharter: CAPSTONE/project_charters/P01_nexus_omni_channel_communication_gateway.md\nGate: p01-nexus-gateway"
add_item "P02 Oracle - AI Search and Research" "Owner team: TBD\nCharter: CAPSTONE/project_charters/P02_oracle_ai_powered_search_research_engine.md\nGate: p02-oracle-research"
add_item "P03 Spark - Synthesized Content Pages" "Owner team: TBD\nCharter: CAPSTONE/project_charters/P03_spark_synthesized_content_pages_sparkpages.md\nGate: p03-spark-pages"
add_item "P04 Forge - Docs Slides Sheets Studio" "Owner team: TBD\nCharter: CAPSTONE/project_charters/P04_forge_ai_document_slides_sheets_studio.md\nGate: p04-forge-studio"
add_item "P05 Chronicle - Session Tracking and Rewind" "Owner team: TBD\nCharter: CAPSTONE/project_charters/P05_chronicle_ai_session_tracking_reproducibility.md\nGate: p05-chronicle-replay"
add_item "P06 Canvas - Live Visual Workspace" "Owner team: TBD\nCharter: CAPSTONE/project_charters/P06_canvas_live_visual_workspace_a2ui.md\nGate: p06-canvas-runtime"
add_item "P07 Echo - Voice Layer" "Owner team: TBD\nCharter: CAPSTONE/project_charters/P07_echo_voice_first_interaction_layer.md\nGate: p07-echo-voice"
add_item "P08 Legion - Multi-Agent Swarm" "Owner team: TBD\nCharter: CAPSTONE/project_charters/P08_legion_multi_agent_swarm_orchestration.md\nGate: p08-legion-swarm"
add_item "P09 Bazaar - Skills Marketplace" "Owner team: TBD\nCharter: CAPSTONE/project_charters/P09_bazaar_skills_agent_marketplace.md\nGate: p09-bazaar-marketplace"
add_item "P10 Phantom - Browser Agent" "Owner team: TBD\nCharter: CAPSTONE/project_charters/P10_phantom_autonomous_browser_agent.md\nGate: p10-phantom-browser"
add_item "P11 Mnemo - Memory and Knowledge Graph" "Owner team: TBD\nCharter: CAPSTONE/project_charters/P11_mnemo_real_time_memory_knowledge_graph.md\nGate: p11-mnemo-memory"
add_item "P12 Aegis - Safety and Trust Layer" "Owner team: TBD\nCharter: CAPSTONE/project_charters/P12_aegis_guardrails_safety_trust_layer.md\nGate: p12-aegis-safety"
add_item "P13 Orbit - Mobile and Cross-Platform" "Owner team: TBD\nCharter: CAPSTONE/project_charters/P13_orbit_mobile_cross_platform_experience.md\nGate: p13-orbit-mobile"
add_item "P14 Watchtower - Ops Dashboard" "Owner team: TBD\nCharter: CAPSTONE/project_charters/P14_watchtower_admin_observability_operations_dashboard.md\nGate: p14-watchtower-ops"
add_item "P15 Gateway - API Integration Hub" "Owner team: TBD\nCharter: CAPSTONE/project_charters/P15_gateway_api_platform_integration_hub.md\nGate: p15-gateway-api"

rm -f "$TMP_CREATE"

echo "Bootstrap complete."
echo "Project URL: $PROJECT_URL"
echo "Project Number: $PROJECT_NUMBER"
