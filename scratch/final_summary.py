import json
with open('artifacts/decisions.json', 'r', encoding='utf-8') as f:
    dec = json.load(f)

parts = {}
states = {}
for k, v in dec['decisions'].items():
    p = v.get('partition')
    s = v.get('state')
    parts[p] = parts.get(p, 0) + 1
    states[s] = states.get(s, 0) + 1

print('=== FINAL DATASET SUMMARY ===')
print('Total leads:', len(dec['decisions']))
print('Partitions:', parts)
print('States:', states)
print()
print('9 Reviewed leads (preserved from Diwas):')
for k, v in dec['decisions'].items():
    if v.get('state') in ('accepted', 'revised'):
        print(' ', v['state'], '|', v['partition'], '|', k)

