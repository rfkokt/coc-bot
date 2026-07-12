import coc_analyzer
import os

def check_image(name, cat, level=1):
    slug = name.lower().replace(' ', '_').replace('.', '')
    if name == 'L.A.S.S.I': slug = 'lassi'
    
    if 'Altar' in name:
        slug = slug.replace('_altar', '')
        return f"web/public/assets/heroes/{slug}/icon.webp"
        
    if name == 'Town Hall': return f"web/public/assets/buildings/home-village/town_hall/level_{level}.webp"
    if name == 'Builder Hall': return f"web/public/assets/buildings/builder-base/builder_hall/level_{level}.webp"
    if name == 'BUILDING 1000093': return f"web/public/assets/buildings/home-village/builder's_hut/level_{level}.webp"
    if name == "Builder's Hut": return f"web/public/assets/buildings/home-village/builder's_hut/level_{level}.webp"
    
    if cat == 'hero': return f"web/public/assets/heroes/{slug}/icon.webp"
    if cat == 'equipment': return f"web/public/assets/equipment/{slug}.webp"
    if cat == 'pet': return f"web/public/assets/pets/{slug}/icon.webp"
    if cat in ['troop', 'dark_troop', 'siege']: return f"web/public/assets/troops/{slug}/icon.webp"
    if cat == 'spell': return f"web/public/assets/spells/{slug}.webp"
    if cat == 'trap': return f"web/public/assets/traps/home-village/{slug}/level_{level}.webp"
    
    return f"web/public/assets/buildings/home-village/{slug}/level_{level}.webp"

missing = []

for k, name in coc_analyzer.TROOP.items():
    path = check_image(name, 'troop')
    if not os.path.exists(path): missing.append(f"Troop: {name} -> {path}")

for k, name in coc_analyzer.HERO.items():
    path = check_image(name, 'hero')
    if not os.path.exists(path): missing.append(f"Hero: {name} -> {path}")

for k, name in coc_analyzer.SPELL.items():
    path = check_image(name, 'spell')
    if not os.path.exists(path): missing.append(f"Spell: {name} -> {path}")

for k, name in coc_analyzer.PET.items():
    path = check_image(name, 'pet')
    if not os.path.exists(path): missing.append(f"Pet: {name} -> {path}")

for k, name in coc_analyzer.EQUIP_NAME.items():
    path = check_image(name, 'equipment')
    if not os.path.exists(path): missing.append(f"Equipment: {name} -> {path}")

for k, name in coc_analyzer.TRAP.items():
    path = check_image(name, 'trap', 1)
    if not os.path.exists(path): missing.append(f"Trap: {name} -> {path}")

for k, name in coc_analyzer.BLDG.items():
    path = check_image(name, 'building', 1)
    if not os.path.exists(path): missing.append(f"Bldg1: {name} -> {path}")

for k, name in coc_analyzer.BLDG2.items():
    path = check_image(name, 'building', 1)
    if not os.path.exists(path): missing.append(f"Bldg2: {name} -> {path}")

print(f"Total Missing: {len(missing)}")
for m in missing:
    print(m)
