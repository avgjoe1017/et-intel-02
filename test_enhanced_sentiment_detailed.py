#!/usr/bin/env python
"""
Detailed test of enhanced sentiment system with full input/output logging.
"""

import json
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from et_intel_core.db import get_session
from et_intel_core.services import EnrichmentService
from et_intel_core.nlp import EntityExtractor, get_sentiment_provider
from et_intel_core.models import Comment, ExtractedSignal, SignalType, MonitoredEntity, Post
from sqlalchemy import func

# Monkey patch to capture API responses
original_analyze = None
captured_data = []

def make_capture_wrapper(original_method, provider_instance):
    """Create a wrapper function that captures inputs/outputs."""
    def wrapper(comment_text, post_caption="", comment_likes=0, target_entities=None):
        # Call original method
        result = original_method(comment_text, post_caption, comment_likes, target_entities)
        
        # Capture the raw response if available
        raw_response = getattr(provider_instance, '_last_response', None)
        
        # Try to parse raw response as JSON to see structure
        parsed_raw = None
        if raw_response:
            try:
                parsed_raw = json.loads(raw_response)
            except:
                pass
        
        captured_data.append({
            'timestamp': datetime.utcnow().isoformat(),
            'input': {
                'comment_text': comment_text,
                'post_caption': post_caption,
                'comment_likes': comment_likes,
                'target_entities': target_entities or []
            },
            'output': {
                'entity_scores': result.get('entity_scores', {}),
                'emotion': result.get('emotion'),
                'stance': result.get('stance'),
                'topics': result.get('topics', []),
                'other_entities': result.get('other_entities', []),
                'sarcasm': result.get('sarcasm'),
                'toxicity': result.get('toxicity')
            },
            'raw_response': raw_response,
            'raw_response_parsed': parsed_raw,
            'validation': {
                'has_entity_scores': bool(result.get('entity_scores')),
                'entity_count': len(result.get('entity_scores', {})),
                'entity_score_count': sum(1 for v in result.get('entity_scores', {}).values() if v is not None)
            }
        })
        
        return result
    return wrapper

def main():
    global original_analyze
    
    print("🧪 Detailed Enhanced Sentiment Test")
    print("=" * 60)
    
    session = get_session()
    
    try:
        # Load entity catalog
        entity_catalog = session.query(MonitoredEntity).filter_by(is_active=True).all()
        if not entity_catalog:
            print("❌ No monitored entities found. Run: python cli.py seed-entities")
            return
        
        print(f"📋 Loaded {len(entity_catalog)} monitored entities")
        entity_names = [e.name for e in entity_catalog]
        print(f"   Entities: {', '.join(entity_names[:5])}{'...' if len(entity_names) > 5 else ''}")
        
        # Get 20 comments (smaller sample for detailed review)
        comments = session.query(Comment).join(Post).filter(
            Post.caption.isnot(None)
        ).limit(20).all()
        
        if not comments:
            comments = session.query(Comment).limit(20).all()
        
        if not comments:
            print("❌ No comments found in database")
            return
        
        print(f"📊 Testing with {len(comments)} comments")
        
        # Get comment IDs
        comment_ids = [c.id for c in comments]
        
        # Initialize enrichment service
        extractor = EntityExtractor(entity_catalog)
        sentiment_provider = get_sentiment_provider(backend="openai")
        
        # Monkey patch to capture API calls
        if hasattr(sentiment_provider, 'analyze_comment'):
            original_analyze = sentiment_provider.analyze_comment
            sentiment_provider.analyze_comment = make_capture_wrapper(original_analyze, sentiment_provider)
        
        print(f"\n🔧 Sentiment Provider: {type(sentiment_provider).__name__}")
        print(f"   - Enhanced analysis: {'✅ Yes' if hasattr(sentiment_provider, 'analyze_comment') else '❌ No'}")
        
        # Delete existing signals for clean test
        print("\n🧹 Cleaning existing signals...")
        deleted = session.query(ExtractedSignal).filter(
            ExtractedSignal.comment_id.in_(comment_ids)
        ).delete(synchronize_session=False)
        session.commit()
        print(f"   - Deleted {deleted} existing signals")
        
        # Run enrichment
        print("\n⏳ Running enrichment with detailed capture...")
        enrichment = EnrichmentService(session, extractor, sentiment_provider)
        stats = enrichment.enrich_comments(comment_ids=comment_ids)
        
        print(f"\n✅ Enrichment Complete!")
        print(f"   - Comments processed: {stats['comments_processed']}")
        print(f"   - Signals created: {stats['signals_created']}")
        print(f"   - Entities discovered: {stats['entities_discovered']}")
        
        # Analyze captured data
        print(f"\n📈 Captured {len(captured_data)} API calls")
        
        # Statistics
        with_entity_scores = sum(1 for d in captured_data if d['validation']['has_entity_scores'])
        total_entity_scores = sum(d['validation']['entity_count'] for d in captured_data)
        avg_entity_scores = total_entity_scores / len(captured_data) if captured_data else 0
        
        print(f"   - Calls with entity_scores: {with_entity_scores}/{len(captured_data)} ({with_entity_scores/len(captured_data)*100:.1f}%)")
        print(f"   - Total entity scores: {total_entity_scores}")
        print(f"   - Avg entity scores per call: {avg_entity_scores:.2f}")
        
        # Emotion breakdown
        emotions = {}
        for d in captured_data:
            emotion = d['output']['emotion']
            emotions[emotion] = emotions.get(emotion, 0) + 1
        print(f"\n😊 Emotion Breakdown:")
        for emotion, count in sorted(emotions.items(), key=lambda x: x[1], reverse=True):
            print(f"   - {emotion}: {count}")
        
        # Stance breakdown
        stances = {}
        for d in captured_data:
            stance = d['output']['stance']
            stances[stance] = stances.get(stance, 0) + 1
        print(f"\n🎯 Stance Breakdown:")
        for stance, count in sorted(stances.items(), key=lambda x: x[1], reverse=True):
            print(f"   - {stance}: {count}")
        
        # Save detailed results to file
        output_file = "test_sentiment_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'test_metadata': {
                    'timestamp': datetime.utcnow().isoformat(),
                    'comments_tested': len(comments),
                    'entities_available': entity_names,
                    'total_api_calls': len(captured_data)
                },
                'statistics': {
                    'with_entity_scores': with_entity_scores,
                    'total_entity_scores': total_entity_scores,
                    'avg_entity_scores_per_call': avg_entity_scores,
                    'emotion_distribution': emotions,
                    'stance_distribution': stances
                },
                'detailed_results': captured_data
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Detailed results saved to: {output_file}")
        print(f"   - Total records: {len(captured_data)}")
        print(f"   - File size: {len(json.dumps(captured_data, indent=2)) / 1024:.1f} KB")
        
        # Show sample entries
        print(f"\n📝 Sample Entries (first 3):")
        for i, entry in enumerate(captured_data[:3], 1):
            print(f"\n   Entry {i}:")
            print(f"   Comment: {entry['input']['comment_text'][:100]}...")
            print(f"   Post Caption: {entry['input']['post_caption'][:80]}...")
            print(f"   Target Entities: {entry['input']['target_entities']}")
            print(f"   Entity Scores: {entry['output']['entity_scores']}")
            print(f"   Emotion: {entry['output']['emotion']}, Stance: {entry['output']['stance']}")
            print(f"   Topics: {entry['output']['topics']}")
            print(f"   Has Entity Scores: {entry['validation']['has_entity_scores']}")
        
        print("\n" + "=" * 60)
        print("✅ Test complete! Review test_sentiment_results.json for full details.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    main()

