#!/usr/bin/env python
"""
Test enhanced sentiment system on Blake/Justin controversy comments.
Includes known negative test cases with expected outputs.
"""

import json
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()

from et_intel_core.db import get_session
from et_intel_core.services import EnrichmentService
from et_intel_core.nlp import EntityExtractor, get_sentiment_provider
from et_intel_core.models import Comment, ExtractedSignal, SignalType, MonitoredEntity, Post
from sqlalchemy import func, or_

# Known test cases with expected outputs
TEST_CASES = [
    {
        "comment_text": "Blake was the worst choice for Lily... Blake ruined it",
        "expected_blake_sentiment": "< -0.5",  # Should be negative
        "expected_emotion": "anger|disgust|disappointment",
        "expected_stance": "oppose",
        "expected_toxicity": "> 0.3"
    },
    {
        "comment_text": "She chose Blake and ruined everything, Justin deserved better 🐍🤮",
        "expected_blake_sentiment": "< -0.5",
        "expected_justin_sentiment": "> 0.5",  # Positive for Justin
        "expected_emotion": "disgust|anger",
        "expected_stance": "oppose",
        "expected_toxicity": "> 0.3"
    },
    {
        "comment_text": "Hopefully Blake's career is done",
        "expected_blake_sentiment": "< -0.7",  # Very negative
        "expected_emotion": "anger|disgust",
        "expected_stance": "oppose",
        "expected_toxicity": "> 0.5"
    },
    {
        "comment_text": "Still hate Blake",
        "expected_blake_sentiment": "< -0.5",
        "expected_emotion": "anger|disgust",
        "expected_stance": "oppose"
    }
]

captured_data = []

def make_capture_wrapper(original_method, provider_instance):
    """Create a wrapper function that captures inputs/outputs."""
    def wrapper(comment_text, post_caption="", comment_likes=0, target_entities=None):
        # Call original method
        result = original_method(comment_text, post_caption, comment_likes, target_entities)
        
        # Capture the raw response if available
        raw_response = getattr(provider_instance, '_last_response', None)
        
        # Try to parse raw response as JSON
        parsed_raw = None
        if raw_response:
            try:
                parsed_raw = json.loads(raw_response)
            except:
                pass
        
        captured_data.append({
            'timestamp': datetime.now(timezone.utc).isoformat(),
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
                'blake_score': result.get('entity_scores', {}).get('Blake Lively'),
                'justin_score': result.get('entity_scores', {}).get('Justin Baldoni'),
            }
        })
        
        return result
    return wrapper

def main():
    print("🧪 Blake/Justin Sentiment Test with Known Negative Cases")
    print("=" * 70)
    
    session = get_session()
    
    try:
        # Load entity catalog
        entity_catalog = session.query(MonitoredEntity).filter_by(is_active=True).all()
        if not entity_catalog:
            print("❌ No monitored entities found. Run: python cli.py seed-entities")
            return
        
        print(f"📋 Loaded {len(entity_catalog)} monitored entities")
        entity_names = [e.name for e in entity_catalog]
        print(f"   Entities: {', '.join(entity_names)}")
        
        # Find Blake/Justin comments - look for Colleen Hoover post or Blake/Justin mentions
        # First, find posts with Blake/Justin in caption
        blake_justin_posts = session.query(Post).filter(
            or_(
                Post.caption.ilike('%Blake%'),
                Post.caption.ilike('%Justin%'),
                Post.caption.ilike('%Colleen Hoover%'),
                Post.caption.ilike('%It Ends With Us%')
            )
        ).limit(5).all()
        
        print(f"\n📊 Found {len(blake_justin_posts)} posts mentioning Blake/Justin/Colleen")
        
        # Get comments from these posts
        comments = []
        for post in blake_justin_posts:
            post_comments = session.query(Comment).filter(
                Comment.post_id == post.id
            ).limit(10).all()
            comments.extend(post_comments)
        
        # Also search for comments that mention Blake or Justin directly
        direct_mentions = session.query(Comment).join(Post).filter(
            or_(
                Comment.text.ilike('%Blake%'),
                Comment.text.ilike('%Justin%'),
                Comment.text.ilike('%Lily%')  # Character from It Ends With Us
            )
        ).limit(20).all()
        
        # Combine and deduplicate
        comment_ids = {c.id for c in comments + direct_mentions}
        comments = session.query(Comment).filter(Comment.id.in_(list(comment_ids))).limit(30).all()
        
        if not comments:
            print("❌ No Blake/Justin comments found in database")
            print("   Try ingesting the Colleen Hoover post comments first")
            return
        
        print(f"📊 Testing with {len(comments)} Blake/Justin related comments")
        
        # Check for negative keywords
        negative_keywords = ['hate', 'worst', 'ruined', 'disgusting', 'terrible', 'awful']
        negative_count = sum(1 for c in comments if any(kw in c.text.lower() for kw in negative_keywords))
        print(f"   - Comments with negative keywords: {negative_count}")
        
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
        blake_scores = [d['validation']['blake_score'] for d in captured_data if d['validation']['blake_score'] is not None]
        justin_scores = [d['validation']['justin_score'] for d in captured_data if d['validation']['justin_score'] is not None]
        
        print(f"   - Calls with entity_scores: {with_entity_scores}/{len(captured_data)}")
        print(f"   - Blake Lively scores: {len(blake_scores)}")
        print(f"   - Justin Baldoni scores: {len(justin_scores)}")
        
        if blake_scores:
            avg_blake = sum(blake_scores) / len(blake_scores)
            min_blake = min(blake_scores)
            max_blake = max(blake_scores)
            print(f"   - Blake sentiment: avg={avg_blake:.2f}, min={min_blake:.2f}, max={max_blake:.2f}")
        
        if justin_scores:
            avg_justin = sum(justin_scores) / len(justin_scores)
            min_justin = min(justin_scores)
            max_justin = max(justin_scores)
            print(f"   - Justin sentiment: avg={avg_justin:.2f}, min={min_justin:.2f}, max={max_justin:.2f}")
        
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
        
        # Toxicity stats
        toxicities = [d['output']['toxicity'] for d in captured_data if d['output']['toxicity'] is not None]
        if toxicities:
            avg_toxicity = sum(toxicities) / len(toxicities)
            max_toxicity = max(toxicities)
            high_toxicity = sum(1 for t in toxicities if t > 0.5)
            print(f"\n⚠️  Toxicity Stats:")
            print(f"   - Average: {avg_toxicity:.2f}")
            print(f"   - Max: {max_toxicity:.2f}")
            print(f"   - High (>0.5): {high_toxicity}")
        
        # Validate against test cases
        print(f"\n✅ Validation Against Known Test Cases:")
        for i, entry in enumerate(captured_data[:10], 1):
            comment = entry['input']['comment_text']
            # Check if this matches any test case
            for test_case in TEST_CASES:
                if test_case['comment_text'].lower() in comment.lower() or comment.lower() in test_case['comment_text'].lower():
                    print(f"\n   Test Case Match #{i}:")
                    print(f"   Comment: {comment[:80]}...")
                    
                    blake_score = entry['validation']['blake_score']
                    if blake_score is not None:
                        expected = test_case.get('expected_blake_sentiment', '')
                        if '< -0.5' in expected:
                            status = "✅" if blake_score < -0.5 else "❌"
                            print(f"   {status} Blake sentiment: {blake_score:.2f} (expected < -0.5)")
                    
                    justin_score = entry['validation']['justin_score']
                    if justin_score is not None:
                        expected = test_case.get('expected_justin_sentiment', '')
                        if '> 0.5' in expected:
                            status = "✅" if justin_score > 0.5 else "❌"
                            print(f"   {status} Justin sentiment: {justin_score:.2f} (expected > 0.5)")
                    
                    emotion = entry['output']['emotion']
                    expected_emotions = test_case.get('expected_emotion', '').split('|')
                    if expected_emotions and emotion in expected_emotions:
                        print(f"   ✅ Emotion: {emotion} (matches expected)")
                    elif expected_emotions:
                        print(f"   ⚠️  Emotion: {emotion} (expected one of: {expected_emotions})")
                    
                    stance = entry['output']['stance']
                    expected_stance = test_case.get('expected_stance', '')
                    if expected_stance and stance == expected_stance:
                        print(f"   ✅ Stance: {stance} (matches expected)")
                    elif expected_stance:
                        print(f"   ⚠️  Stance: {stance} (expected: {expected_stance})")
                    break
        
        # Save detailed results
        output_file = "test_blake_justin_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'test_metadata': {
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'comments_tested': len(comments),
                    'entities_available': entity_names,
                    'total_api_calls': len(captured_data),
                    'test_type': 'Blake/Justin controversy comments'
                },
                'statistics': {
                    'with_entity_scores': with_entity_scores,
                    'blake_scores_count': len(blake_scores),
                    'justin_scores_count': len(justin_scores),
                    'blake_avg_sentiment': sum(blake_scores) / len(blake_scores) if blake_scores else None,
                    'justin_avg_sentiment': sum(justin_scores) / len(justin_scores) if justin_scores else None,
                    'emotion_distribution': emotions,
                    'stance_distribution': stances,
                    'avg_toxicity': sum(toxicities) / len(toxicities) if toxicities else None,
                    'high_toxicity_count': sum(1 for t in toxicities if t > 0.5) if toxicities else 0
                },
                'detailed_results': captured_data
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Detailed results saved to: {output_file}")
        print(f"   - Total records: {len(captured_data)}")
        
        # Show sample entries with Blake/Justin scores
        print(f"\n📝 Sample Entries with Blake/Justin Scores:")
        blake_entries = [e for e in captured_data if e['validation']['blake_score'] is not None]
        for i, entry in enumerate(blake_entries[:5], 1):
            print(f"\n   Entry {i}:")
            print(f"   Comment: {entry['input']['comment_text'][:100]}...")
            print(f"   Target Entities: {entry['input']['target_entities']}")
            print(f"   Entity Scores: {entry['output']['entity_scores']}")
            print(f"   Blake Score: {entry['validation']['blake_score']:.2f}")
            if entry['validation']['justin_score'] is not None:
                print(f"   Justin Score: {entry['validation']['justin_score']:.2f}")
            print(f"   Emotion: {entry['output']['emotion']}, Stance: {entry['output']['stance']}")
            print(f"   Toxicity: {entry['output']['toxicity']:.2f}")
        
        print("\n" + "=" * 70)
        print("✅ Test complete! Review test_blake_justin_results.json for full details.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    main()

