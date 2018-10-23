from collections import namedtuple
import numpy as np

from credentials import SPACETRACK_PASSWD, SPACETRACK_USER

Pos = namedtuple("Pos", "lat long")
RGB = namedtuple("RGB", "r g b")

# Constants determining device behavior
CENTER_LOCATION = Pos(lat=48.224708, long=16.438082)
TARGET_STEP_TIME = 0.5  # s target delta-t between sat position updates
EQUIV_RADIUS = 200  # km
LED_STEP_TIME = 1 / 60.  # s
LED_SWITCH_TIME = 0.5  # s
# sats lower than the first entry will be displayed in the lowest ring,
# those between the first and second in the second ring, and so on
UPPER_LEVELS_ALT_LOWER_BOUNDARIES = [500, 1000, 2500]
# --------------------------------------------------------------


# TLE constants
SPACETRACK_URL = ("https://www.space-track.org/ajaxauth/login -d"
                  "'identity={}&password={}"
                  "&query=https://www.space-track.org/basicspacedata/query/"
                  "class/tle_latest/ORDINAL/1/EPOCH/%3Enow-30/orderby/NORAD_CAT_ID/format/3le'"
                  ).format(SPACETRACK_USER, SPACETRACK_PASSWD)
TLE_FILENAME = "3le.txt"
# --------------------------------------------------------------


# Satellite categorization constants

# - if multiple sats would be displayed on the same led the one with the higher
#   priority wins
#
# - tft shows colors a bit differently than leds, so define separate
#   satellite names
#
# - Satellite names are compared against all the substrings in order.
#   If one matches the satellite is in that class.

HIGHLY_INTERESTING_CLASS = ["ISS", "TIANGONG", "DRAGON", "SOYUZ", "PROGRESS", "HST", "CYGNUS", "GP-B", "TINTIN"]
PLANETLABS_CLASS = ["FLOCK", "DOVE"]

CLASS_COLORS_PRIORITIES = [  # [substring, substring,...]: (tft_color, priority, led_color)
    (["DEB"], (RGB(255, 0, 0), 0, RGB(255, 0, 0))),
    (["R/B"], (RGB(255, 90, 0), 1, RGB(188, 86, 0))),
    (PLANETLABS_CLASS, (RGB(0, 0, 255), 2, RGB(0, 0, 255))),
    (HIGHLY_INTERESTING_CLASS, (RGB(0, 255, 0), 10, RGB(0, 255, 0))),
    ([""], (RGB(255, 255, 255), 2, RGB(255 // 3, 255 // 3, 255 // 3))),  # wildcard
]
# --------------------------------------------------------------


# constants describing the arrangement of the LEDs
RING_RADII = [47.5, 32.0, 16.5, 0.0]
RING_LEDNS = [18, 12, 6, 1]
RING_STARTANGLES = [-np.pi / 2 + np.deg2rad(10), -np.pi / 2, -np.pi / 2 - np.deg2rad(30), 0]
RING_DIRECTIONS = [1, -1, -1, 1]  # I connected the LEDs in the first ring in the opposite direction for some reason...
# --------------------------------------------------------------

# constants related to the WS2812B LEDs
LED_COUNT = 37 * 4  # Number of LED pixels.
LED_PIN = 18  # GPIO pin connected to the pixels (18 uses PWM!).
# LED_PIN        = 10      # GPIO pin connected to the pixels (10 uses SPI /dev/spidev0.0).
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA = 11  # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 50  # Set to 0 for darkest and 255 for brightest
LED_INVERT = False  # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL = 0  # set to '1' for GPIOs 13, 19, 41, 45 or 53
# --------------------------------------------------------------


# constants related to the spi tft display
# Don't forget the other 2 SPI pins SCK and MOSI (SDA)
TFT_RST = 23
TFT_CE = 0  # 0 or 1 for CE0 / CE1 number (NOT the pin#)
TFT_DC = 22  # Labeled on board as "A0"
TFT_LED = 24  # LED backlight sinks 10-14 mA @ 3V
# --------------------------------------------------------------

# calculated constants for demo.py
def ring_led_indices():
    led_index = 0
    indices = []
    for nleds, direction in zip(RING_LEDNS, RING_DIRECTIONS):
        indices.append(list(range(led_index, led_index + nleds)))
        if direction == 1:
            indices[-1].reverse()
        led_index += nleds
    indices.reverse()
    return indices


RING_LED_INDICES = ring_led_indices()
LEVEL_LEDN = sum(RING_LEDNS)
# --------------------------------------------------------------
