"""
implement pcf8523 rtc
https://www.nxp.com/docs/en/data-sheet/PCF8523.pdf
"""

from datetime import datetime
import smbus2 as smbus


class Reg:
    """registers"""

    CONTROL_1 = 0x00
    CONTROL_2 = 0x01
    CONTROL_3 = 0x03
    SECONDS = 0x03
    MINUTES = 0x04
    HOURS = 0x05
    DAYS = 0x06
    WEEKDAY = 0x07
    MONTH = 0x08
    YEAR = 0x09

    # alarm
    ALARM_MINUTES = 0x0A
    ALARM_HOURS = 0x0B
    ALARM_DAY = 0x0C
    ALARM_WEEKDAY = 0x0D
    
    # not used
    RESERVED = 0x0E

    CLK_OUT = 0x0F
    TIMER = 0x0F

# === magic bytes ===
ALARM_IGNORE = 0x80

RTC_RESET = 0x58

# clock-out frequencies
CLOCK_CLK_OUT_FREQ_32_DOT_768KHZ = 0x80
CLOCK_CLK_OUT_FREQ_1_DOT_024KHZ = 0x81
CLOCK_CLK_OUT_FREQ_32_KHZ = 0x82
CLOCK_CLK_OUT_FREQ_1_HZ = 0x83
CLOCK_CLK_HIGH_IMPEDANCE = 0x0  

IGNORE_LAST_BIT = 0x7F

def bcd_to_int(bcd):
    """
    2x4bit bcd to integer
    """
    return bcd // 16 * 10 + bcd % 16


def int_to_bcd(n):
    """
    one/two digits int to bcd format
    """
    return n // 10 * 16 + n % 10


def assert_clock_inputs(seconds=None, minutes=None, hours=None, days=None, month=None, year=None, weekday=None):
        
        if seconds is not None:
            assert 0 <= seconds <= 59, 'invalid seconds %s' % seconds

        if minutes is not None:
            assert 0 <= minutes <= 59, 'invalid minutes %s' % minutes

        if hours is not None:
            assert 0 <= hours <= 23, 'invalid hours %s' % hours

        if days is not None:
            assert 1 <= days <= 31, 'invalid days %s' % days

        if month is not None:
            assert 1 <= month <= 12, 'invalid month %s' % month

        if year is not None:
            assert 0 <= year <= 99, 'invalid year %s' % year

        if weekday is not None:
            assert 1 <= weekday <= 7, 'invalid weekday %s' % weekday


class PCF8523:

    def __init__(self, dev=1, addr=0x68):
        self.bus = smbus.SMBus(dev)
        self.addr = addr

    def read_str(self):
        """
        return 'yy-dd-mm HH:MM:SS'
        """
        return '{:02d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}'.format(
            self.read_year(), self.read_month(), self.read_date(),
            self.read_hours(), self.read_minutes(), self.read_seconds()
        )

    def read_datetime(self, century=21, tzinfo=None):
        """
        return datetime object
        """
        return datetime((century - 1) * 100 + self.read_year(),
                        self.read_month(), self.read_date(), self.read_hours(),
                        self.read_minutes(), self.read_seconds(), 0, tzinfo=tzinfo)
    
    def reset(self):
        self.write(Reg.CONTROL_1, RTC_RESET)

    def set_alarm(self, min=1, hour=None, day=None, weekday=None):
        """
        whenever clock matches these values a falling edge interrupt is triggered
        """

        assert_clock_inputs(minutes=min, hours=hour, days=day, weekday=weekday)

        alarm_minute = ALARM_IGNORE
        alarm_hour = ALARM_IGNORE
        alarm_day = ALARM_IGNORE
        alarm_weekday = ALARM_IGNORE

        if min is not None:
            alarm_minute = int_to_bcd(min) & IGNORE_LAST_BIT

        if hour is not None:
            alarm_hour = int_to_bcd(hour) & IGNORE_LAST_BIT

        if day is not None:
            alarm_day = int_to_bcd(day) & IGNORE_LAST_BIT

        if weekday is not None:
            alarm_weekday = int_to_bcd(weekday) & IGNORE_LAST_BIT

        self.write(Reg.ALARM_MINUTES, alarm_minute)
        self.write(Reg.ALARM_HOURS, alarm_hour)
        self.write(Reg.ALARM_DAY, alarm_day)
        self.write(Reg.ALARM_WEEKDAY, alarm_weekday)

        self.enable_alarm_interrupt()

    def write_datetime(self, dt):
        self.write_all(dt.second, dt.minute, dt.hour,
                        dt.day, dt.month, dt.year % 100, dt.isoweekday())

    def write_now(self):
        self.write_datetime(datetime.now())

    def write(self, register, data):
        self.bus.write_byte_data(self.addr, register, data)

    def read(self, register):
        return self.bus.read_byte_data(self.addr, register)

    def read_seconds(self):
        return bcd_to_int(self.read(Reg.SECONDS) & IGNORE_LAST_BIT)

    def read_minutes(self):
        return bcd_to_int(self.read(Reg.MINUTES) & IGNORE_LAST_BIT)

    def read_hours(self):
        return bcd_to_int(self.read(Reg.HOURS) & 0x3F)

    def read_day(self):
        return bcd_to_int(self.read(Reg.WEEKDAY) & 0x07)

    def read_date(self):
        return bcd_to_int(self.read(Reg.DAYS) & 0x3F)

    def read_month(self):
        return bcd_to_int(self.read(Reg.MONTH) & 0x1F)

    def read_year(self):
        return bcd_to_int(self.read(Reg.YEAR))

    def read_all(self):
        """
        return (year, month, date, day, hours, minutes, seconds)
        """
        return (self.read_year(), self.read_month(), self.read_date(),
                self.read_day(), self.read_hours(), self.read_minutes(),
                self.read_seconds())


    def write_all(self, seconds=None, minutes=None, hours=None,
                  date=None, month=None, year=None, iso_week_day=None):
        """
        write values with range assertion
        """

        assert_clock_inputs(seconds, minutes, hours, date, month, year, iso_week_day)

        if seconds is not None:
            self.write(Reg.SECONDS, int_to_bcd(seconds))

        if minutes is not None:
            self.write(Reg.MINUTES, int_to_bcd(minutes))

        if hours is not None:
            self.write(Reg.HOURS, int_to_bcd(hours))  # no 12 hour mode

        if date is not None:
            self.write(Reg.DAYS, int_to_bcd(date))

        if month is not None:
            self.write(Reg.MONTH, int_to_bcd(month))

        if year is not None:
            self.write(Reg.YEAR, int_to_bcd(year))

        if iso_week_day is not None:
            self.write(Reg.WEEKDAY, int_to_bcd(iso_week_day))

    def set_clk_out_frequency(self, frequency=CLOCK_CLK_OUT_FREQ_1_HZ):
            self.write(Reg.CLK_OUT, frequency)

    def enable_alarm_interrupt(self):
        alarm_state = self.read(Reg.CONTROL_1)
        self.write(Reg.CONTROL_1, alarm_state | 0x02)

    def disable_alarm_interrupt(self):
        alarm_state = self.read(Reg.CONTROL_1)
        self.write(Reg.CONTROL_1, alarm_state & 0xfd)

    def is_alarm_interrupt_enabled(self):
        return bool(self.read(Reg.CONTROL_1) & 0x02)

    def is_alarm_on(self):
        return bool(self.read(Reg.CONTROL_2) & 0x08)

    def turn_alarm_off(self):
        alarm_state = self.read(Reg.CONTROL_2)
        self.write(Reg.CONTROL_2, alarm_state & 0xf7)

    def clear_alarm(self):
        """clear alarm registers and flags"""
        self.write(Reg.CONTROL_2, 0x00)
        
        for reg in (Reg.ALARM_MINUTES, Reg.ALARM_HOURS, Reg.ALARM_DAY, Reg.ALARM_WEEKDAY):
            self.write(reg, ALARM_IGNORE)


if __name__ == '__main__':
    import time
    pcf = PCF8523()
    print('PCF8523 initial time: %s' % pcf.read_datetime())
    pcf.write_now()
    print('PCF8523 synced time: %s' % pcf.read_datetime())
    while True:
        print("rpi time:\t %s" % datetime.utcnow())
        print("pcf time:\t %s\n" % pcf.read_datetime())
        time.sleep(3)
