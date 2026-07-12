import random, time

def human_delay(mean=1.5, sigma=0.4, floor=0.3):
    d = max(floor, random.gauss(mean, sigma))
    time.sleep(d)
    return d

def think_pause():
    if random.random() < 0.15:
        time.sleep(random.uniform(4, 14))

def jitter(x, y, radius=8):
    return (x + random.randint(-radius, radius),
            y + random.randint(-radius, radius))
