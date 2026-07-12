import urllib.request
import os
import time

fandomMap = {
    'Town Hall 17': 'Town_Hall17.png',
    'Town Hall 16': 'Town_Hall16.png',
    'Town Hall 15': 'Town_Hall15.png',
    'Monolith': 'Monolith.png',
    'Spell Tower': 'Spell_Tower1.png',
    'Ricochet Cannon': 'Ricochet_Cannon.png',
    'Multi-Archer Tower': 'Multi-Archer_Tower.png',
    'Root Rider': 'Root_Rider_info.png',
    'Druid': 'Druid_info.png',
    'Apprentice Warden': 'Apprentice_Warden_info.png',
    'Electro Titan': 'Electro_Titan_info.png',
    'Recall Spell': 'Recall_Spell_info.png',
    'Overgrowth Spell': 'Overgrowth_Spell_info.png',
    'Revive Spell': 'Revive_Spell_info.png',
    'Diggy': 'Diggy_info.png',
    'Frosty': 'Frosty_info.png',
    'Spirit Fox': 'Spirit_Fox_info.png',
    'Phoenix': 'Phoenix_info.png',
    'Poison Lizard': 'Poison_Lizard_info.png',
    'Angry Jelly': 'Angry_Jelly_info.png',
    'Giant Gauntlet': 'Giant_Gauntlet.png',
    'Frozen Arrow': 'Frozen_Arrow.png',
    'Fireball': 'Fireball.png',
    'Spiky Ball': 'Spiky_Ball.png',
    'Magic Mirror': 'Magic_Mirror.png',
    'Haste Vial': 'Haste_Vial.png',
    'Hog Rider Puppet': 'Hog_Rider_Puppet.png',
    'Rocket Spear': 'Rocket_Spear.png',
    'Earthquake Boots': 'Earthquake_Boots.png',
    'Barbarian Puppet': 'Barbarian_Puppet.png',
    'Rage Vial': 'Rage_Vial.png',
    'Archer Puppet': 'Archer_Puppet.png',
    'Invisibility Vial': 'Invisibility_Vial.png',
    'Healer Puppet': 'Healer_Puppet.png',
    'Life Gem': 'Life_Gem.png',
    'Eternal Tome': 'Eternal_Tome.png',
    'Royal Gem': 'Royal_Gem.png',
    'Seeking Shield': 'Seeking_Shield.png',
    'Vampstache': 'Vampstache.png',
    'Healing Tome': 'Healing_Tome.png',
    'L.A.S.S.I': 'L.A.S.S.I_info.png',
    'Electro Owl': 'Electro_Owl_info.png',
    'Mighty Yak': 'Mighty_Yak_info.png',
    'Unicorn': 'Unicorn_info.png',
}

os.makedirs('coc_assets', exist_ok=True)
for name, filename in fandomMap.items():
    url = f"https://clashofclans.fandom.com/wiki/Special:FilePath/{filename}"
    filepath = f"coc_assets/{filename}"
    if not os.path.exists(filepath):
        print(f"Downloading {filename}...")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response, open(filepath, 'wb') as out_file:
                out_file.write(response.read())
            time.sleep(0.2)
        except Exception as e:
            print(f"Failed to download {filename}: {e}")

print("Done downloading.")
