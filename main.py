from datetime import datetime, timedelta
from time import time, sleep
import itertools
import multiprocessing as mp
import subprocess
import queue
from collections import defaultdict
import os.path
from typing import List, Tuple, Optional

from subprocess import check_call

from geopy import distance
import neopixel
from gpiozero import Button
import RPi.GPIO as GPIO
from LIBtft144.lib_tft144 import TFT144
import spidev

from orbit_np import Orbitals
from demo import chase_loop, random_loop, rings_loop, spinning_loop, alternate_loop, half_loop
from constants import *


class NearbySatFinder(object):
    def __init__(self, tlefile: str, loc: Pos):
        self.loc = loc
        self.longfactor = np.cos(np.deg2rad(loc.lat))
        self.tles = []
        satnames = []

        with open(tlefile) as f:
            n = 0
            while True:
                n += 1
                satname = f.readline().strip()
                if not satname:
                    # there should be exactly one empty line at the end of the TLE file
                    # check if we are at the end of the file after reading it
                    if f.read(1) != "":  # at the end file.read returns ""
                        # if we are not at the end, something is wrong -> abort
                        raise ValueError("Unexpected empty line in TLE file!")

                    print("Loaded {} sats.".format(n))
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
        rough_near = np.logical_and(np.abs(lats - self.loc.lat) < 3, np.abs(lons - self.loc.long) < 3)
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
    def __init__(self, ring_radii, ring_ledns, ring_startangles, ring_dirs, eq_radius, pos: Pos,
                 upper_levels_alt_lower_boundaries):
        self.eq_radius = eq_radius  # equivalent real radius in km
        self.pos = pos
        self.upper_levels_alt_lower_boundaries = upper_levels_alt_lower_boundaries
        self.level_ledn = np.sum(ring_ledns)

        self.longfactor = np.cos(np.deg2rad(self.pos.lat))
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
        y = lat - self.pos.lat
        x = long - self.pos.long

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


def led_array_from_constants():
    # convenience function
    return LedArray(ring_radii=RING_RADII, ring_ledns=RING_LEDNS, ring_startangles=RING_STARTANGLES,
                    ring_dirs=RING_DIRECTIONS, eq_radius=EQUIV_RADIUS, pos=CENTER_LOCATION,
                    upper_levels_alt_lower_boundaries=UPPER_LEVELS_ALT_LOWER_BOUNDARIES)


def color_priority_from_name(name):
    for c, tftc_prio_ledc in CLASS_COLORS_PRIORITIES:
        if any(s in name for s in c):
            return tftc_prio_ledc


def run_demo(strip, led_queue):
    for demo in (chase_loop, spinning_loop, rings_loop, random_loop):
        print("demo: {}".format(demo))
        p = mp.Process(target=demo, kwargs={"strip": strip, })
        p.start()
        sleep(5)  # show each demo for 5s
        while True:
            # get messages, ignore satellite updates that might still be in the queue
            try:
                m = led_queue.get_nowait()
                if m == "BUTTON":  # if the button is pressed we stay in the demo
                    while True:
                        m = led_queue.get()
                        if m == "BUTTON":  # if the button is pressed again we exit
                            p.terminate()
                            return
            except queue.Empty:
                # if there was no button press move on to the next demo
                p.terminate()
                break


def led_strip_from_constants():
    return neopixel.Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA,
                                      LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL,
                                      strip_type=neopixel.ws.WS2811_STRIP_GRB)


def led_control(led_queue: mp.Queue, demo_mode: mp.Lock):
    strip = led_strip_from_constants()

    # Intialize the library (must be called once before other functions).
    strip.begin()

    def set_all(strip, color):
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, color)
        strip.show()

    set_all(strip, neopixel.Color(0, 0, 0))

    current = defaultdict(lambda: RGB(0, 0, 0))  # TODO: add variable type hints once Raspbian includes Python >=3.6
    target = defaultdict(lambda: RGB(0, 0, 0))
    step = defaultdict(lambda: RGB(0, 0, 0))
    loading_anim_process = mp.Process(target=half_loop, args=(strip,))
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
                print("got demo message")
                demo_mode.acquire()
                print("acquired demo lock")
                run_demo(strip, led_queue)
                demo_mode.release()
                continue
            elif message == "BUTTON":
                # pressed the button too late to stay in demo mode, just ignore
                continue

            elif message is None:
                set_all(strip, neopixel.Color(0, 0, 0))
                sleep(0.5)
                break
            for i in range(strip.numPixels()):
                newtarget = message[i][1] if i in message else (0, 0, 0)
                if target[i] != newtarget:
                    target[i] = newtarget
                    step[i] = tuple((t - c) / (LED_SWITCH_TIME / LED_STEP_TIME) for t, c in zip(target[i], current[i]))

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
        if t1 - t0 < LED_STEP_TIME:
            sleep(LED_STEP_TIME - (t1 - t0))


def update_tle_file():
    # TODO: add error handling...
    subprocess.run(
        "curl {} > {}".format(SPACETRACK_URL, TLE_FILENAME),
        shell=True)
    return datetime.now()


class SattrackerTFT(object):
    num_lines = 12
    num_chars = int(128 / 6)

    BLACK = RGB(0, 0, 0)
    WHITE = RGB(255, 255, 255)
    BLUE = RGB(0, 0, 255)

    def __init__(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

        self._tft = TFT144(GPIO, spidev.SpiDev(), TFT_CE, TFT_DC, TFT_RST, TFT_LED, isRedBoard=True, spi_speed=16000000)

        self._prev_lines = self.num_lines * [(None, None, None)]

    def write_message(self, message: str):
        self.clear()
        self._tft.put_string(message, 0, 0, self._tft.WHITE, self._tft.BLACK, font=3)
        self._prev_lines = self.num_lines * [(None, None, None)]

    def clear(self, color: Optional[RGB] = None):
        if color is None:
            color = self._tft.BLACK
        self._tft.clear_display(color)

    def write_lines(self, lines: List[Tuple[str, RGB, RGB]]):
        lines += (self.num_lines - len(lines)) * [(" " * self.num_chars, self.BLACK, self.BLACK)]
        dy = 0
        for ((new_text, new_colorfg, new_colorbg),
             (prev_text, prev_colorfg, prev_colorbg)) in zip(lines, self._prev_lines):

            if new_text != prev_text or new_colorfg != prev_colorfg or new_colorbg != prev_colorbg:
                self._tft.put_chars(new_text, 0, dy,
                                    self._tft.colour565(*new_colorfg),
                                    self._tft.colour565(*new_colorbg))  # std font 3 (default)
            dy += 10

        self._prev_lines = lines


class SatTracker(object):
    def __init__(self):
        self.led_queue = mp.Queue()
        self.demo_mode = mp.Lock()

        self.led_process = mp.Process(target=led_control, args=(self.led_queue, self.demo_mode,))

        self.shutting_down = False
        self.last_button_release = 0
        self.show_end_of_lines = False

        self.button = Button(3, hold_time=2, bounce_time=0.05)
        self.button.when_held = self.shutdown
        self.button.when_released = self.button_pressed

        self.tft = SattrackerTFT()

        self.tle_updated_time = None

        self.tracker = None  # load in start because it takes quite a long time

        self.led_array = led_array_from_constants()

    def start(self):
        self.led_process.start()
        self.tft.clear()

        if (not os.path.isfile(TLE_FILENAME)) or \
                (datetime.now() - datetime.fromtimestamp(os.path.getmtime(TLE_FILENAME))) > timedelta(days=1):
            self.tft.write_message("Downloading TLEs")
            update_tle_file()
        self.tle_updated_time = datetime.fromtimestamp(os.path.getmtime(TLE_FILENAME))

        self.tft.write_message("Loading Satellites")
        self.tracker = NearbySatFinder(TLE_FILENAME, CENTER_LOCATION)
        self.tracker.nearby_now()  # run once to remove errors

        self.loop()

    def loop(self):
        oddstep = False
        while True:
            if not self.demo_mode.acquire(block=False):
                self.tft.write_message("Showing off :D")
                self.demo_mode.acquire()
            self.demo_mode.release()

            step_start_time = time()

            self.check_tle_update()

            nearby_sats = self.tracker.nearby_now()

            tft_lines = [("{:03d} sats<{}km      {}".format(len(nearby_sats), EQUIV_RADIUS, "-" if oddstep else "|"),
                          self.tft.WHITE, self.tft.BLUE)]
            active_leds = {}
            for name, lat, long, alt in nearby_sats:
                _, led_id, _ = self.led_array.closest_led(lat, long, alt)
                tft_color, priority, led_color = color_priority_from_name(name)
                if (led_id not in active_leds) or priority > active_leds[led_id][0]:
                    active_leds[led_id] = (priority, led_color)
                line = name[2:] + " {}km".format(int(round(alt)))
                if self.show_end_of_lines:
                    line = line[-21:]
                line = line[:21] + max(21 - len(line), 0) * " "  # trim to display length and pad
                tft_lines.append((line, tft_color, self.tft.BLACK))

            if self.show_end_of_lines and time() - self.last_button_release > 2:
                self.show_end_of_lines = False
            if self.shutting_down:
                break
            self.led_queue.put_nowait(active_leds)

            self.tft.write_lines(tft_lines)

            oddstep = not oddstep

            step_time = time() - step_start_time
            print("step_time: {:.2f}s".format(step_time))
            if step_time < TARGET_STEP_TIME:
                sleep(TARGET_STEP_TIME - step_time)

    def check_tle_update(self):
        if datetime.now() - self.tle_updated_time > timedelta(days=1):
            self.tft.write_message("Downloading TLEs")
            self.tle_updated_time = update_tle_file()
            self.tft.write_message("Loading Satellites")
            self.tracker = NearbySatFinder("3le.txt", CENTER_LOCATION)
            self.tracker.nearby_now()  # run once to remove errors

    def shutdown(self):
        self.shutting_down = True
        self.led_queue.put_nowait(None)
        sleep(0.5)
        self.tft.write_message("Shutting down...")
        sleep(0.5)
        check_call(['sudo', 'poweroff'])
        sleep(10)

    def button_pressed(self):
        if time() - self.last_button_release < 1:
            self.led_queue.put_nowait("DEMO")
        else:
            if not self.demo_mode.acquire(block=False):
                self.led_queue.put("BUTTON")
            else:
                self.demo_mode.release()
                self.show_end_of_lines = True
                self.last_button_release = time()


if __name__ == "__main__":
    sat_tracker = SatTracker()
    sat_tracker.start()
