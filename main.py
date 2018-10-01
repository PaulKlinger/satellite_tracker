from datetime import datetime, timedelta
from time import time, sleep
import itertools
import multiprocessing as mp
import subprocess
import queue
from collections import defaultdict
import os.path

import numpy as np
from geopy import distance

from orbit_np import Orbitals
from demo import chase_loop, random_loop, rings_loop, spinning_loop, alternate_loop


class SatTracker(object):
    def __init__(self, tlefile, loc):
        self.loc = loc  # lat long
        self.longfactor = np.cos(np.deg2rad(loc[0]))
        self.tles = []
        satnames = []

        with open(tlefile) as f:
            while True:
                satname = f.readline().strip()
                if not satname:
                    print(satname)
                    print(line1)
                    print("-----")
                    break
                line1 = f.readline().strip()
                line2 = f.readline().strip()
                if line1 and line2:
                    self.tles.append((line1, line2))
                    satnames.append(satname)

        self.satnames = np.array(satnames)

        self.last_query_t = -1000

        self.filtered_errors = False
        self.create_orbitals()

    def create_orbitals(self):
        print("creating orbitals")
        self.orbs = Orbitals(self.tles)

    def nearby_now(self):
        now = datetime.utcnow()

        t1 = time()
        self.last_query_t = t1

        lons, lats, alts, errors = self.orbs.get_lonlatalt(now)
        t2 = time()
        rough_near = np.logical_and(np.abs(lats - self.loc[0]) < 3, np.abs(lons - self.loc[1]) < 3)
        valid_satpos = list(
            zip(self.satnames[~errors][rough_near], lats[rough_near], lons[rough_near], alts[rough_near]))
        nearby = [(name, lat, lon, alt) for name, lat, lon, alt in valid_satpos if
                  distance.distance(self.loc, (lat, lon)).km < 200]
        t3 = time()
        print("loc:{:.2f}s dist: {:.2f}s tot: {:.2f}s, sats: {:02d}".format(t2 - t1, t3 - t2, t3 - t1, len(nearby)))

        if not self.filtered_errors:
            print("filtering errors")
            self.satnames = self.satnames[~errors]
            self.tles = itertools.compress(self.tles, ~errors)
            self.create_orbitals()
            self.filtered_errors = True
        return nearby


class LedArray(object):
    def __init__(self, ring_radii, ring_ledns, ring_startangles, ring_dirs, eq_radius, lat, long,
                 upper_levels_alt_lower_boundaries):
        self.eq_radius = eq_radius  # equivalent real radius in km
        self.lat = lat
        self.long = long
        self.upper_levels_alt_lower_boundaries = upper_levels_alt_lower_boundaries
        self.level_ledn = np.sum(ring_ledns)

        self.longfactor = np.cos(np.deg2rad(lat))
        degreelength = 111  # km
        self.levels_led_poss = []
        distance_factor = eq_radius / np.max(ring_radii)
        for level in range(len(upper_levels_alt_lower_boundaries) + 1):
            led_poss = []
            for ringr, ledn, startangle, direction in zip(ring_radii, ring_ledns, ring_startangles, ring_dirs):
                startangle += (level % 2) * np.pi  # upper levels are rotated 180 degree (to connect do/di)
                anglestep = 2 * np.pi / ledn
                led_poss += [(-distance_factor * ringr * np.cos(startangle + i * anglestep * direction) / degreelength,
                              distance_factor * ringr * np.sin(
                                  startangle + i * anglestep * direction) / degreelength / self.longfactor
                              ) for i in range(ledn)]
            self.levels_led_poss.append(led_poss)

    def _level_from_alt(self, alt):
        i = 0
        for alt_boundary in self.upper_levels_alt_lower_boundaries:
            if alt < alt_boundary:
                break
            i += 1
        return i

    def closest_led(self, lat, long, alt):
        y = lat - self.lat
        x = long - self.long

        level = self._level_from_alt(alt)
        closest_led_index = None
        closest_led_distance = (2 * self.eq_radius) ** 2
        for i, ledpos in enumerate(self.levels_led_poss[level]):
            d = ((ledpos[1] - x) * self.longfactor) ** 2 + (ledpos[0] - y) ** 2
            if d < closest_led_distance:
                closest_led_distance = d
                closest_led_index = i

        closest_led_pos = self.levels_led_poss[level][closest_led_index]
        closest_led_index += level * self.level_ledn
        return closest_led_pos, closest_led_index, closest_led_distance


HERE = (48.224708, 16.438082)  # lat long

HIGHLY_INTERESTING_CLASS = ["ISS", "TIANGONG", "DRAGON", "SOYUZ", "PROGRESS", "HST", "CYGNUS", "GP-B", "TINTIN"]
PLANETLABS_CLASS = ["FLOCK", "DOVE"]

CLASS_COLORS_PRIORITIES = [  # [substring, substring,...]: (tft_color, priority, led_color)
    (["DEB"], ((255, 0, 0), 0, (255, 0, 0))),
    (["R/B"], ((255, 90, 0), 1, (188, 86, 0))),
    (PLANETLABS_CLASS, ((0, 0, 255), 2, (0, 0, 255))),
    (HIGHLY_INTERESTING_CLASS, ((0, 255, 0), 10, (0, 255, 0))),
    ([""], ((255, 255, 255), 2, (255 // 3, 255 // 3, 255 // 3))),  # wildcard
]


def color_priority_from_name(name):
    for c, tftc_prio_ledc in CLASS_COLORS_PRIORITIES:
        if any(s in name for s in c):
            return tftc_prio_ledc


def run_demo(strip):
    current = chase_loop(strip, timeout=5)
    current = spinning_loop(strip, current=current, timeout=5)
    current = rings_loop(strip, current=current, timeout=5)
    current = random_loop(strip, current=current, timeout=5)


def led_control(led_queue):
    import neopixel

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

    def set_all(strip, color):
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, color)
        strip.show()

    set_all(strip, neopixel.Color(0, 0, 0))



    stepsize = 1 / 60.  # s
    switch_time = 0.5  # s

    current = defaultdict(lambda: (0, 0, 0))
    target = defaultdict(lambda: (0, 0, 0))
    step = defaultdict(lambda: (0, 0, 0))
    loading_anim_process = mp.Process(target=alternate_loop, args=(strip,))
    loading_anim_process.start()
    m = led_queue.get()
    loading_anim_process.terminate()
    led_queue.put(m)  # ugly...

    while True:
        t0 = time()
        try:
            message = led_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            if message == "DEMO":
                run_demo(strip)
                continue

            elif message is None:
                set_all(strip, neopixel.Color(0, 0, 0))
                sleep(0.5)
                break
            for i in range(strip.numPixels()):
                target[i] = message[i][1] if i in message else (0, 0, 0)
                step[i] = tuple((t - c) / (switch_time / stepsize) for t, c in zip(target[i], current[i]))

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
        if t1 - t0 < stepsize:
            sleep(stepsize - (t1 - t0))


def update_tle_file():
    # TODO: add error handling...
    subprocess.run(
        ("curl https://www.space-track.org/ajaxauth/login -d"
         "'identity=***REMOVED***&password=***REMOVED***"
         "&query=https://www.space-track.org/basicspacedata/query/"
         "class/tle_latest/ORDINAL/1/EPOCH/%3Enow-30/orderby/NORAD_CAT_ID/format/3le'"
         "> 3le.txt"),
        shell=True)
    return datetime.now()


TARGET_STEP_TIME = 0.5  # s target delta-t between sat position updates
EQUIV_RADIUS = 200  # km


def main_loop():
    from gpiozero import Button
    from subprocess import check_call

    led_queue = mp.Queue()

    led_process = mp.Process(target=led_control, args=(led_queue,))
    led_process.start()

    shutting_down = False

    def shutdown():
        nonlocal shutting_down
        shutting_down = True
        led_queue.put_nowait(None)
        sleep(0.5)
        write_message("Shutting down...")
        sleep(0.5)
        check_call(['sudo', 'poweroff'])
        sleep(10)

    def button_pressed():
        nonlocal last_button_release, show_end_of_lines
        if time() - last_button_release < 1:
            led_queue.put_nowait("DEMO")
            sleep(10)
        else:
            show_end_of_lines = True
            last_button_release = time()

    the_btn = Button(3, hold_time=2, bounce_time=0.05)
    the_btn.when_held = shutdown
    last_button_release = 0
    the_btn.when_released = button_pressed

    import RPi.GPIO as GPIO
    from LIBtft144.lib_tft144 import TFT144
    import spidev

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    RST = 23
    CE = 0  # 0 or 1 for CE0 / CE1 number (NOT the pin#)
    DC = 22  # Labeled on board as "A0"
    LED = 24  # LED backlight sinks 10-14 mA @ 3V

    # Don't forget the other 2 SPI pins SCK and MOSI (SDA)

    TFT = TFT144(GPIO, spidev.SpiDev(), CE, DC, RST, LED, isRedBoard=True, spi_speed=16000000)

    def write_message(message):
        TFT.clear_display(TFT.BLACK)
        TFT.put_string(message, 0, 0, TFT.WHITE, TFT.BLACK)

    TFT.clear_display(TFT.BLACK)

    FILENAME = "3le.txt"
    if (not os.path.isfile(FILENAME)) or \
            (datetime.now() - datetime.fromtimestamp(os.path.getmtime(FILENAME))) > timedelta(days=1):
        write_message("Downloading TLEs")
        update_tle_file()
    tle_updated_time = datetime.fromtimestamp(os.path.getmtime(FILENAME))

    write_message("Loading Satellites")
    tracker = SatTracker(FILENAME, HERE)

    leds = LedArray([49.0, 32.0, 16.5, 0.0], [18, 12, 6, 1],
                    [-np.pi / 2 + np.deg2rad(10), -np.pi / 2, -np.pi / 2 - np.deg2rad(30), 0], [1, -1, -1, 1],
                    EQUIV_RADIUS, *HERE, [500, 1000, 2500])

    tracker.nearby_now()  # run once to remove errors
    oddstep = True
    show_end_of_lines = False
    prev_strings = 12 * [(" " * int(128 / 6), TFT.BLACK)]
    while True:
        step_start_time = time()
        if datetime.now() - tle_updated_time > timedelta(days=1):
            write_message("Downloading TLEs")
            tle_updated_time = update_tle_file()
            write_message("Loading Satellites")
            tracker = SatTracker("3le.txt", HERE)
            tracker.nearby_now()  # run once to remove errors

        nearby_sats = tracker.nearby_now()

        strings = []
        active_leds = {}
        for name, lat, long, alt in nearby_sats:
            _, led_id, _ = leds.closest_led(lat, long, alt)
            tft_color, priority, led_color = color_priority_from_name(name)
            if (led_id not in active_leds) or priority > active_leds[led_id][0]:
                active_leds[led_id] = (priority, led_color)
            line = name[2:] + " {}km".format(int(round(alt)))
            if show_end_of_lines:
                line = line[-21:]
            line = line[:21] + max(21 - len(line), 0) * " "  # trim to display length and pad
            strings.append((line, TFT.colour565(*tft_color)))

            # print(f"led {i}, dist {d}km")
        if show_end_of_lines and time() - last_button_release > 2:
            show_end_of_lines = False
        if shutting_down:
            break
        led_queue.put_nowait(active_leds)
        strings += (12 - len(strings)) * [(" " * int(128 / 6), TFT.BLACK)]

        TFT.put_chars("{:03d} sats<{}km      {}".format(len(nearby_sats), EQUIV_RADIUS, "-" if oddstep else "|"),
                      0, 0, TFT.WHITE, TFT.BLUE)
        oddstep = not oddstep
        dy = 10
        for (s, c), (prev_s, _) in zip(strings, prev_strings):
            if s != prev_s:
                TFT.put_chars(s, 0, dy, c, TFT.BLACK)  # std font 3 (default)
            dy += 10
        prev_strings = strings

        step_time = time() - step_start_time
        print("step_time: {:.2f}s".format(step_time))
        if step_time < TARGET_STEP_TIME:
            sleep(TARGET_STEP_TIME - step_time)


if __name__ == "__main__":
    main_loop()
    # pygame_demo()
