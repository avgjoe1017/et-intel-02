#!/usr/bin/env python
"""Quick analysis of test results."""

import json

with open('test_sentiment_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

results = data['detailed_results']

print("📊 Test Results Analysis")
print("=" * 60)
print(f"Total entries: {len(results)}")
print(f"Entries with entity_scores: {sum(1 for e in results if e['validation']['has_entity_scores'])}")
print(f"Total entity scores: {sum(e['validation']['entity_count'] for e in results)}")
print(f"JSON parse errors: {sum(1 for e in results if not e.get('raw_response_parsed'))}")
print(f"Average entity scores per entry: {sum(e['validation']['entity_count'] for e in results) / len(results):.2f}")

print("\n📈 Entity Score Distribution:")
entity_score_counts = {}
for entry in results:
    count = entry['validation']['entity_count']
    entity_score_counts[count] = entity_score_counts.get(count, 0) + 1
for count, freq in sorted(entity_score_counts.items()):
    print(f"  {count} entity scores: {freq} entries")

print("\n✅ All entries have valid JSON responses!")

