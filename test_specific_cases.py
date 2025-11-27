#!/usr/bin/env python
"""
Test specific problematic cases identified by user.
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

# Specific test cases with expected outputs
TEST_CASES = [
    {
        "comment_text": "💐 You earned it. You chose Blake",
        "comment_likes": 5149,
        "expected": {
            "blake_sentiment": "< -0.5",
            "sarcasm": True,
            "emotion": "disgust|anger",
            "stance": "oppose"
        },
        "description": "High-engagement sarcastic comment (5,149 likes)"
    },
    {
        "comment_text": "Is it possible that Blake is telling the truth?",
        "comment_likes": 97,
        "expected": {
            "blake_sentiment": "≈ 0.0",
            "emotion": "neutral",
            "stance": "neutral"
        },
        "description": "Neutral question, not supportive"
    },
    {
        "comment_text": "I could never see Wicked without thinking of everything Lily Jay and her son lost",
        "expected": {
            "lily_jay_sentiment": "> 0.0",  # Positive toward Lily Jay (sympathy)
            "emotion": "disappointment|sadness",
            "note": "Sentiment toward Lily Jay should be positive (sympathy), not negative"
        },
        "description": "Sympathy context - positive toward person, negative toward situation"
    }
]

captured_data = []

def make_capture_wrapper(original_method, provider_instance):
    """Create a wrapper function that captures inputs/outputs."""
    def wrapper(comment_text, post_caption="", comment_likes=0, target_entities=None):
        result = original_method(comment_text, post_caption, comment_likes, target_entities)
        raw_response = getattr(provider_instance, '_last_response', None)
        
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
                'sarcasm': result.get('sarcasm'),
                'toxicity': result.get('toxicity')
            },
            'raw_response': raw_response,
            'raw_response_parsed': parsed_raw
        })
        
        return result
    return wrapper

def main():
    print("🧪 Testing Specific Problematic Cases")
    print("=" * 70)
    
    session = get_session()
    
    try:
        # Load entity catalog
        entity_catalog = session.query(MonitoredEntity).filter_by(is_active=True).all()
        if not entity_catalog:
            print("❌ No monitored entities found. Run: python cli.py seed-entities")
            return
        
        print(f"📋 Loaded {len(entity_catalog)} monitored entities")
        
        # Find comments matching test cases
        test_comments = []
        for test_case in TEST_CASES:
            comment_text = test_case['comment_text']
            # Search for this comment or similar
            comments = session.query(Comment).filter(
                Comment.text.ilike(f"%{comment_text[:30]}%")
            ).limit(1).all()
            
            if comments:
                test_comments.extend(comments)
            else:
                print(f"⚠️  Comment not found: {comment_text[:50]}...")
        
        # Test directly with the provider (regardless of database comments)
        print("\n🧪 Testing directly with sentiment provider...")
        extractor = EntityExtractor(entity_catalog)
        sentiment_provider = get_sentiment_provider(backend="openai")
        
        if hasattr(sentiment_provider, 'analyze_comment'):
            original_analyze = sentiment_provider.analyze_comment
            sentiment_provider.analyze_comment = make_capture_wrapper(original_analyze, sentiment_provider)
            
            # Test case 1: Sarcasm
            print("\n📝 Test Case 1: Sarcasm Detection")
            print("Comment: '💐 You earned it. You chose Blake'")
            print("Expected: Blake < -0.5, sarcasm=true")
            
            post_caption = "Colleen Hoover says the legal battle between Justin Baldoni and Blake Lively has tainted how she feels about her novel"
            result1 = sentiment_provider.analyze_comment(
                comment_text="💐 You earned it. You chose Blake",
                post_caption=post_caption,
                comment_likes=5149,
                target_entities=["Blake Lively", "Colleen Hoover"]
            )
            
            blake_score = result1.get('entity_scores', {}).get('Blake Lively')
            sarcasm = result1.get('sarcasm', False)
            
            print(f"Result: Blake={blake_score}, Sarcasm={sarcasm}")
            if blake_score is not None and blake_score < -0.5 and sarcasm:
                print("✅ PASS")
            else:
                print(f"❌ FAIL - Expected Blake < -0.5 and sarcasm=true, got Blake={blake_score}, sarcasm={sarcasm}")
            
            # Test case 2: Question
            print("\n📝 Test Case 2: Question Handling")
            print("Comment: 'Is it possible that Blake is telling the truth?'")
            print("Expected: Blake ≈ 0.0 (neutral)")
            
            result2 = sentiment_provider.analyze_comment(
                comment_text="Is it possible that Blake is telling the truth?",
                post_caption=post_caption,
                comment_likes=97,
                target_entities=["Blake Lively"]
            )
            
            blake_score2 = result2.get('entity_scores', {}).get('Blake Lively')
            print(f"Result: Blake={blake_score2}")
            if blake_score2 is not None and abs(blake_score2) < 0.2:
                print("✅ PASS")
            else:
                print(f"❌ FAIL - Expected Blake ≈ 0.0, got {blake_score2}")
            
            # Test case 3: Context understanding
            print("\n📝 Test Case 3: Context Understanding")
            print("Comment: 'I could never see Wicked without thinking of everything Lily Jay and her son lost'")
            print("Expected: Positive sentiment toward Lily Jay (sympathy)")
            
            result3 = sentiment_provider.analyze_comment(
                comment_text="I could never see Wicked without thinking of everything Lily Jay and her son lost",
                post_caption="",
                comment_likes=0,
                target_entities=[]
            )
            
            lily_score = result3.get('entity_scores', {}).get('Lily Jay')
            print(f"Result: Lily Jay={lily_score}")
            if lily_score is not None and lily_score > 0.0:
                print("✅ PASS")
            elif lily_score is None:
                print("⚠️  Lily Jay not in entity_scores (may be in other_entities)")
                print(f"Other entities: {result3.get('other_entities', [])}")
            else:
                print(f"❌ FAIL - Expected positive sentiment toward Lily Jay, got {lily_score}")
        
        # Save results
        if captured_data:
            output_file = "test_specific_cases_results.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'test_metadata': {
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'test_cases': TEST_CASES,
                        'total_tests': len(captured_data)
                    },
                    'detailed_results': captured_data
                }, f, indent=2, ensure_ascii=False)
            
            print(f"\n💾 Results saved to: {output_file}")
        
        print("\n" + "=" * 70)
        print("✅ Test complete!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    main()

