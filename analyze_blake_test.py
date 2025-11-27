#!/usr/bin/env python
"""Quick analysis of Blake/Justin test results."""

import json

with open('test_blake_justin_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

entries = data['detailed_results']
blake_scores = [e['validation']['blake_score'] for e in entries if e['validation']['blake_score'] is not None]
blake_neg = [s for s in blake_scores if s < -0.5]

print("📊 Blake/Justin Test Analysis")
print("=" * 60)
print(f"Total entries: {len(entries)}")
print(f"Blake scores: {len(blake_scores)}")
print(f"Blake < -0.5: {len(blake_neg)}/{len(blake_scores)} ({len(blake_neg)/len(blake_scores)*100:.1f}%)")
print(f"Blake avg: {data['statistics']['blake_avg_sentiment']:.3f}")
print(f"\nEmotions: {data['statistics']['emotion_distribution']}")
print(f"Stances: {data['statistics']['stance_distribution']}")
print(f"Avg Toxicity: {data['statistics']['avg_toxicity']:.3f}")
print(f"High Toxicity (>0.5): {data['statistics']['high_toxicity_count']}")

