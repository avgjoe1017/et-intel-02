# Week 5: Reporting & PDF Generation - Detailed Documentation

## Overview

Week 5 focuses on generating professional PDF intelligence briefs from analytics data. The system separates computation (BriefBuilder) from presentation (PDFRenderer), allowing briefs to be rendered in multiple formats.

**Status**: 🟡 In Progress

---

## Architecture

### Separation of Concerns

```
┌─────────────────────┐
│  BriefBuilder       │  ← Computes & assembles data
│  (Data Assembly)    │
└──────────┬──────────┘
           │ IntelligenceBriefData
           ↓
┌─────────────────────┐
│  PDFRenderer        │  ← Formats & renders PDF
│  (Presentation)     │
└─────────────────────┘
```

**Key Design Principle**: BriefBuilder creates pure data structures. PDFRenderer handles all formatting. This allows:
- Multiple output formats (PDF, JSON, Slack, Email)
- Easy testing (test data separately from rendering)
- Future extensibility (add HTML renderer, etc.)

---

## Components

### 1. BriefSection

A dataclass representing one section of the brief:

```python
@dataclass
class BriefSection:
    title: str
    items: List[Dict[str, Any]] = field(default_factory=list)
    summary: Optional[str] = None
```

**Usage**:
```python
section = BriefSection(
    title="Top Entities by Volume",
    items=[{'entity_name': 'Blake Lively', 'mention_count': 100}],
    summary="Blake Lively dominated with 100 mentions"
)
```

### 2. IntelligenceBriefData

The complete brief data structure:

```python
@dataclass
class IntelligenceBriefData:
    timeframe: Dict[str, datetime]
    topline_summary: Dict[str, Any]
    top_entities: BriefSection
    velocity_alerts: BriefSection
    storylines: BriefSection
    risk_signals: BriefSection
    metadata: Dict[str, Any]
```

**Features**:
- `to_dict()` method for JSON serialization
- All datetime/UUID values properly serialized
- Ready for multiple output formats

### 3. BriefBuilder

Composes analytics results into brief structure:

```python
class BriefBuilder:
    def __init__(self, analytics: AnalyticsService):
        self.analytics = analytics
    
    def build(
        self,
        start: datetime,
        end: datetime,
        platforms: Optional[List[str]] = None,
        focus_entities: Optional[List[uuid.UUID]] = None,
        top_entities_limit: int = 20
    ) -> IntelligenceBriefData:
        # Assembles all sections
```

**What it does**:
1. Queries top entities from AnalyticsService
2. Checks velocity for top entities
3. Counts comments and alerts
4. Generates executive summaries
5. Assembles all sections into IntelligenceBriefData

**Key Methods**:
- `build()`: Main method to create brief
- `_summarize_top_entities()`: Generates executive summary text

### 4. PDFRenderer

Renders IntelligenceBriefData as professional PDF:

```python
class PDFRenderer:
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self._setup_custom_styles()
    
    def render(
        self,
        brief: IntelligenceBriefData,
        filename: Optional[str] = None
    ) -> Path:
        # Creates PDF file
```

**Features**:
- Professional styling with custom colors
- Title page with timeframe
- Executive summary with metrics table
- Top entities table with sentiment scores
- Velocity alerts table with color coding
- Automatic filename generation
- Proper page breaks and formatting

**Custom Styles**:
- `CustomTitle`: Large, centered title
- `SectionTitle`: Section headings
- `Summary`: Summary text styling

---

## PDF Structure

### Title Page
- Main title: "ET Social Intelligence Brief"
- Timeframe: Start and end dates
- Generated timestamp
- Topline summary (comments, entities, alerts)

### Executive Summary
- Key metrics table:
  - Total Comments
  - Entities Tracked
  - Velocity Alerts
  - Critical Alerts (>50%)
- Key highlights text

### Top Entities Section
- Table with columns:
  - Rank
  - Entity Name
  - Type
  - Mentions
  - Avg Sentiment (color-coded)
  - Total Likes
- Summary text

### Velocity Alerts Section
- Table with columns:
  - Entity Name
  - Change % (color-coded)
  - Recent Sentiment
  - Previous Sentiment
  - Status (🚨 ALERT or ✓ Stable)
- Summary text

### Storylines Section
- Placeholder for future implementation
- Currently shows "No active storylines detected"

### Risk Signals Section
- Placeholder for future implementation
- Currently shows "No risk signals detected"

### Footer
- System version
- Generation timestamp
- Platforms analyzed

---

## CLI Command

### Usage

```bash
# Basic usage
python cli.py brief --start 2024-01-01 --end 2024-01-07

# With platform filter
python cli.py brief --start 2024-01-01 --end 2024-01-07 \
    --platforms instagram --platforms youtube

# With custom output filename
python cli.py brief --start 2024-01-01 --end 2024-01-07 \
    --output weekly_brief.pdf

# With JSON export
python cli.py brief --start 2024-01-01 --end 2024-01-07 --json
```

### Options

- `--start`: Start date (YYYY-MM-DD, required)
- `--end`: End date (YYYY-MM-DD, required)
- `--platforms`: Filter by platform (can specify multiple)
- `--output`: Custom PDF filename (auto-generated if not provided)
- `--json`: Also save brief data as JSON file

### Output

The command:
1. Builds brief data from analytics
2. Renders PDF to `reports/` directory
3. Optionally saves JSON file
4. Displays summary statistics
5. Shows path to generated PDF

**Example Output**:
```
📄 Generating intelligence brief...
   Period: 2024-01-01 to 2024-01-07

⏳ Building brief data...
⏳ Rendering PDF...

✓ Brief generated: reports/ET_Intelligence_Brief_20241124_143022.pdf

📊 Brief Summary:
   Total Comments: 1,234
   Entities Tracked: 15
   Velocity Alerts: 2
   Critical Alerts: 1

💡 Open PDF: reports/ET_Intelligence_Brief_20241124_143022.pdf
```

---

## Code Examples

### Building a Brief

```python
from datetime import datetime, timedelta
from et_intel_core.db import get_session
from et_intel_core.analytics import AnalyticsService
from et_intel_core.reporting import BriefBuilder

session = get_session()
analytics = AnalyticsService(session)
builder = BriefBuilder(analytics)

start = datetime(2024, 1, 1)
end = datetime(2024, 1, 7)

brief = builder.build(start, end)

# Access brief data
print(f"Total comments: {brief.topline_summary['total_comments']}")
print(f"Top entity: {brief.top_entities.items[0]['entity_name']}")
```

### Rendering PDF

```python
from pathlib import Path
from et_intel_core.reporting import PDFRenderer

renderer = PDFRenderer(Path('reports'))
pdf_path = renderer.render(brief, filename='my_brief.pdf')

print(f"PDF saved to: {pdf_path}")
```

### Exporting to JSON

```python
import json

brief_dict = brief.to_dict()
with open('brief.json', 'w') as f:
    json.dump(brief_dict, f, indent=2, default=str)
```

---

## Testing

Comprehensive test suite in `tests/test_reporting.py`:

### Test Coverage

1. **BriefSection Tests**
   - Creation with defaults
   - Creation with all fields

2. **IntelligenceBriefData Tests**
   - Creation
   - to_dict() serialization

3. **BriefBuilder Tests**
   - Creation
   - Building with empty database
   - Building with data
   - Summarizing entities

4. **PDFRenderer Tests**
   - Creation
   - Rendering PDF
   - Auto-filename generation
   - Extension handling
   - Section creation methods

### Running Tests

```bash
# Run all reporting tests
pytest tests/test_reporting.py -v

# Run with coverage
pytest tests/test_reporting.py --cov=et_intel_core.reporting
```

---

## Future Enhancements

### Charts (Planned)
- Sentiment trend charts (Plotly → PDF)
- Entity comparison charts
- Velocity visualization
- Time series plots

### Storylines (Planned)
- Detect recurring themes
- Track storyline evolution
- Identify emerging narratives

### Risk Signals (Planned)
- Toxicity detection
- Threat identification
- Harassment flags
- Doxxing warnings

### Multiple Formats
- HTML renderer for web viewing
- Email renderer for distribution
- Slack renderer for team updates
- CSV export for data analysis

---

## Files Created

### Core Module
- `et_intel_core/reporting/__init__.py` - Module exports
- `et_intel_core/reporting/brief_builder.py` - BriefBuilder and data structures
- `et_intel_core/reporting/pdf_renderer.py` - PDFRenderer implementation

### Tests
- `tests/test_reporting.py` - Comprehensive test suite

### Documentation
- `MD_DOCS/WEEK_5_REPORTING.md` - This file

---

## Dependencies

### Required
- `reportlab==4.0.7` - PDF generation
- `pandas` - Data manipulation (already in requirements)
- `datetime` - Date handling (stdlib)

### Optional (Future)
- `plotly==5.18.0` - Chart generation (already in requirements)
- `matplotlib==3.8.2` - Alternative charts (already in requirements)

---

## Key Design Decisions

### 1. Separation of Concerns
**Decision**: BriefBuilder creates data, PDFRenderer formats it.
**Rationale**: Allows multiple output formats, easier testing, better maintainability.

### 2. Dataclasses for Data Structures
**Decision**: Use Python dataclasses for BriefSection and IntelligenceBriefData.
**Rationale**: Clean, type-safe, easy to serialize, minimal boilerplate.

### 3. ReportLab for PDF
**Decision**: Use ReportLab instead of alternatives (WeasyPrint, pdfkit).
**Rationale**: Mature, well-documented, good control over layout, handles tables well.

### 4. Auto-filename Generation
**Decision**: Generate filenames with timestamp if not provided.
**Rationale**: Prevents overwriting, easy to track generation time.

### 5. JSON Export Option
**Decision**: Optional JSON export alongside PDF.
**Rationale**: Enables programmatic access, data analysis, integration with other tools.

---

## Troubleshooting

### PDF Generation Fails
**Issue**: `PermissionError` or `FileNotFoundError`
**Solution**: Ensure `reports/` directory exists and is writable

### Empty Brief
**Issue**: Brief shows no data
**Solution**: Check that:
- Data exists in the time window
- Entities are monitored
- Comments are enriched

### Velocity Alerts Missing
**Issue**: No velocity alerts in brief
**Solution**: 
- Ensure sufficient data (10+ comments per window)
- Check that entities have recent activity
- Verify velocity window (default 72 hours)

### Date Format Errors
**Issue**: `ValueError: time data does not match format`
**Solution**: Use YYYY-MM-DD format (e.g., 2024-01-01)

---

## Success Metrics

✅ **BriefBuilder**: Successfully assembles analytics into brief structure
✅ **PDFRenderer**: Generates professional PDFs with proper formatting
✅ **CLI Integration**: Brief command works with all options
✅ **Testing**: Comprehensive test coverage
✅ **Documentation**: Complete guide with examples

---

**Week 5 Status**: 🟡 In Progress

**Next**: Complete chart generation, final testing, documentation updates

---

*Last Updated: 2025-11-24*

