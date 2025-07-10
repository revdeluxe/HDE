""" Defines the BOARD class that contains the board pin mappings and RF module HF/LF info. """
# -*- coding: utf-8 -*-

# Copyright 2015-2022 Mayer Analytics Ltd.
#
# This file is part of pySX127x.
#
# pySX127x is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public
# License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# pySX127x is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.
#
# You can be released from the requirements of the license by obtaining a commercial license. Such a license is
# mandatory as soon as you develop commercial activities involving pySX127x without disclosing the source code of your
# own applications, or shipping pySX127x with a closed source product.
#
# You should have received a copy of the GNU General Public License along with pySX127.  If not, see
# <http://www.gnu.org/licenses/>.
import RPi.GPIO as GPIO
import spidev
import time

# suppress “already in use” warnings
GPIO.setwarnings(False)

# once we’ve run setup(), flip this to True so we don’t do it again
_board_setup_done = False

class BOARD:
    """Raspberry Pi pin mapping + safe setup/edge-detect for SX127x"""

    # BCM pin numbers
    DIO0   = 22
    DIO1   = 23
    DIO2   = 24
    DIO3   = 25
    LED    = 18
    SWITCH = 4

    # SPI handle storage
    spi = None

    # low_band selects RF_LF vs RF_HF pins on your module
    low_band = True

    @staticmethod
    def setup():
        """Configure LED, SWITCH, DIO0-DIO3 once."""
        global _board_setup_done
        if _board_setup_done:
            return

        GPIO.setmode(GPIO.BCM)

        # LED output
        GPIO.setup(BOARD.LED, GPIO.OUT)
        GPIO.output(BOARD.LED, 0)

        # User switch
        GPIO.setup(BOARD.SWITCH, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

        # DIO0–DIO3 inputs with pulldown
        for pin in (BOARD.DIO0, BOARD.DIO1, BOARD.DIO2, BOARD.DIO3):
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

        # blink twice so you know setup ran
        BOARD.blink(0.1, 2)

        _board_setup_done = True

    @staticmethod
    def teardown():
        """Call at shutdown to release GPIO & SPI."""
        GPIO.cleanup()
        if BOARD.spi:
            BOARD.spi.close()

    @staticmethod
    def SpiDev(spi_bus=0, spi_cs=0):
        """Return a configured spidev.SpiDev instance."""
        BOARD.spi = spidev.SpiDev()
        BOARD.spi.open(spi_bus, spi_cs)
        BOARD.spi.max_speed_hz = 5_000_000
        return BOARD.spi

    @staticmethod
    def add_event_detect(pin, callback=None, bouncetime=None):
        """
        Safely arm an IRQ watcher on `pin`.  
        Removes any old watcher, then tries to add.  
        Ignores RuntimeError if it's already been armed.
        """
        try:
            GPIO.remove_event_detect(pin)
        except (RuntimeError, ValueError):
            pass

        try:
            if bouncetime:
                GPIO.add_event_detect(pin, GPIO.RISING,
                                      callback=callback,
                                      bouncetime=bouncetime)
            else:
                GPIO.add_event_detect(pin, GPIO.RISING,
                                      callback=callback)
        except RuntimeError:
            # > Failed to add edge detection ? already armed
            pass

    @staticmethod
    def add_events(cb_dio0, cb_dio1, cb_dio2, cb_dio3, cb_dio4, cb_dio5, switch_cb=None):
        """
        Wire up DIO0-DIO3 callbacks via our safe helper,
        and optionally watch the SWITCH too.
        """
        BOARD.add_event_detect(BOARD.DIO0, callback=cb_dio0)
        BOARD.add_event_detect(BOARD.DIO1, callback=cb_dio1)
        BOARD.add_event_detect(BOARD.DIO2, callback=cb_dio2)
        BOARD.add_event_detect(BOARD.DIO3, callback=cb_dio3)

        # inAir9B doesn't have DIO4/DIO5 exposed, so ignore those
        if switch_cb:
            BOARD.add_event_detect(BOARD.SWITCH,
                                   callback=switch_cb,
                                   bouncetime=300)

    @staticmethod
    def led_on(value=1):
        GPIO.output(BOARD.LED, value)
        return value

    @staticmethod
    def led_off():
        GPIO.output(BOARD.LED, 0)
        return 0

    @staticmethod
    def blink(time_sec, n_blink):
        """Flash the LED `n_blink` times with `time_sec` intervals."""
        for _ in range(n_blink):
            BOARD.led_on()
            time.sleep(time_sec)
            BOARD.led_off()
            time.sleep(time_sec)
