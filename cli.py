#!/usr/bin/env python
"""
ET Social Intelligence CLI

Command-line interface for the ET Intelligence system.
"""

import click
from pathlib import Path
import json
import sys
import os
from datetime import datetime, timedelta

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from et_intel_core.db import get_session, init_db
from sqlalchemy import text
from et_intel_core.services import IngestionService, EnrichmentService
from et_intel_core.sources import ESUITSource, ApifySource, ApifyPostSource, ApifyMetadataSource

# Try to import merged adapter
try:
    from et_intel_core.sources.apify_merged import ApifyMergedAdapter
    HAS_MERGED = True
except ImportError:
    HAS_MERGED = False
from et_intel_core.sources.apify_live import ApifyLiveSource
from et_intel_core.models import MonitoredEntity, DiscoveredEntity, EntityType
from et_intel_core.nlp import EntityExtractor, get_sentiment_provider
from et_intel_core.analytics import AnalyticsService
from et_intel_core.reporting import BriefBuilder, PDFRenderer


# Color helpers
def success(msg):
    """Print success message in green."""
    return click.style(msg, fg='green', bold=True)

def error(msg):
    """Print error message in red."""
    return click.style(msg, fg='red', bold=True)

def warning(msg):
    """Print warning message in yellow."""
    return click.style(msg, fg='yellow', bold=True)

def info(msg):
    """Print info message in cyan."""
    return click.style(msg, fg='cyan')

def highlight(msg):
    """Print highlighted message in bright white."""
    return click.style(msg, fg='bright_white', bold=True)


@click.group()
@click.version_option(version="2.0.0", prog_name="ET Intelligence V2")
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.pass_context
def cli(ctx, verbose):
    """
    ET Social Intelligence CLI - V2
    
    Convert social media comments into strategic intelligence.
    
    \b
    Quick Start:
      1. python cli.py init
      2. python cli.py seed-entities
      3. python cli.py ingest --source esuit --file data.csv
      4. python cli.py enrich
      5. python cli.py top-entities
    
    \b
    Documentation: https://github.com/your-repo/docs
    """
    ctx.ensure_object(dict)
    ctx.obj['VERBOSE'] = verbose


@cli.command()
@click.option('--force', is_flag=True, help='Force initialization (drops existing tables)')
def init(force):
    """Initialize the database (create tables)."""
    click.echo(info("🔧 Initializing database..."))
    
    if force:
        if not click.confirm(warning("⚠️  This will DROP all existing tables. Continue?")):
            click.echo(info("Aborted."))
            return
        
        from et_intel_core.db import drop_db
        click.echo(info("  Dropping existing tables..."))
        try:
            drop_db()
            click.echo(success("  ✓ Tables dropped"))
        except Exception as e:
            click.echo(error(f"  ✗ Error dropping tables: {e}"))
            raise click.Abort()
    
    try:
        init_db()
        click.echo(success("✓ Database initialized successfully"))
        click.echo(info("\nNext steps:"))
        click.echo(info("  1. python cli.py seed-entities"))
        click.echo(info("  2. python cli.py ingest --source esuit --file data.csv"))
        click.echo(info("  3. python cli.py enrich"))
    except Exception as e:
        click.echo(error(f"✗ Error initializing database: {e}"))
        if "already exists" in str(e).lower():
            click.echo(warning("\nTip: Use --force to drop and recreate tables"))
        raise click.Abort()


@cli.command()
@click.option(
    '--source',
    type=click.Choice(['esuit', 'apify', 'apify-posts', 'apify-metadata']),
    required=True,
    help='Data source format (esuit: ESUIT CSV, apify: Apify comments CSV, apify-posts: Apify posts CSV, apify-metadata: Apify metadata CSV)'
)
@click.option(
    '--file',
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help='Path to CSV file'
)
@click.pass_context
def ingest(ctx, source: str, file: Path):
    """Ingest comments from CSV file."""
    verbose = ctx.obj.get('VERBOSE', False)
    
    click.echo(info(f"📥 Ingesting from {highlight(source)} file: {highlight(str(file))}"))
    
    # Validate file
    if not file.exists():
        click.echo(error(f"✗ File not found: {file}"))
        raise click.Abort()
    
    file_size = file.stat().st_size / 1024  # KB
    click.echo(info(f"   File size: {file_size:.1f} KB"))
    
    try:
        # Create appropriate source
        if source == 'esuit':
            src = ESUITSource(file)
        elif source == 'apify-posts':
            src = ApifyPostSource(file)
        elif source == 'apify-metadata':
            src = ApifyMetadataSource(file)
        else:
            # For Apify comments, check if we need post URL mapping
            # The raw dataset format needs media_id -> post_url mapping
            post_urls = None
            # Try to detect if it's raw format (has media_id column)
            try:
                import pandas as pd
                sample_df = pd.read_csv(file, nrows=1)
                if 'media_id' in sample_df.columns and 'url' not in sample_df.columns:
                    # Raw format - we'll need to extract post IDs from comments
                    # For now, we'll construct URLs from media_id
                    post_urls = {}
            except:
                pass
            src = ApifySource(file, post_urls=post_urls)
        
        # Get database session
        session = get_session()
        
        try:
            # Ingest with progress indication
            click.echo(info("\n⏳ Processing..."))
            ingestion = IngestionService(session)
            
            with click.progressbar(
                length=100,
                label='Ingesting',
                show_eta=False
            ) as bar:
                stats = ingestion.ingest(src)
                bar.update(100)
            
            # Display results
            click.echo(success("\n✓ Ingestion complete!"))
            click.echo(f"  Posts created:    {highlight(str(stats['posts_created']))}")
            click.echo(f"  Posts updated:    {highlight(str(stats['posts_updated']))}")
            click.echo(f"  Comments created: {highlight(str(stats['comments_created']))}")
            click.echo(f"  Comments updated: {highlight(str(stats['comments_updated']))}")
            
            total = stats['comments_created'] + stats['comments_updated']
            if total > 0:
                click.echo(info(f"\n💡 Next step: python cli.py enrich --days 1"))
            
        finally:
            session.close()
            
    except FileNotFoundError as e:
        click.echo(error(f"\n✗ File error: {e}"))
        raise click.Abort()
    except Exception as e:
        click.echo(error(f"\n✗ Error during ingestion: {e}"))
        if verbose:
            import traceback
            click.echo(error(traceback.format_exc()))
            raise click.Abort()


@cli.command(name='apify-scrape')
@click.option(
    '--token',
    envvar='APIFY_TOKEN',
    required=True,
    help='Apify API token (or set APIFY_TOKEN env var)'
)
@click.option(
    '--urls',
    required=True,
    help='Instagram post URLs to scrape (space-separated, or use --urls multiple times)'
)
@click.option(
    '--cookies',
    type=click.Path(exists=True, path_type=Path),
    help='Path to JSON file containing Instagram cookies (for cheaper scraping)'
)
@click.option(
    '--max-comments',
    default=2000,
    help='Maximum comments to scrape per post (default: 2000)'
)
@click.option(
    '--max-cost',
    type=float,
    help='Maximum cost per run in USD'
)
@click.option(
    '--parallel/--no-parallel',
    default=True,
    help='Process multiple posts in parallel (default: True)'
)
@click.option(
    '--max-workers',
    default=5,
    help='Maximum parallel workers (default: 5)'
)
@click.pass_context
def apify_scrape(ctx, token, urls, cookies, max_comments, max_cost, parallel, max_workers):
    """
    Scrape Instagram comments directly from Apify API.
    
    This command scrapes comments live from Apify and ingests them directly
    into the database. No CSV export step required.
    
    Examples:
        python cli.py apify-scrape --urls https://www.instagram.com/p/ABC123/
        python cli.py apify-scrape --urls URL1 URL2 --cookies cookies.json
        python cli.py apify-scrape --urls URL1 --max-comments 5000 --max-cost 10.0
    """
    verbose = ctx.obj.get('VERBOSE', False)
    
    # Parse URLs - support both space-separated and comma-separated
    # Click's multiple=True means if user passes --urls URL1 --urls URL2, we get a tuple
    # But if user passes --urls "URL1 URL2" (quoted), we get a single string
    if isinstance(urls, tuple):
        # Multiple --urls flags were used
        url_list = list(urls)
    elif isinstance(urls, str):
        # Single string - split by comma or whitespace
        if ',' in urls:
            url_list = [u.strip() for u in urls.split(',')]
        else:
            # Split by whitespace - this handles "URL1 URL2 URL3"
            url_list = urls.split()
    else:
        url_list = [str(urls)]
    
    # Clean up URLs - remove empty strings and trailing slashes
    url_list = [u.strip().rstrip('/') for u in url_list if u and u.strip()]
    
    if not url_list:
        click.echo(error("✗ No valid URLs provided"))
        raise click.Abort()
    
    # Show parsed URLs
    click.echo(info(f"🔍 Scraping {len(url_list)} post(s) from Apify..."))
    for i, url in enumerate(url_list, 1):
        click.echo(info(f"   {i}. {url}"))
    
    # Load cookies if provided
    cookies_json = None
    if cookies:
        try:
            with open(cookies, 'r', encoding='utf-8') as f:
                cookies_data = json.load(f)
                # Handle different cookie formats:
                # 1. Direct array: [{"name": "...", ...}, ...]
                # 2. Wrapped object: {"cookies": [{"name": "...", ...}, ...]}
                if isinstance(cookies_data, dict) and 'cookies' in cookies_data:
                    cookies_array = cookies_data['cookies']
                elif isinstance(cookies_data, list):
                    cookies_array = cookies_data
                else:
                    cookies_array = [cookies_data]
                
                # Apify expects cookies as a JSON string representation of the array
                # Convert the array to a JSON string
                cookies_json = json.dumps(cookies_array)
                click.echo(info(f"   Loaded {len(cookies_array)} cookies from {cookies}"))
        except Exception as e:
            click.echo(error(f"✗ Error loading cookies: {e}"))
            raise click.Abort()
    
    try:
        # Create Apify live source
        source = ApifyLiveSource(
            api_token=token,
            post_urls=url_list,
            max_comments=max_comments,
            cookies=cookies_json,
            max_cost=max_cost,
            parallel=parallel,
            max_workers=max_workers,
        )
        
        # Get database session
        session = get_session()
        
        try:
            # Ingest with progress indication
            click.echo(info("\n⏳ Scraping and ingesting..."))
            ingestion = IngestionService(session)
            
            with click.progressbar(
                length=100,
                label='Processing',
                show_eta=False
            ) as bar:
                stats = ingestion.ingest(source)
                bar.update(100)
            
            # Display results
            click.echo(success("\n✓ Scraping and ingestion complete!"))
            click.echo(f"  Posts created:    {highlight(str(stats['posts_created']))}")
            click.echo(f"  Posts updated:    {highlight(str(stats['posts_updated']))}")
            click.echo(f"  Comments created: {highlight(str(stats['comments_created']))}")
            click.echo(f"  Comments updated: {highlight(str(stats['comments_updated']))}")
            
            total = stats['comments_created'] + stats['comments_updated']
            if total > 0:
                click.echo(info(f"\n💡 Next step: python cli.py enrich --days 1"))
            
        finally:
            session.close()
            
    except Exception as e:
        click.echo(error(f"\n✗ Error during scraping: {e}"))
        if verbose:
            import traceback
            click.echo(error(traceback.format_exc()))
        raise click.Abort()


@cli.command()
@click.option('--detailed', is_flag=True, help='Show detailed breakdown')
def status(detailed):
    """Show database status and system health."""
    from et_intel_core.models import Post, Comment, ExtractedSignal
    
    session = get_session()
    try:
        # Get counts
        post_count = session.query(Post).count()
        comment_count = session.query(Comment).count()
        entity_count = session.query(MonitoredEntity).count()
        signal_count = session.query(ExtractedSignal).count()
        discovered_count = session.query(DiscoveredEntity).count()
        
        # Calculate enrichment percentage
        enriched_comments = session.execute(
            text("SELECT COUNT(DISTINCT comment_id) FROM extracted_signals")
        ).scalar() or 0
        enrichment_pct = (enriched_comments / comment_count * 100) if comment_count > 0 else 0
        
        # Display
        click.echo(info("\n📊 Database Status"))
        click.echo("=" * 60)
        click.echo(f"Posts:              {highlight(f'{post_count:,}')}")
        click.echo(f"Comments:           {highlight(f'{comment_count:,}')}")
        click.echo(f"Monitored Entities: {highlight(f'{entity_count:,}')}")
        click.echo(f"Extracted Signals:  {highlight(f'{signal_count:,}')}")
        click.echo(f"Discovered Entities:{highlight(f'{discovered_count:,}')}")
        click.echo("=" * 60)
        
        # Enrichment status
        if comment_count > 0:
            if enrichment_pct >= 90:
                status_msg = success(f"✓ {enrichment_pct:.1f}% enriched")
            elif enrichment_pct >= 50:
                status_msg = warning(f"⚠ {enrichment_pct:.1f}% enriched")
            else:
                status_msg = error(f"✗ {enrichment_pct:.1f}% enriched")
            
            click.echo(f"\nEnrichment: {status_msg}")
            
            if enrichment_pct < 100:
                unenriched = comment_count - enriched_comments
                click.echo(info(f"💡 Run: python cli.py enrich  ({unenriched:,} comments pending)"))
        
        # Detailed breakdown
        if detailed:
            click.echo(info("\n📈 Signal Breakdown:"))
            signal_types = session.execute(
                text("SELECT signal_type, COUNT(*) as count FROM extracted_signals GROUP BY signal_type")
            ).fetchall()
            for sig_type, count in signal_types:
                click.echo(f"  {sig_type}: {count:,}")
            
            if discovered_count > 0:
                click.echo(info(f"\n🔍 {discovered_count} entities discovered"))
                click.echo(info("   Run: python cli.py review-entities"))
        
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
    click.echo(info(f"📦 Loading seed entities from: {highlight(str(file))}\n"))
    
    try:
        # Validate file exists
        if not file.exists():
            click.echo(error(f"✗ File not found: {file}"))
            click.echo(info("   Expected location: data/seed_entities.json"))
            raise click.Abort()
        
        with open(file, 'r') as f:
            entities_data = json.load(f)
        
        click.echo(info(f"   Found {len(entities_data)} entities in file\n"))
        
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
                    click.echo(warning(f"  ⊘ Skipped: {entity_data['name']} (already exists)"))
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
                click.echo(success(f"  ✓ Added: {entity_data['name']}"))
            
            session.commit()
            
            if created > 0:
                click.echo(success(f"\n✓ Loaded {created} new entities"))
            if skipped > 0:
                click.echo(info(f"  ({skipped} already existed)"))
            
            if created > 0:
                click.echo(info("\n💡 Next step: python cli.py enrich"))
            
        finally:
            session.close()
            
    except json.JSONDecodeError as e:
        click.echo(error(f"\n✗ Invalid JSON file: {e}"))
        raise click.Abort()
    except Exception as e:
        click.echo(error(f"\n✗ Error loading entities: {e}"))
        raise click.Abort()


@cli.command()
@click.option('--since', type=str, help='Only enrich comments after this date (YYYY-MM-DD)')
@click.option('--days', type=int, help='Only enrich comments from last N days')
@click.pass_context
def enrich(ctx, since: str, days: int):
    """Extract entities and score sentiment."""
    verbose = ctx.obj.get('VERBOSE', False)
    
    click.echo(info("🧠 Starting enrichment..."))
    
    session = get_session()
    try:
        # Load entity catalog
        entity_catalog = session.query(MonitoredEntity).filter_by(is_active=True).all()
        
        if not entity_catalog:
            click.echo(warning("\n⚠️  No monitored entities found."))
            click.echo(info("   Run: python cli.py seed-entities"))
            raise click.Abort()
        
        click.echo(info(f"   Loaded {highlight(str(len(entity_catalog)))} monitored entities"))
        
        # Set up enrichment
        from et_intel_core.config import settings
        click.echo(info(f"   Sentiment backend: {highlight(settings.sentiment_backend)}"))
        
        extractor = EntityExtractor(entity_catalog)
        sentiment_provider = get_sentiment_provider()
        enrichment = EnrichmentService(session, extractor, sentiment_provider)
        
        # Parse date filter
        since_date = None
        if since:
            try:
                since_date = datetime.strptime(since, '%Y-%m-%d')
                click.echo(info(f"   Filtering: comments since {since}"))
            except ValueError:
                click.echo(error("✗ Invalid date format. Use YYYY-MM-DD"))
                raise click.Abort()
        elif days:
            since_date = datetime.utcnow() - timedelta(days=days)
            click.echo(info(f"   Filtering: last {days} days"))
        
        # Count comments to process
        from et_intel_core.models import Comment
        query = session.query(Comment)
        if since_date:
            query = query.filter(Comment.created_at >= since_date)
        total_comments = query.count()
        
        if total_comments == 0:
            click.echo(warning("\n⚠️  No comments to enrich"))
            return
        
        click.echo(info(f"   Found {highlight(str(total_comments))} comments to process\n"))
        
        # Run enrichment with progress bar
        with click.progressbar(
            length=total_comments,
            label='Processing',
            show_eta=True,
            show_percent=True
        ) as bar:
            stats = enrichment.enrich_comments(since=since_date)
            bar.update(stats['comments_processed'])
        
        # Display results
        click.echo(success("\n✓ Enrichment complete!"))
        click.echo(f"  Comments processed:  {highlight(str(stats['comments_processed']))}")
        click.echo(f"  Signals created:     {highlight(str(stats['signals_created']))}")
        
        if stats['entities_discovered'] > 0:
            click.echo(warning(f"  Entities discovered: {stats['entities_discovered']}"))
            click.echo(info("  💡 Run: python cli.py review-entities"))
        
        # Suggest next steps
        if stats['comments_processed'] > 0:
            click.echo(info("\n💡 Next steps:"))
            click.echo(info("   python cli.py top-entities"))
            click.echo(info("   python cli.py velocity \"Entity Name\""))
        
    except Exception as e:
        click.echo(error(f"\n✗ Error during enrichment: {e}"))
        if verbose:
            import traceback
            click.echo(error(traceback.format_exc()))
        raise click.Abort()
    finally:
        session.close()


@cli.command()
@click.option('--min-mentions', default=5, help='Minimum mentions to show')
@click.option('--limit', default=20, help='Maximum entities to show')
def review_entities(min_mentions: int, limit: int):
    """Review entities discovered by spaCy."""
    session = get_session()
    try:
        click.echo(info(f"🔍 Reviewing discovered entities (min {min_mentions} mentions)...\n"))
        
        discovered = session.query(DiscoveredEntity).filter(
            DiscoveredEntity.reviewed == False,
            DiscoveredEntity.mention_count >= min_mentions
        ).order_by(DiscoveredEntity.mention_count.desc()).limit(limit).all()
        
        if not discovered:
            click.echo(success("✓ No new entities to review. All caught up!"))
            return
        
        click.echo(highlight(f"Found {len(discovered)} entities:\n"))
        
        for idx, entity in enumerate(discovered, 1):
            click.echo(f"{idx}. {highlight(entity.name)} ({info(entity.entity_type)})")
            click.echo(f"   Mentions: {entity.mention_count}")
            click.echo(f"   First seen: {entity.first_seen_at.strftime('%Y-%m-%d')}")
            click.echo(f"   Last seen: {entity.last_seen_at.strftime('%Y-%m-%d')}")
            if entity.sample_mentions:
                sample = entity.sample_mentions[0][:100]
                click.echo(f"   Sample: \"{sample}...\"")
            click.echo()
        
        click.echo(info("💡 To add an entity to monitoring:"))
        click.echo(info("   python cli.py add-entity \"Entity Name\" --type person"))
        
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
        click.echo(info(f"➕ Adding entity: {highlight(name)}"))
        
        # Check if already exists
        existing = session.query(MonitoredEntity).filter_by(name=name).first()
        if existing:
            click.echo(error(f"✗ Entity '{name}' already exists"))
            # Handle entity_type - could be Enum or string
            entity_type_str = existing.entity_type.value if hasattr(existing.entity_type, 'value') else str(existing.entity_type)
            click.echo(info(f"   Type: {entity_type_str}"))
            click.echo(info(f"   Aliases: {', '.join(existing.aliases) if existing.aliases else 'None'}"))
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
        
        click.echo(success(f"✓ Added {name} to monitored entities"))
        click.echo(info(f"   Type: {entity_type}"))
        if aliases:
            click.echo(info(f"   Aliases: {', '.join(aliases)}"))
        
        # Mark as reviewed if it was discovered
        discovered = session.query(DiscoveredEntity).filter_by(name=name).first()
        if discovered:
            discovered.reviewed = True
            discovered.reviewed_at = datetime.utcnow()
            discovered.action_taken = "added_to_monitored"
            session.commit()
            click.echo(info("   ✓ Marked as reviewed in discovered entities"))
        
        click.echo(info("\n💡 Next step: python cli.py enrich --days 7"))
        
    finally:
        session.close()


@cli.command()
@click.option('--days', default=7, help='Number of days to analyze')
@click.option('--limit', default=10, help='Number of entities to show')
@click.option('--export', type=click.Path(), help='Export to CSV file')
def top_entities(days: int, limit: int, export: str):
    """Show top entities by mention count."""
    session = get_session()
    try:
        click.echo(info(f"📊 Analyzing top entities (last {days} days)...\n"))
        
        analytics = AnalyticsService(session)
        
        # Calculate time window
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get top entities
        df = analytics.get_top_entities((start_date, end_date), limit=limit)
        
        if len(df) == 0:
            click.echo(warning("⚠️  No entity data found for this time period."))
            click.echo(info("   Make sure you've run: python cli.py enrich"))
            return
        
        click.echo(highlight(f"Top {len(df)} Entities"))
        click.echo("=" * 80)
        
        for idx, (_, row) in enumerate(df.iterrows(), 1):
            # Sentiment emoji and color
            if row['avg_sentiment'] > 0.3:
                sentiment_emoji = "😊"
                sentiment_color = success(f"{row['avg_sentiment']:+.2f}")
            elif row['avg_sentiment'] > -0.3:
                sentiment_emoji = "😐"
                sentiment_color = warning(f"{row['avg_sentiment']:+.2f}")
            else:
                sentiment_emoji = "😞"
                sentiment_color = error(f"{row['avg_sentiment']:+.2f}")
            
            click.echo(f"\n{idx}. {highlight(row['entity_name'])} ({info(row['entity_type'])})")
            click.echo(f"   Mentions: {int(row['mention_count']):,}")
            click.echo(f"   Sentiment: {sentiment_color} {sentiment_emoji}")
            click.echo(f"   Total Likes: {int(row['total_likes']):,}")
            click.echo(f"   Weighted: {row['weighted_sentiment']:.2f}")
        
        click.echo("\n" + "=" * 80)
        
        # Export if requested
        if export:
            df.to_csv(export, index=False)
            click.echo(success(f"\n✓ Exported to {export}"))
        
        click.echo(info("\n💡 For detailed analysis:"))
        click.echo(info("   python cli.py velocity \"Entity Name\""))
        click.echo(info("   python cli.py sentiment-history \"Entity Name\""))
        
    finally:
        session.close()


@cli.command()
@click.argument('entity_name')
@click.option('--hours', default=72, help='Window size in hours')
def velocity(entity_name: str, hours: int):
    """Check velocity alert for an entity."""
    session = get_session()
    try:
        click.echo(info(f"🔍 Analyzing velocity for: {highlight(entity_name)}\n"))
        
        # Find entity
        entity = session.query(MonitoredEntity).filter_by(name=entity_name).first()
        if not entity:
            click.echo(error(f"✗ Entity '{entity_name}' not found"))
            click.echo(info("  Run: python cli.py top-entities"))
            
            # Suggest similar entities
            all_entities = session.query(MonitoredEntity).filter_by(is_active=True).all()
            similar = [e.name for e in all_entities if entity_name.lower() in e.name.lower()]
            if similar:
                click.echo(info(f"\n  Did you mean: {', '.join(similar[:5])}?"))
            return
        
        # Compute velocity
        analytics = AnalyticsService(session)
        velocity_data = analytics.compute_velocity(entity.id, window_hours=hours)
        
        if 'error' in velocity_data:
            click.echo(warning(f"⚠️  {velocity_data['error']}"))
            if 'recent_count' in velocity_data:
                click.echo(f"  Recent comments: {velocity_data['recent_count']}")
                click.echo(f"  Previous comments: {velocity_data['previous_count']}")
                click.echo(f"  Minimum required: {velocity_data['min_required']}")
            return
        
        # Display results
        click.echo(highlight(f"Velocity Analysis: {entity_name}"))
        click.echo("=" * 60)
        click.echo(f"Window: Last {highlight(str(hours))} hours")
        click.echo(f"Recent sentiment:   {velocity_data['recent_sentiment']:+.3f}")
        click.echo(f"Previous sentiment: {velocity_data['previous_sentiment']:+.3f}")
        
        # Color-code the change
        change = velocity_data['percent_change']
        if abs(change) > 30:
            change_str = error(f"{change:+.1f}%") if change < 0 else success(f"{change:+.1f}%")
            alert_msg = error("🚨 ALERT") if change < 0 else warning("⚠️  ALERT")
        else:
            change_str = warning(f"{change:+.1f}%") if abs(change) > 15 else info(f"{change:+.1f}%")
            alert_msg = success("✓ Stable")
        
        click.echo(f"Change:             {change_str} ({velocity_data['direction']})")
        click.echo(f"Sample sizes:       {velocity_data['recent_sample_size']} recent, {velocity_data['previous_sample_size']} previous")
        click.echo(f"\nStatus:             {alert_msg}")
        
        if velocity_data['alert']:
            click.echo(error(f"\n🚨 ALERT: Significant sentiment shift detected!"))
            click.echo(f"   {abs(velocity_data['percent_change']):.1f}% change exceeds 30% threshold")
        else:
            click.echo(success(f"\n✓ Stable: No significant sentiment shift"))
        
        click.echo("=" * 60)
        
    finally:
        session.close()


@cli.command()
@click.argument('entity_name')
@click.option('--days', default=30, help='Number of days of history')
@click.option('--export', type=click.Path(), help='Export to CSV file')
def sentiment_history(entity_name: str, days: int, export: str):
    """Show sentiment history for an entity."""
    session = get_session()
    try:
        click.echo(info(f"📈 Loading sentiment history for: {highlight(entity_name)}\n"))
        
        # Find entity
        entity = session.query(MonitoredEntity).filter_by(name=entity_name).first()
        if not entity:
            click.echo(error(f"✗ Entity '{entity_name}' not found"))
            click.echo(info("  Run: python cli.py top-entities"))
            return
        
        # Get history
        analytics = AnalyticsService(session)
        df = analytics.get_entity_sentiment_history(entity.id, days=days)
        
        if len(df) == 0:
            click.echo(warning(f"⚠️  No sentiment history found for {entity_name}"))
            click.echo(info(f"   Try a longer time window: --days {days * 2}"))
            return
        
        click.echo(highlight(f"Sentiment History: {entity_name} (Last {days} Days)"))
        click.echo("=" * 70)
        
        for _, row in df.iterrows():
            date_str = row['date'].strftime('%Y-%m-%d')
            sentiment = row['avg_sentiment']
            mentions = int(row['mention_count'])
            likes = int(row['total_likes'])
            
            # Visual bar with color
            bar_length = int(abs(sentiment) * 20)
            if sentiment > 0.3:
                bar = success("+" * bar_length)
            elif sentiment < -0.3:
                bar = error("-" * bar_length)
            else:
                bar = warning("=" * bar_length)
            
            sentiment_str = f"{sentiment:+.2f}"
            click.echo(f"{date_str}: {sentiment_str} {bar} ({mentions} mentions, {likes:,} likes)")
        
        click.echo("=" * 70)
        
        # Summary stats
        avg_sentiment = df['avg_sentiment'].mean()
        total_mentions = int(df['mention_count'].sum())
        total_likes = int(df['total_likes'].sum())
        
        click.echo(f"Average:        {avg_sentiment:+.2f}")
        click.echo(f"Total mentions: {total_mentions:,}")
        click.echo(f"Total likes:    {total_likes:,}")
        
        # Export if requested
        if export:
            df.to_csv(export, index=False)
            click.echo(success(f"\n✓ Exported to {export}"))
        
    finally:
        session.close()


@cli.command()
@click.option('--start', type=str, required=True, help='Start date (YYYY-MM-DD)')
@click.option('--end', type=str, required=True, help='End date (YYYY-MM-DD)')
@click.option('--platforms', multiple=True, help='Filter by platform (instagram, youtube, tiktok)')
@click.option('--output', type=click.Path(), help='Output PDF filename (auto-generated if not provided)')
@click.option('--json', 'save_json', is_flag=True, help='Also save brief data as JSON')
@click.pass_context
def brief(ctx, start: str, end: str, platforms: tuple, output: str, save_json: bool):
    """Generate intelligence brief PDF report."""
    verbose = ctx.obj.get('VERBOSE', False)
    
    try:
        # Parse dates
        start_date = datetime.strptime(start, '%Y-%m-%d')
        end_date = datetime.strptime(end, '%Y-%m-%d')
        
        if end_date < start_date:
            click.echo(error("✗ End date must be after start date"))
            raise click.Abort()
        
        click.echo(info(f"📄 Generating intelligence brief..."))
        click.echo(info(f"   Period: {start} to {end}"))
        
        if platforms:
            click.echo(info(f"   Platforms: {', '.join(platforms)}"))
        
        session = get_session()
        try:
            # Build brief
            analytics = AnalyticsService(session)
            builder = BriefBuilder(analytics)
            
            click.echo(info("\n⏳ Building brief data..."))
            brief_data = builder.build(
                start=start_date,
                end=end_date,
                platforms=list(platforms) if platforms else None,
                top_entities_limit=20
            )
            
            # Render PDF
            reports_dir = Path('reports')
            renderer = PDFRenderer(reports_dir)
            
            click.echo(info("⏳ Rendering PDF..."))
            pdf_path = renderer.render(brief_data, filename=output)
            
            click.echo(success(f"\n✓ Brief generated: {pdf_path}"))
            
            # Save JSON if requested
            if save_json:
                json_path = pdf_path.with_suffix('.json')
                import json
                with open(json_path, 'w') as f:
                    json.dump(brief_data.to_dict(), f, indent=2, default=str)
                click.echo(success(f"✓ Data saved: {json_path}"))
            
            # Show summary
            summary = brief_data.topline_summary
            click.echo(info("\n📊 Brief Summary:"))
            click.echo(f"   Total Comments: {summary['total_comments']:,}")
            click.echo(f"   Entities Tracked: {summary['total_entities']}")
            click.echo(f"   Velocity Alerts: {summary['velocity_alerts_count']}")
            click.echo(f"   Critical Alerts: {summary['critical_alerts']}")
            
            click.echo(info(f"\n💡 Open PDF: {pdf_path}"))
            
        finally:
            session.close()
            
    except ValueError as e:
        click.echo(error(f"✗ Invalid date format: {e}"))
        click.echo(info("   Use format: YYYY-MM-DD (e.g., 2024-01-01)"))
        raise click.Abort()
    except Exception as e:
        click.echo(error(f"\n✗ Error generating brief: {e}"))
        if verbose:
            import traceback
            click.echo(error(traceback.format_exc()))
        raise click.Abort()


@cli.command()
def version():
    """Show version and system information."""
    import sys
    import platform
    from sqlalchemy import __version__ as sqlalchemy_version
    import spacy
    
    click.echo(info("\n🎯 ET Social Intelligence System"))
    click.echo("=" * 60)
    click.echo(f"Version:        {highlight('2.0.0')}")
    click.echo(f"Python:         {sys.version.split()[0]}")
    click.echo(f"Platform:       {platform.system()} {platform.release()}")
    click.echo(f"SQLAlchemy:     {sqlalchemy_version}")
    
    try:
        nlp = spacy.load("en_core_web_sm")
        click.echo(f"spaCy:          {spacy.__version__} (model: en_core_web_sm)")
    except:
        click.echo(warning(f"spaCy:          {spacy.__version__} (model not found)"))
    
    # Check database connection
    try:
        session = get_session()
        session.execute(text("SELECT 1"))
        session.close()
        click.echo(success("Database:       ✓ Connected"))
    except Exception as e:
        click.echo(error(f"Database:       ✗ Error: {str(e)[:40]}"))
    
    # Check OpenAI API key
    from et_intel_core.config import settings
    if settings.openai_api_key and settings.openai_api_key != "your-openai-api-key-here":
        click.echo(success("OpenAI API:     ✓ Configured"))
    else:
        click.echo(warning("OpenAI API:     ⚠ Not configured"))
    
    click.echo("=" * 60)
    click.echo(info("\n💡 Documentation: https://github.com/your-repo/docs"))


@cli.command(name='ingest-apify')
@click.option(
    '--posts', '-p',
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help='Post scraper CSV file'
)
@click.option(
    '--comments', '-c',
    multiple=True,
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help='Comment scraper CSV file(s)'
)
@click.option(
    '--metadata', '-m',
    multiple=True,
    type=click.Path(exists=True, path_type=Path),
    help='Metadata scraper CSV file(s)'
)
@click.pass_context
def ingest_apify(ctx, posts: Path, comments: tuple, metadata: tuple):
    """
    Ingest Apify CSV exports with proper ID matching.
    
    This uses ApifyMergedSource which handles the ID matching problem:
    - Post scraper returns exact IDs (3773020515456922670)
    - Comments scraper returns rounded IDs (3773020515456922000)
    - Uses 15-digit prefix matching to join them correctly
    
    Example:
        python cli.py ingest-apify -p posts.csv -c comments1.csv -c comments2.csv -m metadata.csv
    """
    if not HAS_MERGED:
        click.echo(error("✗ ApifyMergedAdapter not available. Ensure et_intel_apify module is in path."))
        raise click.Abort()
    
    verbose = ctx.obj.get('VERBOSE', False)
    
    click.echo(info(f"📥 Ingesting Apify merged data"))
    click.echo(info(f"   Post CSV: {posts}"))
    click.echo(info(f"   Comment CSVs: {len(comments)} file(s)"))
    if metadata:
        click.echo(info(f"   Metadata CSVs: {len(metadata)} file(s)"))
    
    try:
        source = ApifyMergedAdapter(
            post_csv=posts,
            comment_csvs=list(comments),
            metadata_csvs=list(metadata) if metadata else None,
        )
        
        # Get stats before ingestion
        stats = source.merged_source.get_stats()
        click.echo(info(f"\n   Loaded {stats['posts_loaded']} posts ({stats['posts_with_metadata']} with metadata)"))
        
        session = get_session()
        try:
            service = IngestionService(session)
            click.echo(info("\n⏳ Processing..."))
            
            with click.progressbar(
                length=100,
                label='Ingesting',
                show_eta=False
            ) as bar:
                results = service.ingest(source)
                bar.update(100)
            
            click.echo(success("\n✓ Ingestion complete!"))
            click.echo(f"  Posts created:    {highlight(str(results['posts_created']))}")
            click.echo(f"  Posts updated:    {highlight(str(results['posts_updated']))}")
            click.echo(f"  Comments created: {highlight(str(results['comments_created']))}")
            click.echo(f"  Comments updated: {highlight(str(results['comments_updated']))}")
            
        except Exception as e:
            click.echo(error(f"\n✗ Error during ingestion: {e}"))
            if verbose:
                import traceback
                click.echo(error(traceback.format_exc()))
            session.rollback()
            raise click.Abort()
        finally:
            session.close()
            
    except Exception as e:
        click.echo(error(f"\n✗ Error: {e}"))
        if verbose:
            import traceback
            click.echo(error(traceback.format_exc()))
        raise click.Abort()


@cli.command()
def create_indexes():
    """Create performance indexes for analytics queries."""
    from et_intel_core.db_indexes import create_performance_indexes
    
    click.echo(info("🔧 Creating performance indexes...\n"))
    session = get_session()
    try:
        create_performance_indexes(session)
        click.echo(success("\n✓ Indexes created successfully"))
        click.echo(info("   Query performance should be significantly improved"))
    except Exception as e:
        click.echo(error(f"\n✗ Error creating indexes: {e}"))
        raise click.Abort()
    finally:
        session.close()


if __name__ == '__main__':
    cli()

