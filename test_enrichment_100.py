#!/usr/bin/env python
"""
Test script to enrich just 100 comments with the enhanced sentiment system.
"""

import uuid
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from et_intel_core.db import get_session
from et_intel_core.services import EnrichmentService
from et_intel_core.nlp import EntityExtractor, get_sentiment_provider
from et_intel_core.models import Comment, ExtractedSignal, SignalType, MonitoredEntity, Post
from sqlalchemy import func

def main():
    print("🧪 Testing Enhanced Sentiment System with 100 Comments")
    print("=" * 60)
    
    session = get_session()
    
    try:
        # Load entity catalog first
        entity_catalog = session.query(MonitoredEntity).filter_by(is_active=True).all()
        if not entity_catalog:
            print("❌ No monitored entities found. Run: python cli.py seed-entities")
            return
        
        print(f"📋 Loaded {len(entity_catalog)} monitored entities")
        
        # Get 100 comments (prefer ones with post captions for better testing)
        comments = session.query(Comment).join(Post).filter(
            Post.caption.isnot(None)
        ).limit(100).all()
        
        if not comments:
            # Fallback: get any 100 comments
            comments = session.query(Comment).limit(100).all()
        
        if not comments:
            print("❌ No comments found in database")
            return
        
        print(f"📊 Found {len(comments)} comments to test")
        
        # Check if any have post captions
        with_captions = sum(1 for c in comments if c.post.caption)
        print(f"   - {with_captions} have post captions")
        
        # Get comment IDs
        comment_ids = [c.id for c in comments]
        
        # Initialize enrichment service
        extractor = EntityExtractor(entity_catalog)
        sentiment_provider = get_sentiment_provider(backend="openai")  # Force OpenAI for enhanced features
        
        # Check if provider supports enhanced analysis
        has_enhanced = hasattr(sentiment_provider, 'analyze_comment')
        print(f"\n🔧 Sentiment Provider: {type(sentiment_provider).__name__}")
        print(f"   - Enhanced analysis: {'✅ Yes' if has_enhanced else '❌ No (using legacy)'}")
        
        if not has_enhanced:
            print("\n⚠️  Warning: Provider doesn't support enhanced analysis.")
            print("   Make sure OPENAI_API_KEY is set and provider is 'openai'")
        
        enrichment = EnrichmentService(session, extractor, sentiment_provider)
        
        # Delete existing signals for these comments (clean slate)
        print("\n🧹 Cleaning existing signals for test comments...")
        deleted = session.query(ExtractedSignal).filter(
            ExtractedSignal.comment_id.in_(comment_ids)
        ).delete(synchronize_session=False)
        session.commit()
        print(f"   - Deleted {deleted} existing signals")
        
        # Run enrichment
        print("\n⏳ Running enrichment...")
        stats = enrichment.enrich_comments(comment_ids=comment_ids)
        
        print(f"\n✅ Enrichment Complete!")
        print(f"   - Comments processed: {stats['comments_processed']}")
        print(f"   - Signals created: {stats['signals_created']}")
        print(f"   - Entities discovered: {stats['entities_discovered']}")
        
        # Analyze what signals were created
        print("\n📈 Signal Type Breakdown:")
        signal_counts = session.query(
            ExtractedSignal.signal_type,
            func.count(ExtractedSignal.id).label('count')
        ).filter(
            ExtractedSignal.comment_id.in_(comment_ids)
        ).group_by(ExtractedSignal.signal_type).all()
        
        for signal_type, count in signal_counts:
            print(f"   - {signal_type}: {count}")
        
        # Check for entity-targeted sentiment
        entity_sentiment = session.query(func.count(func.distinct(ExtractedSignal.entity_id))).filter(
            ExtractedSignal.comment_id.in_(comment_ids),
            ExtractedSignal.signal_type == SignalType.SENTIMENT,
            ExtractedSignal.entity_id.isnot(None)
        ).scalar()
        
        print(f"\n🎯 Entity-Targeted Sentiment:")
        print(f"   - Comments with entity-specific sentiment: {entity_sentiment}")
        
        # Sample a few signals to show structure
        print("\n📝 Sample Signals (first 5):")
        sample_signals = session.query(ExtractedSignal).filter(
            ExtractedSignal.comment_id.in_(comment_ids)
        ).limit(5).all()
        
        for signal in sample_signals:
            entity_name = signal.entity.name if signal.entity else "None"
            print(f"   - {signal.signal_type}: {signal.value} (entity: {entity_name}, numeric: {signal.numeric_value})")
        
        print("\n" + "=" * 60)
        print("✅ Test complete! Check the signals above to verify enhanced features.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    main()

