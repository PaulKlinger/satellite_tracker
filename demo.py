import numpy as np
import math
import neopixel
from time import sleep, time
import itertools
from random import randint, shuffle
from collections import defaultdict

from constants import RING_LEDNS, LEVEL_LEDN, RING_LED_INDICES


def set_all(strip, color, show=True):
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
    if show:
        strip.show()


def running(strip):
    i = 0
    while True:
        i = (i + 1) % strip.numPixels()
        set_all(strip, neopixel.Color(0, 0, 0))
        strip.setPixelColor(i, neopixel.Color(30, 0, 0))
        strip.show()
        sleep(0.3)


def lat_sweep(strip, leds):
    for alt in itertools.cycle([300, 800, 1500, 3000]):
        for deltalat in np.linspace(-2, 2, 20):
            _, ledid, _ = leds.closest_led(leds.lat + deltalat, leds.long, alt)
            set_all(strip, neopixel.Color(0, 0, 0))
            strip.setPixelColor(int(ledid), neopixel.Color(30, 0, 0))
            strip.show()
            sleep(0.2)


def long_sweep(strip, leds):
    for alt in itertools.cycle([300, 800, 1500, 3000]):
        for deltalong in np.linspace(-2, 2, 20):
            _, ledid, _ = leds.closest_led(leds.lat, leds.long + deltalong, alt)
            set_all(strip, neopixel.Color(0, 0, 0))
            strip.setPixelColor(int(ledid), neopixel.Color(30, 0, 0))
            strip.show()
            sleep(0.2)


def to_target(strip, current, target, switch_time=0.5, step_time=1 / 30.):
    tot_t0 = time()
    step = defaultdict(lambda: (0, 0, 0))
    for i in range(strip.numPixels()):
        step[i] = tuple((t - c) / (switch_time / step_time) for t, c in zip(target[i], current[i]))

    for _ in range(math.ceil(switch_time / step_time)):
        t0 = time()
        for i in range(strip.numPixels()):
            current[i] = tuple(c + s for c, s in zip(current[i], step[i]))
            if any((s < 0 and c < t) or (s > 0 and c > t) for s, c, t in zip(step[i], current[i], target[i])):
                step[i] = (0, 0, 0)
                current[i] = target[i]
            color_int = tuple(int(round(c)) for c in current[i])

            # cut off at low intensity to remove perceived flicker
            # using gamma correction would be better maybe?
            color_int = tuple(0 if c < 10 and s < 0 else c for c, s in zip(color_int, step[i]))
            strip.setPixelColor(i, neopixel.Color(*color_int))

        strip.show()
        t1 = time()
        if t1 - t0 < step_time:
            sleep(step_time - (t1 - t0))
        else:
            print("too slow!")
    # print("{:.3f}s transition".format(time()-tot_t0))
    return current


def random_target(strip, tot=100):
    target = {}
    for i in range(strip.numPixels()):
        r, g, b = randint(0, 255), randint(0, 255), randint(0, 255)
        rtot = r + g + b + 1  # prevent div by 0
        target[i] = [int(r * tot / rtot), int(g * tot / rtot), int(b * tot / rtot)]
    return target


def random_hue_target(strip, saturation=1, lightness=0.5, tot=100):
    target = {}
    for i in range(strip.numPixels()):
        rgb = np.array(hsl_to_rgbnorm(randint(0, 360), saturation, lightness))
        target[i] = rgb * tot / np.sum(rgb)

    return target


def random_loop(strip, switch_time=0.5, total_brightness=100, timeout=None, current=None):
    if current is None:
        set_all(strip, neopixel.Color(0, 0, 0))
        current = defaultdict(lambda: (0, 0, 0))
    start_time = time()
    while True:
        target = random_hue_target(strip, tot=total_brightness)
        current = to_target(strip, current, target, switch_time)
        if timeout is not None and time() - start_time >= timeout:
            return current


def hsl_to_rgbnorm(h, s, l):
    c = (1 - np.abs(2 * l - 1)) * s
    hp = h / 60
    x = c * (1 - np.abs(hp % 2 - 1))
    r1, g1, b1 = (c, x, 0) if 0 <= hp <= 1 else (x, c, 0) if 1 <= hp <= 2 else (0, c, x) if 2 <= hp <= 3 else \
        (0, x, c) if 3 <= hp <= 4 else (x, 0, c) if 4 <= hp <= 5 else (c, 0, x)
    m = l - c / 2
    return (r1 + m, g1 + m, b1 + m)


def full_color_gradient(n, tot, saturation=1, lightness=0.5):
    hues = np.linspace(0, 360, n)
    return [np.array(hsl_to_rgbnorm(h, saturation, lightness)) * tot for h in hues]


def chase_loop(strip, step_time=0.03, timeout=None, current=None):
    if current is None:
        set_all(strip, neopixel.Color(0, 0, 0))
    else:
        to_target(strip, current, defaultdict(lambda: (0, 0, 0)))
    start_time = time()

    gradient_length = 10
    max_brightness = 255
    offset = gradient_length
    brightness_gradient = [0] * (strip.numPixels() - gradient_length) + [
        int(round(i ** 2 * max_brightness / gradient_length ** 2)) for i in range(1, gradient_length + 1)]

    color_gradient = full_color_gradient(strip.numPixels(), 100)
    while True:
        step_t0 = time()
        current = {}
        for i in range(strip.numPixels()):
            current[i] = brightness_gradient[(i - offset) % strip.numPixels()] * color_gradient[i] / 100
            strip.setPixelColor(i, neopixel.Color(int(current[i][0]), int(current[i][1]), int(current[i][2])))
        strip.show()
        elapsed = time() - step_t0
        if elapsed < step_time:
            sleep(step_time - elapsed)
        if timeout is not None and time() - start_time >= timeout:
            return current
        offset += 1


def rings_loop(strip, step_time=0.25, timeout=None, current=None):
    if current is None:
        set_all(strip, neopixel.Color(0, 0, 0))
        current = defaultdict(lambda: (0, 0, 0))
    start_time = time()

    colors = [np.array(hsl_to_rgbnorm(h, 1, 0.5)) * 100 for h in np.linspace(0, 360, 4 * 4)]
    shuffle(colors)

    offset = 0
    while True:
        target = defaultdict(lambda: (0, 0, 0))
        for level in range(4):
            for ringid, ring in enumerate(RING_LED_INDICES):
                for l in ring:
                    target[l + level * LEVEL_LEDN] = colors[(level + offset + ringid) % (4 * 4)]
        current = to_target(strip, current, target, step_time)

        if timeout is not None and time() - start_time >= timeout:
            return current

        offset += 1


def spinning_loop(strip, step_time=0.1, timeout=None, current=None):
    if current is None:
        set_all(strip, neopixel.Color(0, 0, 0))
        current = defaultdict(lambda: (0, 0, 0))
    start_time = time()

    max_brightness = 255
    brightness_gradients = [[
        int(round(i ** 2 * max_brightness / gradient_length ** 2)) for i in range(1, gradient_length + 1)] for
        gradient_length in reversed(RING_LEDNS)]

    color_gradient = full_color_gradient(strip.numPixels(), 100)

    offset = 0
    while True:
        target = {}
        for level in range(4):
            for ring_id, ring in enumerate(RING_LED_INDICES):
                direction = (1 - 2 * ((ring_id + level) % 2))
                for led_ring_id, led_level_id in enumerate(ring):
                    led_id = led_level_id + level * LEVEL_LEDN
                    target[led_id] = (
                            brightness_gradients[ring_id][
                                ((led_ring_id - direction * offset) * direction) %
                                RING_LEDNS[::-1][ring_id]] *
                            color_gradient[led_id] / 100)
        current = to_target(strip, current, target, step_time)

        if timeout is not None and time() - start_time >= timeout:
            return current

        offset += 1


def alternate_loop(strip, step_time=0.4, timeout=None, current=None):
    if current is None:
        set_all(strip, neopixel.Color(0, 0, 0))
        current = defaultdict(lambda: (0, 0, 0))
    start_time = time()

    gradient_length = 10
    color_gradient = full_color_gradient(gradient_length, 100)

    offset = 0
    while True:
        target = {}
        for i in range(strip.numPixels()):
            target[i] = (i + offset) % 2 * color_gradient[offset % gradient_length]
        current = to_target(strip, current, target, step_time)

        if timeout is not None and time() - start_time >= timeout:
            return current

        offset += 1


def half_loop(strip, step_time=0.5, color=(0, 100, 0), timeout=None, current=None):
    if current is None:
        set_all(strip, neopixel.Color(0, 0, 0))
        current = defaultdict(lambda: (0, 0, 0))
    start_time = time()
    active_leds = [False] * math.ceil(strip.numPixels()) + [True] * math.floor(strip.numPixels())
    while True:
        shuffle(active_leds)
        target = {i: color if a else (0, 0, 0) for i, a in enumerate(active_leds)}
        current = to_target(strip, current, target, step_time)

        if timeout is not None and time() - start_time >= timeout:
            return current


def init():
    from main import led_strip_from_constants, led_array_from_constants

    strip = led_strip_from_constants()

    # Intialize the library (must be called once before other functions).
    strip.begin()
    set_all(strip, neopixel.Color(0, 0, 0))

    leds = led_array_from_constants()

    return strip, leds


if __name__ == "__main__":
    strip, leds = init()
    current = None
    while True:
        current = spinning_loop(strip, timeout=5, current=current)
        current = rings_loop(strip, timeout=5, current=current)
        current = chase_loop(strip, timeout=5, current=current)
        current = half_loop(strip, timeout=5, current=current)
        current = alternate_loop(strip, timeout=5, current=current)
        current = random_loop(strip, timeout=5, current=current)
