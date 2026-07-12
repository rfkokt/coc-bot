import json
import re

with open('www.clash.ninja.har') as f:
    har = json.load(f)

mapping = {}
for entry in har['log']['entries']:
    url = entry['request']['url']
    if 'clash.ninja' in url and entry['response']['content'].get('mimeType', '') == 'text/html':
        html = entry['response']['content'].get('text', '')
        # look for <img ... src="/images/entities/1_13.png" ... title="Town Hall Level 13" ...>
        # or anything similar
        imgs = re.findall(r'<img[^>]+>', html)
        for img in imgs:
            src_m = re.search(r'src=[\"\'](/images/entities/[^\'\"]+)[\"\']', img)
            title_m = re.search(r'title=[\"\']([^\"\']+)[\"\']', img)
            alt_m = re.search(r'alt=[\"\']([^\"\']+)[\"\']', img)
            if src_m:
                src = src_m.group(1)
                name = None
                if title_m: name = title_m.group(1)
                elif alt_m: name = alt_m.group(1)
                
                if name:
                    # e.g., name="Cannon Level 13"
                    mapping[src] = name

for k, v in mapping.items():
    print(k, '=>', v)
