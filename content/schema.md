# P03 Page Schema

This file documents the canonical page JSON schema used by the Spark page generator.

## Enhanced Schema (Phase 2)

Phase 2 adds support for:
- Multiple chart types (bar, line, pie, radar, scatter)
- Media blocks (images, videos)
- Highlight blocks for key metrics
- Insight blocks for data analysis
- Enhanced table metadata
- Comprehensive chart configurations

Example page JSON (Phase 2 enhanced):

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
      "title": "Executive Summary", 
      "blocks": [
        {
          "kind": "markdown",
          "text": "# Executive Summary: Electric Scooter Market\n\nThis analysis synthesizes information from 3 authoritative sources..."
        },
        {
          "kind": "highlight",
          "metric": "Market Growth Rate",
          "value": "28.5%",
          "source": "Industry Research Report 2026",
          "style": "metric-card"
        },
        {
          "kind": "media",
          "media_type": "image",
          "url": "https://example.org/images/market_chart.png",
          "title": "Market Growth Visualization",
          "description": "Visual representation of market growth trends",
          "thumbnail": "https://example.org/thumbnails/chart_thumb.png",
          "source": "https://example.org/research-source"
        },
        {
          "kind": "citation", 
          "ids": ["T001", "T002", "T003"]
        }
      ],
      "widgets": [],
      "metadata": {
        "key_metrics_count": 4,
        "sources_synthesized": 3,
        "enhanced": true
      }
    },
    {
      "id": "s_data_1",
      "type": "data",
      "title": "Data & Visualizations",
      "blocks": [
        {
          "kind": "table",
          "title": "Market Statistics",
          "columns": ["Metric", "2024", "2025", "2026 (Forecast)"],
          "rows": [
            ["Market Size ($B)", "12.4", "15.8", "20.3"],
            ["Growth Rate (%)", "18.5", "27.4", "28.5"]
          ],
          "metadata": {
            "source": "Market Research Institute",
            "url": "https://example.org/research"
          }
        },
        {
          "kind": "media",
          "media_type": "video",
          "url": "https://example.org/analysis.mp4",
          "title": "Market Analysis Video",
          "description": "Expert analysis of market trends",
          "thumbnail": "https://example.org/video_thumb.png",
          "duration": "5:42",
          "source": "https://example.org/video-source"
        }
      ],
      "charts": [
        {
          "chart_id": "bar_12345678",
          "type": "bar",
          "title": "Market Size Growth",
          "chart_data": {
            "labels": ["2024", "2025", "2026"],
            "datasets": [{
              "label": "Market Size ($B)",
              "data": [12.4, 15.8, 20.3],
              "backgroundColor": "rgba(54, 162, 235, 0.6)",
              "borderColor": "rgba(54, 162, 235, 1)",
              "borderWidth": 1
            }]
          },
          "config": {
            "responsive": true,
            "plugins": {"legend": {"display": true}},
            "scales": {"y": {"beginAtZero": true}}
          }
        },
        {
          "chart_id": "pie_87654321",
          "type": "pie",
          "title": "Market Share Distribution",
          "chart_data": {
            "labels": ["North America", "Europe", "Asia Pacific"],
            "datasets": [{
              "data": [35.2, 28.7, 31.1],
              "backgroundColor": [
                "rgba(255, 99, 132, 0.8)",
                "rgba(54, 162, 235, 0.8)",
                "rgba(255, 205, 86, 0.8)"
              ]
            }]
          },
          "config": {
            "responsive": true,
            "plugins": {"legend": {"position": "right"}}
          }
        }
      ],
      "metadata": {
        "tables_count": 1,
        "charts_count": 2,
        "media_count": 1,
        "enhanced": true
      }
    }
  ],
  "citations": {
    "T001": {
      "url": "https://example.org/research-2026",
      "title": "Electric Scooter Market Report 2026",
      "snippet": "Comprehensive market analysis showing 28.5% growth...",
      "credibility": 0.95
    },
    "T002": {
      "url": "https://example.org/regional-analysis",
      "title": "Regional Market Distribution Study", 
      "snippet": "Geographic analysis of market penetration...",
      "credibility": 0.90
    }
  },
  "metadata": {
    "created_by": "dev",
    "created_at": "2026-02-28T10:30:00Z",
    "versions": [],
    "phase": "2"
  }
}
```

## Block Types Reference

### Core Blocks
- **markdown**: Rich text content with Markdown formatting
- **table**: Tabular data with optional metadata  
- **citation**: Reference to sources in page citations

### Phase 2 Enhanced Blocks
- **highlight**: Key metric cards with styling
- **media**: Images and videos with metadata
- **insight**: Data analysis insights with credibility scoring

### Chart Types
- **bar**: Vertical bar charts for categorical comparisons
- **line**: Line charts for trends over time
- **pie**: Pie charts for proportional data
- **radar**: Multi-dimensional comparison charts
- **scatter**: Scatter plots for correlation analysis

### Media Types
- **image**: Static images with thumbnails and descriptions
- **video**: Video content with duration and thumbnails

Notes:
- `sections` is a list of ordered section objects. Each section contains `blocks` and optional `charts`.
- `citations` is a top-level mapping from citation id → metadata. Section blocks reference citation ids.
- Phase 2 adds comprehensive chart support with Chart.js-compatible configurations.
- Media blocks include thumbnail support and source attribution.
- Enhanced metadata tracking for analytics and debugging.
