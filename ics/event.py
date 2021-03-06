#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals, absolute_import

from six import PY2, PY3, StringIO, string_types, text_type, integer_types
from six.moves import filter, map, range

import arrow
import copy
from datetime import timedelta

from .component import Component
from .utils import (
    parse_duration,
    timedelta_to_duration,
    iso_to_arrow,
    iso_precision,
    get_arrow,
    arrow_to_iso,
    uid_gen,
)
from .parse import ContentLine, Container

# TODO: GLS: # https://tools.ietf.org/html/rfc5545#page-56
# TODO: GLS: fail gracefully when parsing errors for incoming file
import sys


class Event(Component):

    """A calendar event.

    Can be full-day or between two instants.
    Can be defined by a beginning instant and\
    a duration *or* end instant.
    """

    _TYPE = "VEVENT"
    _EXTRACTORS = []
    _OUTPUTS = []

    def __init__(self,
                 name=None,
                 begin=None,
                 end=None,
                 duration=None,
                 uid=None,
                 description=None,
                 created=None,
                 location=None):
        """Instanciates a new :class:`ics.event.Event`.

        Args:
            name (string)
            begin (Arrow-compatible)
            end (Arrow-compatible)
            duration (datetime.timedelta)
            uid (string): must be unique
            description (string)
            created (Arrow-compatible)
            location (string)

        Raises:
            ValueError: if `end` and `duration` are specified at the same time
        """

        self._duration = None
        self._end_time = None
        self._begin = None
        self._begin_precision = None
        self.uid = uid_gen() if not uid else uid
        self.description = description
        self.created = get_arrow(created)
        self.location = location
        self._unused = Container(name='VEVENT')

        self.name = name
        self.begin = begin
        #TODO: DRY [1]
        if duration and end:
            raise ValueError(
                'Event() may not specify an end and a duration \
                at the same time')
        elif end:  # End was specified
            self.end = end
        elif duration:  # Duration was specified
            self.duration = duration

    def has_end(self):
        """
        Return:
            bool: self has an end
        """
        return bool(self._end_time or self._duration)

    @property
    def begin(self):
        """Get or set the beginning of the event.

        |  Will return an :class:`Arrow` object.
        |  May be set to anything that :func:`Arrow.get` understands.
        |  If an end is defined (not a duration), .begin must not
            be set to a superior value.
        """
        return self._begin

    @begin.setter
    def begin(self, value):
        value = get_arrow(value)
        if value and self._end_time and value > self._end_time:
            raise ValueError('Begin must be before end')
        self._begin = value
        self._begin_precision = 'second'

    @property
    def end(self):
        """Get or set the end of the event.

        |  Will return an :class:`Arrow` object.
        |  May be set to anything that :func:`Arrow.get` understands.
        |  If set to a non null value, removes any already
            existing duration.
        |  Setting to None will have unexpected behavior if
            begin is not None.
        |  Must not be set to an inferior value than self.begin.
        """

        if self._duration:  # if end is duration defined
            # return the beginning + duration
            return self.begin + self._duration
        elif self._end_time:  # if end is time defined
            return self._end_time
        elif self._begin:  # if end is not defined
            # return beginning + precision
            return self.begin.replace(**{self._begin_precision + 's': +1})
        else:
            return None

    @end.setter
    def end(self, value):
        value = get_arrow(value)
        if value and value < self._begin:
            raise ValueError('End must be after begin')

        self._end_time = value
        if value:
            self._duration = None

    @property
    def duration(self):
        """Get or set the duration of the event.

        |  Will return a timedelta object.
        |  May be set to anything that timedelta() understands.
        |  May be set with a dict ({"days":2, "hours":6}).
        |  If set to a non null value, removes any already
            existing end time.
        """
        if self._duration:
            return self._duration
        elif self.end:
            return self.end - self.begin
        else:
            return None

    @duration.setter
    def duration(self, value):
        if isinstance(value, dict):
            value = timedelta(**value)
        elif isinstance(value, timedelta):
            value = value
        elif not value is None:
            value = timedelta(value)

        if value:
            self._end_time = None

        self._duration = value

    @property
    def all_day(self):
        """
        Return:
            bool: self is an all-day event
        """
        return self._begin_precision == 'day' and not self.has_end()

    def make_all_day(self):
        """Transforms self to an all-day event.

        The day will be the day of self.begin.
        """
        self._begin_precision = 'day'
        self._begin = self._begin.floor('day')
        self._duration = None
        self._end_time = None

    def __urepr__(self):
        """Should not be used directly. Use self.__repr__ instead.

        Returns:
            unicode: a unicode representation (__repr__) of the event.
        """
        name = "'{}' ".format(self.name) if self.name else ''
        if self.all_day:
            return "<all-day Event {}{}>".format(name, self.begin.strftime("%F"))
        elif self.begin is None:
            return "<Event '{}'>".format(self.name) if self.name else "<Event>"
        else:
            return "<Event {}begin:{} end:{}>".format(name, self.begin, self.end)

    def __lt__(self, other):
        if not isinstance(other, Event):
            raise NotImplementedError(
                'Cannot compare Event and {}'.format(type(other)))
        if self.begin is None and other.begin is None:
            return self.name < other.name
        return self.begin < other.begin

    def __le__(self, other):
        if not isinstance(other, Event):
            raise NotImplementedError(
                'Cannot compare Event and {}'.format(type(other)))
        if self.begin is None and other.begin is None:
            return self.name <= other.name
        return self.begin <= other.begin

    def __gt__(self, other):
        if not isinstance(other, Event):
            raise NotImplementedError(
                'Cannot compare Event and {}'.format(type(other)))
        if self.begin is None and other.begin is None:
            return self.name > other.name
        return self.begin > other.begin

    def __ge__(self, other):
        if not isinstance(other, Event):
            raise NotImplementedError(
                'Cannot compare Event and {}'.format(type(other)))
        if self.begin is None and other.begin is None:
            return self.name >= other.name
        return self.begin >= other.begin

    def __or__(self, other):
        begin, end = None, None
        if self.begin and other.begin:
            begin = max(self.begin, other.begin)
        if self.end and other.end:
            end = min(self.end, other.end)
        return (begin, end) if begin and end and begin < end else (None, None)

    def __eq__(self, other):
        """Two events are considered equal if they have the same uid."""
        return self.uid == other.uid

    def clone(self):
        """
        Returns:
            Event: an exact copy of self"""
        clone = copy.copy(self)
        clone._unused = clone._unused.clone()
        return clone

    def __hash__(self):
        """
        Returns:
            int: hash of self. Based on self.uid."""
        ord3 = lambda x: '%.3d' % ord(x)
        return int(''.join(map(ord3, self.uid)))


######################
####### Inputs #######

@Event._extracts('DTSTAMP')
def created(event, line):
    if line:
        # get the dict of vtimezones passed to the classmethod
        tz_dict = event._classmethod_kwargs['tz']
        event.created = iso_to_arrow(line, tz_dict)


@Event._extracts('DTSTART')
def start(event, line):
    if line:
        # get the dict of vtimezones passed to the classmethod
        tz_dict = event._classmethod_kwargs['tz']
        # TODO: GLS: temp while testing: fail from parsing errors gracefully
        try:
            event.begin = iso_to_arrow(line, tz_dict)
        except arrow.parser.ParserError:
            print('\n\t***** GLS: Parsing error encountered: *****')
            print('event: {}\nline: {}\n'.format(event, line)) # GLS: debugging
            #print('line: {0}'.format(line))   # GLS: debugging
            sys.exit(0)
        #event.begin = iso_to_arrow(line, tz_dict)
        event._begin_precision = iso_precision(line.value)

# TODO: GLS: the current traceback:
#Traceback (most recent call last):
#File "main.py", line 66, in <module>
    #cal = Calendar(urlopen(url).read().decode('iso-8859-1'))
#File "/home/gellis/virtualenvs/glscal-test1/local/lib/python2.7/site-packages/ics-0.3_dev-py2.7.egg/ics/icalendar.py", line 84, in __init__
    #self._populate(container[0])  # Use first calendar
#File "/home/gellis/virtualenvs/glscal-test1/local/lib/python2.7/site-packages/ics-0.3_dev-py2.7.egg/ics/component.py", line 52, in _populate
    #extractor.function(self, lines)  # Send a list or empty list
#File "/home/gellis/virtualenvs/glscal-test1/local/lib/python2.7/site-packages/ics-0.3_dev-py2.7.egg/ics/icalendar.py", line 278, in events
    #calendar.events = list(map(event_factory, lines))
#File "/home/gellis/virtualenvs/glscal-test1/local/lib/python2.7/site-packages/ics-0.3_dev-py2.7.egg/ics/icalendar.py", line 277, in <lambda>
    #event_factory = lambda x: Event._from_container(x, tz=calendar._timezones)
#File "/home/gellis/virtualenvs/glscal-test1/local/lib/python2.7/site-packages/ics-0.3_dev-py2.7.egg/ics/component.py", line 31, in _from_container
    #k._populate(container)
#File "/home/gellis/virtualenvs/glscal-test1/local/lib/python2.7/site-packages/ics-0.3_dev-py2.7.egg/ics/component.py", line 55, in _populate
    #extractor.function(self, lines[0])  # Send the element
#File "/home/gellis/virtualenvs/glscal-test1/local/lib/python2.7/site-packages/ics-0.3_dev-py2.7.egg/ics/event.py", line 289, in start
    #event.begin = iso_to_arrow(line, tz_dict)
#File "/home/gellis/virtualenvs/glscal-test1/local/lib/python2.7/site-packages/ics-0.3_dev-py2.7.egg/ics/utils.py", line 50, in iso_to_arrow
    #return arrow.get(val)
#File "/usr/local/lib/python2.7/dist-packages/arrow-0.4.2-py2.7.egg/arrow/api.py", line 23, in get
    #return _factory.get(*args, **kwargs)
#File "/usr/local/lib/python2.7/dist-packages/arrow-0.4.2-py2.7.egg/arrow/factory.py", line 142, in get
    #dt = parser.DateTimeParser(locale).parse_iso(arg)
#File "/usr/local/lib/python2.7/dist-packages/arrow-0.4.2-py2.7.egg/arrow/parser.py", line 95, in parse_iso
    #return self._parse_multiformat(string, formats)
#File "/usr/local/lib/python2.7/dist-packages/arrow-0.4.2-py2.7.egg/arrow/parser.py", line 209, in _parse_multiformat
    #raise ParserError('Could not match input to any of {0}'.format(formats))
#arrow.parser.ParserError: Could not match input to any of ['YYYY-MM-DDTHH:mm']


@Event._extracts('DURATION')
def duration(event, line):
    if line:
        #TODO: DRY [1]
        if event._end_time: # pragma: no cover
            raise ValueError("An event can't have both DTEND and DURATION")
        event._duration = parse_duration(line.value)


@Event._extracts('DTEND')
def end(event, line):
    if line:
        #TODO: DRY [1]
        if event._duration:
            raise ValueError("An event can't have both DTEND and DURATION")
        # get the dict of vtimezones passed to the classmethod
        tz_dict = event._classmethod_kwargs['tz']
        event._end_time = iso_to_arrow(line, tz_dict)


@Event._extracts('SUMMARY')
def summary(event, line):
    event.name = line.value if line else None


@Event._extracts('DESCRIPTION')
def description(event, line):
    event.description = line.value if line else None


@Event._extracts('LOCATION')
def location(event, line):
    event.location = line.value if line else None


# TODO : make uid required ?
# TODO : add option somewhere to ignore some errors
@Event._extracts('UID')
def uid(event, line):
    if line:
        event.uid = line.value


######################
###### Outputs #######
@Event._outputs
def o_created(event, container):
    if event.created:
        instant = event.created
    else:
        instant = arrow.now()

    container.append(ContentLine('DTSTAMP', value=arrow_to_iso(instant)))


@Event._outputs
def o_start(event, container):
    if event.begin:
        container.append(
            ContentLine('DTSTART', value=arrow_to_iso(event.begin)))

    # TODO : take care of precision


@Event._outputs
def o_duration(event, container):
    # TODO : DURATION
    if event._duration and event.begin:
        representation = timedelta_to_duration(event._duration)
        container.append(ContentLine('DURATION', value=representation))


@Event._outputs
def o_end(event, container):
    if event.begin and event._end_time:
        container.append(ContentLine('DTEND', value=arrow_to_iso(event.end)))


@Event._outputs
def o_summary(event, container):
    if event.name:
        container.append(ContentLine('SUMMARY', value=event.name))


@Event._outputs
def o_description(event, container):
    if event.description:
        container.append(ContentLine('DESCRIPTION', value=event.description))


@Event._outputs
def o_location(event, container):
    if event.location:
        container.append(ContentLine('LOCATION', value=event.location))


@Event._outputs
def o_uid(event, container):
    if event.uid:
        uid = event.uid
    else:
        uid = uid_gen()

    container.append(ContentLine('UID', value=uid))
