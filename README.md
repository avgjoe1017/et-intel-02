# ET Social Intelligence System - V2

A production-grade social intelligence platform that converts ET's comment sections into strategic intelligence.

## Core Philosophy

> **Intelligence is derived, not stored. Comments are atoms. Everything else is a view.**

## Features

- **Multi-source ingestion**: ESUIT, Apify, CSV formats
- **Entity extraction**: spaCy-powered NER with custom catalog
- **Sentiment analysis**: Hybrid approach (rule-based → LLM escalation)
- **Velocity alerts**: 30% sentiment change in 72hrs = red flag
- **Entity-targeted sentiment**: "I love Ryan but hate Blake" = 2 distinct signals
- **Extensible signals**: Add emotion/toxicity/risk without schema migrations
- **Professional reports**: PDF briefs with charts and insights
- **Interactive dashboard**: Streamlit-based exploration

## Architecture

```
┌─────────────────────────────────────┐
│   Core Library (et_intel_core)     │
│                                     │
│  Ingestion → Enrichment → Analytics│
│       ↓           ↓           ↓    │
│     Posts → Comments → Signals     │
└─────────────────────────────────────┘
         ↓                    ↓
    CLI Tools          Streamlit Dashboard
```

**Key Innovation**: The **signals table** - intelligence as derived data, not stored properties.

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+

### Installation

```bash
# Clone repository
git clone <repo-url>
cd et-intel-02

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm

# Set up environment
cp .env.example .env
# Edit .env with your database credentials and API keys

# Initialize database
alembic upgrade head
```

### Usage

```bash
# 1. Initialize database
python cli.py init

# 2. Load seed entities
python cli.py seed-entities

# 3. Ingest comments from CSV
python cli.py ingest --source esuit --file data/comments.csv

# 4. Extract entities and sentiment
python cli.py enrich

# 5. Check status
python cli.py status

# 6. Review discovered entities
python cli.py review-entities --min-mentions 10

# 7. Add entity to monitoring
python cli.py add-entity "Taylor Swift" --type person --aliases "T-Swift" "Tay"

# 8. Generate intelligence brief
python cli.py brief --start 2024-01-01 --end 2024-01-07 --output weekly_brief.pdf

# 9. Launch interactive dashboard
streamlit run dashboard.py
```

## Project Structure

```
et-intel-02/
├── et_intel_core/          # Core library
│   ├── models/             # SQLAlchemy models
│   ├── services/           # Business logic services
│   ├── sources/            # Ingestion adapters
│   ├── nlp/                # NLP components
│   ├── analytics/          # Analytics queries
│   ├── reporting/          # Brief builder & PDF renderer
│   └── db.py               # Database connection
├── alembic/                # Database migrations
├── tests/                  # Unit tests
├── cli.py                  # Command-line interface
├── dashboard.py            # Streamlit dashboard
├── data/                   # Sample data files
├── reports/                # Generated reports
└── MD_DOCS/                # Supplemental documentation
```

## Development

### Running Tests

```bash
pytest tests/ -v --cov=et_intel_core
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Code Quality

```bash
# Format code
black .

# Lint
flake8 et_intel_core/

# Type check
mypy et_intel_core/
```

## Technology Stack

- **Language**: Python 3.11+
- **Database**: PostgreSQL 15
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Alembic
- **Validation**: Pydantic v2
- **CLI**: Click
- **Dashboard**: Streamlit
- **NLP**: spaCy 3.7
- **Sentiment**: TextBlob + OpenAI (optional)
- **Reporting**: ReportLab + Plotly

## Documentation

- [Architecture Document](ET_Intelligence_Rebuild_Architecture.md) - Complete system design
- [Progress Log](PROGRESS.md) - Build progress and decisions
- [Setup Guide](SETUP.md) - Step-by-step setup instructions
- [Quick Reference](MD_DOCS/QUICK_REFERENCE.md) - CLI commands cheat sheet
- [Production Instructions](PRODUCTION_INSTRUCTIONS.md) - Deployment guide

### Weekly Guides
- [Week 1: Foundation](MD_DOCS/WEEK_1_FOUNDATION.md) - Database & ingestion
- [Week 2: NLP Layer](MD_DOCS/WEEK_2_NLP_LAYER.md) - Entity extraction & sentiment
- [Week 3: Analytics](MD_DOCS/WEEK_3_ANALYTICS.md) - Metrics & queries
- [Week 4: CLI Polish](MD_DOCS/WEEK_4_CLI_POLISH.md) - User experience & testing
- [Week 5: Reporting](MD_DOCS/WEEK_5_REPORTING.md) - PDF generation & brief builder

## Development Status

✅ **Week 1**: Foundation (Database, Models, Ingestion)
✅ **Week 2**: NLP Layer (Entity Extraction, Sentiment Analysis)
✅ **Week 3**: Analytics (Velocity, History, Top Entities)
✅ **Week 4**: CLI Polish (UX, Error Handling, Testing)
✅ **Week 5**: Reporting (PDF Generation, Brief Builder)
🔜 **Week 6**: Dashboard (Streamlit UI)
🔜 **Week 7**: Production Prep (Docker, Deployment)
🔜 **Week 8**: Polish & Deploy

## License

Proprietary - All Rights Reserved

## Contact

For questions or support, contact the development team.

# et-intel-02
