"""Analyze duplicate posts in database."""
from et_intel_core.db import get_session
from et_intel_core.models import Post
from sqlalchemy import func
from collections import defaultdict

session = get_session()

# Count posts by type
total = session.query(func.count(Post.id)).scalar()
shortcode_posts = session.query(Post).filter(~Post.external_id.like('37%')).all()
numeric_posts = session.query(Post).filter(Post.external_id.like('37%')).all()

print(f"Total posts: {total}")
print(f"Posts with shortCode IDs: {len(shortcode_posts)}")
print(f"Posts with numeric IDs: {len(numeric_posts)}")

# Check for duplicates by URL
url_to_posts = defaultdict(list)
for post in session.query(Post).all():
    url_to_posts[post.url].append(post)

duplicate_urls = {url: posts for url, posts in url_to_posts.items() if len(posts) > 1}

print(f"\nDuplicate URLs (same post, different external_ids): {len(duplicate_urls)}")
for url, posts in list(duplicate_urls.items())[:5]:
    print(f"\n  URL: {url}")
    for p in posts:
        print(f"    - external_id: {p.external_id}, has caption: {bool(p.caption)}")

# Check unique shortCodes
shortcodes = set()
for post in shortcode_posts:
    if post.url:
        # Extract shortCode from URL
        parts = post.url.rstrip('/').split('/')
        if len(parts) > 0:
            sc = parts[-1]
            if sc != 'p' and not sc.startswith('37'):
                shortcodes.add(sc)

print(f"\nUnique shortCodes: {len(shortcodes)}")
print(f"Expected: 62 (from provided URLs)")

# Check which shortCodes we have
provided_shortcodes = {
    'DRSssyVEuwk', 'DRSmMhODnJ2', 'DRSe90UkyQX', 'DRTFz2IDlCi', 'DRTJ5HSEsbn',
    'DRTNS-DE-vo', 'DRTQvKBjGfd', 'DRTUK7iiTlt', 'DRTjZodk_f_', 'DRTl88yAtpT',
    'DRUjWHHkmYn', 'DRUm7JTgnYg', 'DRUqEbUFaXF', 'DRUvfbygbOy', 'DRU2XcJAGMT',
    'DRU_A73lX3t', 'DRVCC0akxdD', 'DRVHPGNjERP', 'DRVLE4lkuzy', 'DRVP0YvCCsR',
    'DRVTjwviQwD', 'DRVagS8Elpo', 'DRVhY01Drat', 'DRVoNTAkeGr', 'DRXO0LIASWo',
    'DRXc6ZFgdZH', 'DRXqntkklNN', 'DRX3_vDCY1I', 'DRYGJRZkVCZ', 'DRZ6cjqD8gu',
    'DRaIjrvkhxo', 'DRaV7Moidkh', 'DRaiPEYjhQ9', 'DRaprNhjbmy', 'DRaxvV_iVWU',
    'DRa6LOREeey', 'DRbR-C_iib1', 'DRcRixzjwMW', 'DRcWscGknwt', 'DRcdisiEjQu',
    'DRcfYdOCrea', 'DRcmRMVkqAp', 'DRcuyaxEx-A', 'DRc0XPqDDFq', 'DRc7HlcAQDD',
    'DRc-I7Ekfob', 'DRdE3pEEw6I', 'DRdL7IYgUIt', 'DRdNnJNEphK', 'DRdUd6fE3gN',
    'DRdcWIJgEtz', 'DRddaIOlUGA', 'DRdgeTBDjq3', 'DRdnWxHleh4', 'DRdqxxOjYl3',
    'DReveV_Cu85', 'DRe-iwyj0OQ', 'DRfELnPEi1C', 'DRfLXeeDXPy', 'DRfSMFojoOo',
    'DRfW7gxD7Zb', 'DRfeIXeFD1e',
}

missing = provided_shortcodes - shortcodes
extra = shortcodes - provided_shortcodes

print(f"\nShortCodes from provided URLs: {len(provided_shortcodes)}")
print(f"ShortCodes in database: {len(shortcodes)}")
print(f"Missing: {len(missing)}")
print(f"Extra: {len(extra)}")

if missing:
    print(f"\nMissing shortCodes (first 10): {list(missing)[:10]}")
if extra:
    print(f"\nExtra shortCodes (first 10): {list(extra)[:10]}")

session.close()

