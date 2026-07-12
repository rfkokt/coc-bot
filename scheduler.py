import random, datetime

def should_be_active(now=None):
    now = now or datetime.datetime.now()
    random.seed(now.date().toordinal())
    if random.random() < 0.14:          # ~1 hari/minggu libur
        return False
    start_h = random.randint(8, 12)
    play_hours = random.randint(6, 10)
    end_h = min(23, start_h + play_hours)
    random.seed()                       # balikin randomness normal
    return start_h <= now.hour < end_h
