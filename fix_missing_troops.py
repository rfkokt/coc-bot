import coc_analyzer
import re

with open('coc_analyzer.py', 'r') as f:
    content = f.read()

# Add known missing troops to TROOP dict
if '4000123' not in content:
    content = content.replace('4000110: "Furnace",', '4000110: "Furnace", 4000123: "Mecha", 4000150: "Broom Witch",')
    with open('coc_analyzer.py', 'w') as f:
        f.write(content)
