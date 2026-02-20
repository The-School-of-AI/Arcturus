# P03 Page Schema

This file documents the canonical page JSON schema used by the Spark page generator.

Example page JSON (canonical):

```json
{
  "id": "page_abc123",
  "title": "Market Analysis: Electric Scooters 2026",
  "query": "electric scooter market 2026 forecast",
  "template": "topic_overview",
  "sections": [
    {
      "id": "s_overview_1",
      "type": "overview",
      "title": "Executive summary",
      "blocks": [
         {"kind":"markdown","text":"High level summary..."},
         {"kind":"citation","ids":["T001"]}
      ],
      "widgets": [],
      "metadata": {}
    },
    {
      "id":"s_data_1",
      "type":"data",
      "title":"Market numbers",
      "blocks":[ {"kind":"table","columns":["metric","value"],"rows":[["CAGR","20.9%"]]} ],
      "charts": [{"chart_id":"c1","chart_data":{}}],
      "metadata": {}
    }
  ],
  "citations": {
    "T001": {"url":"https://...","title":"Report 2025","snippet":"...","credibility":0.9}
  },
  "metadata": {"created_by":"dev","created_at":"2026-02-17T00:00:00Z","versions":[]}
}
```

Notes:
- `sections` is a list of ordered section objects. Each section contains `blocks` which are small typed blocks (markdown, table, chart, citation, etc.).
- `citations` is a top-level mapping from citation id -> metadata. Section blocks reference citation ids.
