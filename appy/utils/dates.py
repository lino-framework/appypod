'''Date-related classes and functions'''

# ~license~
# ------------------------------------------------------------------------------
try:
    from DateTime import DateTime
except ImportError:
    pass # Zope is required

# ------------------------------------------------------------------------------
def toUTC(d):
    '''When manipulating DateTime instances, like p_d, errors can raise when
       performing operations on dates that are not in Universal time, during
       months when changing from/to summer/winter hour. This function returns
       p_d set to UTC.'''
    return DateTime('%d/%d/%d UTC' % (d.year(), d.month(), d.day()))

# ------------------------------------------------------------------------------
class DayIterator:
    '''Class allowing to iterate over a range of days'''

    def __init__(self, startDay, endDay, back=False):
        self.start = toUTC(startDay)
        self.end = toUTC(endDay)
        # If p_back is True, the iterator will allow to browse days from end to
        # start.
        self.back = back
        self.finished = False
        # Store where we are within [start, end] (or [end, start] if back)
        if not back:
            self.current = self.start
        else:
            self.current = self.end

    def __iter__(self): return self
    def __next__(self):
        '''Returns the next day'''
        if self.finished:
            raise StopIteration
        res = self.current
        # Get the next day, forward
        if not self.back:
            if self.current >= self.end:
                self.finished = True
            else:
                self.current += 1
        # Get the next day, backward
        else:
            if self.current <= self.start:
                self.finished = True
            else:
                self.current -= 1
        return res

# ------------------------------------------------------------------------------
def getLastDayOfMonth(date):
    '''Returns a DateTime object representing the last day of date.month()'''
    day = 31
    month = date.month()
    year = date.year()
    found = False
    while not found:
        try:
            res = DateTime('%d/%d/%d 12:00' % (year, month, day))
            found = True
        except DateTime.DateError:
            day -= 1
    return res

def getDayInterval(date):
    '''Returns a tuple (startOfDay, endOfDay) representing the whole day into
       which p_date occurs.'''
    day = date.strftime('%Y/%m/%d')
    return DateTime('%s 00:00' % day), DateTime('%s 23:59' % day)
# ------------------------------------------------------------------------------
