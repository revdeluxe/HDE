# SX127x/board_config.py

import os
import time
import spidev
import RPi.GPIO as GPIO

# If SKIP_HW=1 or true in env, we won't touch any GPIO
SKIP_HW = os.getenv('SKIP_HW', '').lower() in ('1', 'true')

# suppress warnings about pins already in use
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# ensure we only do setmode()/setup() once
_board_setup_done = False

class BOARD:
    """Raspberry Pi BCM pin mapping + safe setup for SX1278x"""

    # BCM pin numbers
    RESET = 17
    DIO0  = 22
    DIO1  = 23  # only if you wire it

    # holds the spidev handle
    spi = None

    @staticmethod
    def setup():
        global _board_setup_done

        if SKIP_HW:
            print(f"[BOARD] setup skipped (SKIP_HW={SKIP_HW})")
            return
        if _board_setup_done:
            return

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        try:
            GPIO.cleanup()
        except:
            pass

        def safe_setup(pin, direction, **kwargs):
            try:
                GPIO.setup(pin, direction, **kwargs)
            except Exception as e:
                print(f"[WARN] GPIO.setup(pin={pin}) failed: {e}")

        # 1) NSS / CS for SPI  
        safe_setup(BOARD, GPIO.OUT, initial=GPIO.HIGH)

        # 2) RESET: start released (HIGH), then pulse LOW→HIGH
        safe_setup(BOARD.RESET, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.output(BOARD.RESET, GPIO.LOW)
        time.sleep(0.01)                # 10 ms reset pulse
        GPIO.output(BOARD.RESET, GPIO.HIGH)
        time.sleep(0.01)                # 10 ms for internal boot

        # 3) DIO0 / DIO1 interrupts
        safe_setup(BOARD.DIO0, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        safe_setup(BOARD.DIO1, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

        _board_setup_done = True
        print("[BOARD] hardware setup complete")

        @staticmethod
        def teardown():
            """Release all GPIO & SPI on shutdown."""
            try:
                GPIO.cleanup()
            except Exception:
                pass
            if BOARD.spi:
                try:
                    BOARD.spi.close()
                except Exception:
                    pass

    @staticmethod
    def SpiDev(spi_bus=0, spi_cs=0):
        """
        Return a configured spidev.SpiDev instance on (bus, cs).
        This uses CE0 (GPIO8) or CE1 (GPIO7) under the hood.
        """
        BOARD.spi = spidev.SpiDev()
        BOARD.spi.open(spi_bus, spi_cs)
        BOARD.spi.max_speed_hz = 5_000_000
        return BOARD.spi

    @staticmethod
    def add_event_detect(pin, callback=None, bouncetime=None):
        """
        Safely arm an IRQ watcher on `pin`.
        Removes any old watcher, then tries to add.
        Ignores errors if it's already armed or unavailable.
        """
        try:
            GPIO.remove_event_detect(pin)
        except Exception:
            pass

        try:
            if bouncetime:
                GPIO.add_event_detect(
                    pin, GPIO.RISING, callback=callback, bouncetime=bouncetime
                )
            else:
                GPIO.add_event_detect(pin, GPIO.RISING, callback=callback)
        except Exception:
            pass

    @staticmethod
    @staticmethod
    def add_events(cb_dio0=None, cb_dio1=None,
                   cb_dio2=None, cb_dio3=None,
                   cb_dio4=None, cb_dio5=None,
                   switch_cb=None):
        """Matches SX127x.LoRa.__init__ signature"""

        # Only wire DIO0-DIO1; others are ignored unless you add them later
        if cb_dio0:
            BOARD.add_event_detect(BOARD.DIO0, callback=cb_dio0)
        if cb_dio1:
            BOARD.add_event_detect(BOARD.DIO1, callback=cb_dio1)

        # DIO2 DIO5 are not wired, so skip safely
        for cb, pin in zip(
            [cb_dio2, cb_dio3, cb_dio4, cb_dio5],
            [None, None, None, None]  # or GPIO24 GPIO27 if you expand later
        ):
            if cb and pin:
                BOARD.add_event_detect(pin, callback=cb)

        # Ignore switch_cb unless you wire SWITCH

    @staticmethod
    def set_mode_bcm():
        """Expose setmode if ever needed elsewhere."""
        GPIO.setmode(GPIO.BCM)
