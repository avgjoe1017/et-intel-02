#!/usr/bin/env python
"""
ET Social Intelligence CLI

Command-line interface for the ET Intelligence system.
"""

import click
from pathlib import Path
import json
from datetime import datetime, timedelta

from et_intel_core.db import get_session, init_db
from et_intel_core.services import IngestionService, EnrichmentService
from et_intel_core.sources import ESUITSource, ApifySource
from et_intel_core.models import MonitoredEntity, DiscoveredEntity, EntityType
from et_intel_core.nlp import EntityExtractor, get_sentiment_provider


@click.group()
@click.version_option(version="2.0.0")
def cli():
    """ET Social Intelligence CLI - V2"""
    pass


@cli.command()
def init():
    """Initialize the database (create tables)."""
    click.echo("Initializing database...")
    try:
        init_db()
        click.echo("✓ Database initialized successfully")
    except Exception as e:
        click.echo(f"✗ Error initializing database: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option(
    '--source',
    type=click.Choice(['esuit', 'apify']),
    required=True,
    help='Data source format'
)
@click.option(
    '--file',
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help='Path to CSV file'
)
def ingest(source: str, file: Path):
    """Ingest comments from CSV file."""
    click.echo(f"Ingesting from {source} file: {file}")
    
    try:
        # Create appropriate source
        if source == 'esuit':
            src = ESUITSource(file)
        else:
            src = ApifySource(file)
        
        # Get database session
        session = get_session()
        
        try:
            # Ingest
            ingestion = IngestionService(session)
            stats = ingestion.ingest(src)
            
            # Display results
            click.echo("\n✓ Ingestion complete!")
            click.echo(f"  Posts created: {stats['posts_created']}")
            click.echo(f"  Posts updated: {stats['posts_updated']}")
            click.echo(f"  Comments created: {stats['comments_created']}")
            click.echo(f"  Comments updated: {stats['comments_updated']}")
            
        finally:
            session.close()
            
    except Exception as e:
        click.echo(f"\n✗ Error during ingestion: {e}", err=True)
        raise click.Abort()


@cli.command()
def status():
    """Show database status."""
    from et_intel_core.models import Post, Comment, ExtractedSignal
    
    session = get_session()
    try:
        post_count = session.query(Post).count()
        comment_count = session.query(Comment).count()
        entity_count = session.query(MonitoredEntity).count()
        signal_count = session.query(ExtractedSignal).count()
        discovered_count = session.query(DiscoveredEntity).count()
        
        click.echo("\n📊 Database Status")
        click.echo("=" * 40)
        click.echo(f"Posts:              {post_count:,}")
        click.echo(f"Comments:           {comment_count:,}")
        click.echo(f"Monitored Entities: {entity_count:,}")
        click.echo(f"Extracted Signals:  {signal_count:,}")
        click.echo(f"Discovered Entities:{discovered_count:,}")
        click.echo("=" * 40)
        
    finally:
        session.close()


@cli.command()
@click.option(
    '--file',
    type=click.Path(exists=True, path_type=Path),
    default=Path('data/seed_entities.json'),
    help='Path to seed entities JSON file'
)
def seed_entities(file: Path):
    """Load seed entities from JSON file."""
    click.echo(f"Loading seed entities from {file}...")
    
    try:
        with open(file, 'r') as f:
            entities_data = json.load(f)
        
        session = get_session()
        try:
            created = 0
            skipped = 0
            
            for entity_data in entities_data:
                # Check if already exists
                existing = session.query(MonitoredEntity).filter_by(
                    name=entity_data['name']
                ).first()
                
                if existing:
                    click.echo(f"  ⊘ Skipped: {entity_data['name']} (already exists)")
                    skipped += 1
                    continue
                
                # Create entity
                entity = MonitoredEntity(
                    name=entity_data['name'],
                    canonical_name=entity_data['canonical_name'],
                    entity_type=EntityType[entity_data['entity_type'].upper()],
                    is_active=True,
                    aliases=entity_data.get('aliases', [])
                )
                session.add(entity)
                created += 1
                click.echo(f"  ✓ Added: {entity_data['name']}")
            
            session.commit()
            click.echo(f"\n✓ Loaded {created} entities ({skipped} skipped)")
            
        finally:
            session.close()
            
    except Exception as e:
        click.echo(f"\n✗ Error loading entities: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option('--since', type=str, help='Only enrich comments after this date (YYYY-MM-DD)')
@click.option('--days', type=int, help='Only enrich comments from last N days')
def enrich(since: str, days: int):
    """Extract entities and score sentiment."""
    click.echo("Starting enrichment...")
    
    session = get_session()
    try:
        # Load entity catalog
        entity_catalog = session.query(MonitoredEntity).filter_by(is_active=True).all()
        
        if not entity_catalog:
            click.echo("\n⚠️  No monitored entities found. Run 'seed-entities' first.")
            raise click.Abort()
        
        click.echo(f"  Loaded {len(entity_catalog)} monitored entities")
        
        # Set up enrichment
        extractor = EntityExtractor(entity_catalog)
        sentiment_provider = get_sentiment_provider()
        enrichment = EnrichmentService(session, extractor, sentiment_provider)
        
        # Parse date filter
        since_date = None
        if since:
            since_date = datetime.strptime(since, '%Y-%m-%d')
        elif days:
            since_date = datetime.utcnow() - timedelta(days=days)
        
        # Run enrichment
        click.echo("  Processing comments...")
        stats = enrichment.enrich_comments(since=since_date)
        
        # Display results
        click.echo("\n✓ Enrichment complete!")
        click.echo(f"  Comments processed: {stats['comments_processed']}")
        click.echo(f"  Signals created: {stats['signals_created']}")
        if stats['entities_discovered'] > 0:
            click.echo(f"  Entities discovered: {stats['entities_discovered']}")
            click.echo(f"    (Run 'review-entities' to see them)")
        
    finally:
        session.close()


@cli.command()
@click.option('--min-mentions', default=5, help='Minimum mentions to show')
def review_entities(min_mentions: int):
    """Review entities discovered by spaCy."""
    session = get_session()
    try:
        discovered = session.query(DiscoveredEntity).filter(
            DiscoveredEntity.reviewed == False,
            DiscoveredEntity.mention_count >= min_mentions
        ).order_by(DiscoveredEntity.mention_count.desc()).all()
        
        if not discovered:
            click.echo("\nNo new entities to review.")
            return
        
        click.echo(f"\n{len(discovered)} entities discovered:\n")
        
        for entity in discovered:
            click.echo(f"  {entity.name} ({entity.entity_type})")
            click.echo(f"    Mentions: {entity.mention_count}")
            click.echo(f"    First seen: {entity.first_seen_at.strftime('%Y-%m-%d')}")
            if entity.sample_mentions:
                click.echo(f"    Sample: {entity.sample_mentions[0]}")
            click.echo()
        
        click.echo("To add an entity to monitoring, use: python cli.py add-entity <name>")
        
    finally:
        session.close()


@cli.command()
@click.argument('name')
@click.option('--type', 'entity_type', type=click.Choice(['person', 'show', 'couple', 'brand']), default='person')
@click.option('--aliases', multiple=True, help='Alternate names')
def add_entity(name: str, entity_type: str, aliases: tuple):
    """Add entity to monitored list."""
    session = get_session()
    try:
        # Check if already exists
        existing = session.query(MonitoredEntity).filter_by(name=name).first()
        if existing:
            click.echo(f"✗ Entity '{name}' already exists")
            return
        
        entity = MonitoredEntity(
            name=name,
            canonical_name=name,
            entity_type=EntityType[entity_type.upper()],
            aliases=list(aliases) if aliases else [],
            is_active=True
        )
        
        session.add(entity)
        session.commit()
        
        click.echo(f"✓ Added {name} to monitored entities")
        
    finally:
        session.close()


if __name__ == '__main__':
    cli()

