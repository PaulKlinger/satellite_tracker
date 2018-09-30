import numpy as np
import neopixel
from time import sleep, time
import itertools
from random import randint, shuffle
from collections import defaultdict


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

    for _ in range(int(np.ceil(switch_time / step_time))):
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


def color_gradient_target(strip, tot, saturation=1, lightness=0.5):
    hues = np.linspace(0, 360, strip.numPixels())
    return [np.array(hsl_to_rgbnorm(h, saturation, lightness)) * tot for h in hues]


def chase_loop(strip, step_time=0.03, timeout=None, current=None):
    if current is None:
        set_all(strip, neopixel.Color(0, 0, 0))
    else:
        to_target(strip, current, defaultdict(lambda: (0, 0, 0)))
    current = defaultdict(lambda: (0, 0, 0))
    start_time = time()

    gradient_length = 10
    max_brightness = 255
    offset = gradient_length
    brightness_gradient = [0] * (strip.numPixels() - gradient_length) + [
        int(round(i ** 2 * max_brightness / gradient_length ** 2)) for i in range(1, gradient_length + 1)]

    color_gradient = color_gradient_target(strip, 100)
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

    rings = [range(18), range(18, 18 + 12), range(18 + 12, 18 + 12 + 6), [18 + 12 + 6]]
    rings.reverse()
    colors = [np.array(hsl_to_rgbnorm(h, 1, 0.5)) * 100 for h in np.linspace(0, 360, 4 * 4)]
    shuffle(colors)

    offset = 0
    while True:
        target = defaultdict(lambda: (0, 0, 0))
        for level in range(4):
            for ringid, ring in enumerate(rings):
                for l in ring:
                    target[l + level * (18 + 12 + 6 + 1)] = colors[(level + offset + ringid) % (4 * 4)]
        current = to_target(strip, current, target, step_time)

        if timeout is not None and time() - start_time >= timeout:
            return current

        offset += 1


def init():
    from main import LedArray
    LED_COUNT = 37 * 4  # Number of LED pixels.
    LED_PIN = 18  # GPIO pin connected to the pixels (18 uses PWM!).
    # LED_PIN        = 10      # GPIO pin connected to the pixels (10 uses SPI /dev/spidev0.0).
    LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
    LED_DMA = 11  # DMA channel to use for generating signal (try 10)
    LED_BRIGHTNESS = 50  # Set to 0 for darkest and 255 for brightest
    LED_INVERT = False  # True to invert the signal (when using NPN transistor level shift)
    LED_CHANNEL = 0  # set to '1' for GPIOs 13, 19, 41, 45 or 53
    strip = neopixel.Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA,
                                       LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL,
                                       strip_type=neopixel.ws.WS2811_STRIP_GRB)

    # Intialize the library (must be called once before other functions).
    strip.begin()
    set_all(strip, neopixel.Color(0, 0, 0))

    here = (48.224708, 16.438082)  # lat long

    leds = LedArray([49.0, 32.0, 16.5, 0.0], [18, 12, 6, 1],
                    [-np.pi / 2 + np.deg2rad(10), -np.pi / 2, -np.pi / 2 - np.deg2rad(30), 0], [1, -1, -1, 1], 200,
                    *here, [500, 1000, 2500])

    return strip, leds


if __name__ == "__main__":
    strip, leds = init()
    current = None
    while True:
        current = rings_loop(strip, timeout=5, current=current)
        current = chase_loop(strip, timeout=5, current=current)
        current = random_loop(strip, timeout=5, current=current)
