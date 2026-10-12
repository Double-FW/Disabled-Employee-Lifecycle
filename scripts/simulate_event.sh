#!/usr/bin/env bash
# Simulate a synthetic event to a local agent endpoint
# Usage: ./scripts/simulate_event.sh tests/synthetic-events/example_inaccessible_assessment.json

AGENT_URL=${AGENT_URL:-http://localhost:8080/events}
EVENT_FILE=${1:-tests/synthetic-events/example_inaccessible_assessment.json}

if [ ! -f "$EVENT_FILE" ]; then
  echo "Event file not found: $EVENT_FILE"
  exit 1
fi

curl -X POST -H "Content-Type: application/json" --data-binary @"$EVENT_FILE" "$AGENT_URL"
