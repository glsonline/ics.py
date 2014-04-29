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

# TODO: GLS: + add properties: due, duration
# TODO: GLS: + remove properties:  end, begin
# TODO: GLS: + add property: percent
# TODO: GLS: add properties: completed, status, ...
# TODO: GLS: apply DRY principle
# TODO: GLS: verify properties: due vs. duration: Todo.due()
# TODO: GLS: global substitutions:
# +    _end_time => _due
# +    end => due
# +    begin =>
# +    _begin
# +    _begin_precision
#    _due -> due


class Todo(Component):

    """A calendar todo.

    Can be full-day or between two instants.
    Can be defined by a beginning instant and\
    a duration *or* due instant.
    """

    _TYPE = "VTODO"
    _EXTRACTORS = []
    _OUTPUTS = []

    def __init__(self,
                 name=None,
                 #begin=None,
                 due=None,
                 duration=None,
                 uid=None,
                 description=None,
                 priority=None,
                 categories=None,
                 created=None,
                 percent=None,
                 completed=None,
                 location=None):
        """Instanciates a new :class:`ics.todo.Todo`.

        Args:
            name (string)
            #begin (Arrow-compatible)
            due (Arrow-compatible)
            duration (datetime.timedelta)
            uid (string): must be unique
            description (string)
            priority (int) # GLS: (0-9)
            categories (list) # GLS: ??? should it be a list or just treat as
                                # list during manipulations
            created (Arrow-compatible)
            percent (int) # GLS: (0-100)
            completed (Arrow-compatible)
            location (string)

        Raises:
            ValueError: if `due` and `duration` are specified at the same time
        """

        self._duration = None
        self._due = None
        #self._begin = None
        #self._begin_precision = None
        self.uid = uid_gen() if not uid else uid
        self.description = description
        self.priority = priority
        self.categories = categories
        self.created = get_arrow(created)
        self.percent = percent
        self._completed = get_arrow(completed)
        #self.completed = completed  # TODO: GLS: double-check this
        self.location = location
        self._unused = Container(name='VTODO')

        self.name = name
        #self.begin = begin
        #TODO: DRY [1]
        if duration and due:
            raise ValueError(
                'Todo() may not specify an due and a duration \
                at the same time')
        elif due:  # End was specified
            self._due = due
        elif duration:  # Duration was specified
            self.duration = duration

    def has_due(self):
        """
        Return:
            bool: self has an due
        """
        return bool(self._due) # GLS: ???: use only _due now?
        #return bool(self._due or self._duration) # GLS: ???: why not only _due?

    #@property
    #def begin(self):
        #"""Get or set the beginning of the todo.

        #|  Will return an :class:`Arrow` object.
        #|  May be set to anything that :func:`Arrow.get` understands.
        #|  If an due is defined (not a duration), .begin must not
            #be set to a superior value.
        #"""
        #return self._begin

    #@begin.setter
    #def begin(self, value):
        #value = get_arrow(value)
        #if value and self._due and value > self._due:
            #raise ValueError('Begin must be before due')
        #self._begin = value
        #self._begin_precision = 'second'

    @property
    def due(self):
        """Get or set the due of the todo.

        |  Will return an :class:`Arrow` object.
        |  May be set to anything that :func:`Arrow.get` understands.
        |  If set to a non null value, removes any already
            existing duration.
        |  Setting to None will have unexpected behavior if
            begin is not None.
        |  Must not be set to an inferior value than self.begin.
        """

        #TODO: GLS: DRY [1]
        #if self._duration:  # if due is duration defined # TODO: GLS: no longer applies
            ## return the duration
            #return self._duration
        #if self._duration:  # if due is duration defined
            ## return the beginning + duration
            #return self.begin + self._duration
        if self._due:  # if due is time defined
            return self._due
        #elif self._begin:  # if due is not defined
            ## return beginning + precision
            #return self.begin.replace(**{self._begin_precision + 's': +1})
        else:
            return None

    @due.setter
    def due(self, value):
        value = get_arrow(value)
        #if value and value < self._begin:
            #raise ValueError('End must be after begin')

        self._due = value
        #if value:     # TODO: GLS: no longer applies
            #self._duration = None

    @property
    def percent(self):
        """Get or set the percent of the todo.

        |  Will return an :class:`Arrow` object.
        |  May be set to anything that :func:`Arrow.get` understands.
        |  If set to a non null value, removes any already
            existing duration.
        |  Setting to None will have unexpected behavior if
            begin is not None.
        |  Must not be set to an inferior value than self.begin.
        """

        #TODO: GLS: DRY [1]
        if self._percent:
            return self._percent
        else:
            return None

    @percent.setter
    def percent(self, value):
        value = arrow.now() if not value else get_arrow(value)
        self._percent = value

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
    def completed(self):
        """Get or set the completed of the todo.

        |  Will return an :class:`Arrow` object.
        |  May be set to anything that :func:`Arrow.get` understands.
        |  If set to a non null value, removes any already
            existing duration.
        |  Setting to None will have unexpected behavior if
            begin is not None.
        |  Must not be set to an inferior value than self.begin.
        """

        #TODO: GLS: DRY [1]
        if self._completed:  # if completed is time defined
            return self._completed
        else:
            return None

    @completed.setter
    def completed(self, value):
        value = arrow.now() if not value else get_arrow(value)
        self._completed = value

    # TODO: GLS: feel free to rename
    def bump(self, delta, force_empty_dues=False): # GLS: touch_recurs=False
        """Adjusts the due date by delta
            TODO: GLS: ???: should it bump those that have no due date?
        Args:
            delta (dict) (Arrow-convertible)
            force_empty_dues (bool): also bump todos currently without a due date
            touch_recurs (bool): also bump recurring todos
        Raises:
            ValueError: if delta not set
            ValueError: if ...
        """
        #TODO: GLS: DRY [1]
        if not force_empty_dues and not self._due: # GLS: do nothing
            print('{}: check 1'.format(__name__))
            return
        if not self._due:
            self._due = arrow.now(tz='local')    # GLS: ???: which tz to use?
            #print "{}: check 2".format(__name__)
            #tz_dict = self._classmethod_kwargs['tz']
            #print "tz_dict: {}".format(tz_dict)
            ##self._due = arrow.now(tz=tz_dict)    # GLS: ???: which tz to use?
            ##    we don't necessarily have a reference to a calendar
            #print "{}: check 3".format(__name__)
            ##self._due = arrow.now(tz=calendar._timezones)    # GLS:

        #print '{}: GLS: BEFORE: self._due: {}'.format(__name__, self._due)
        self._due = self._due.replace(**delta)
        #print "{}: check 4".format(__name__)
        #print '{}: GLS: AFTER: self._due: {}'.format(__name__, self._due)
        return

    def __urepr__(self):
        """Should not be used directly. Use self.__repr__ instead.

        Returns:
            unicode: a unicode representation (__repr__) of the todo.
        """
        #TODO: GLS: DRY [1]
        name = "'{}' ".format(self.name) if self.name else ''
        if self._due:
            return "<Todo {} due:{}>".format(name, self._due)
        return "<Todo '{}'>".format(self.name) if self.name else "<Todo>"
        #if self.all_day:
            #return "<all-day Todo {}{}>".format(name, self.begin.strftime("%F"))
        #elif self.begin is None:
            #return "<Todo '{}'>".format(self.name) if self.name else "<Todo>"
        #else:
            #return "<Todo {}begin:{} due:{}>".format(name, self.begin, self._due)

    # TODO: GLS: verify these comparison functions
    def __lt__(self, other):
        if not isinstance(other, Todo):
            raise NotImplementedError(
                'Cannot compare Todo and {}'.format(type(other)))
        #TODO: GLS: DRY [1]
        if self._due is None and other.due is None:
            return self.name < other.name
        return self._due < other.due

    def __le__(self, other):
        if not isinstance(other, Todo):
            raise NotImplementedError(
                'Cannot compare Todo and {}'.format(type(other)))
        #TODO: GLS: DRY [1]
        if self._due is None and other.due is None:
            return self.name <= other.name
        return self._due <= other.due

    def __gt__(self, other):
        if not isinstance(other, Todo):
            raise NotImplementedError(
                'Cannot compare Todo and {}'.format(type(other)))
        #TODO: GLS: DRY [1]
        if self._due is None and other.due is None:
            return self.name > other.name
        return self._due > other.due

    def __ge__(self, other):
        if not isinstance(other, Todo):
            raise NotImplementedError(
                'Cannot compare Todo and {}'.format(type(other)))
        #TODO: GLS: DRY [1]
        if self._due is None and other.due is None:
            return self.name >= other.name
        return self._due >= other.due

    # TODO: GLS: commented; ???: Does this make sense anymore? When/How used?
    #def __or__(self, other):
        #begin, due = None, None
        #if self.begin and other.begin:
            #begin = max(self.begin, other.begin)
        #if self._due and other.due:
            #due = min(self._due, other.due)
        #return (begin, due) if begin and due and begin < due else (None, None)

    def __eq__(self, other):
        """Two todos are considered equal if they have the same uid."""
        if not isinstance(other, Todo):
            raise NotImplementedError(
                'Cannot compare Todo and {}'.format(type(other)))
        #TODO: GLS: DRY [1]
        #print 'self: {}\nother: {}'.format(self, other)
        return self.uid == other.uid

    def is_complete(self):
        """A Todo is complete if its completion percentage is 100%
        Return:
            bool: self is past due
        """
        return self.percent == 100

    def is_overdue(self):
        """A Todo is overdue if due date is less than the current time
        Return:
            bool: self is past due
        """
        return self._due < arrow.now()

    def fancy_due(self,
            dist_past='MMM D\nYYYY',
            near_past='MMM D\nYYYY',
            near_future='ddd',
            dist_future='ddd MMM D\n@ hh:mm a',
            ):
        """Show fancy display of due date based on its value
        Return:

        string: "fancy" display of due date based on its value
        """
        now = arrow.now()
        # TODO: GLS: substitute _HUMAN_ str in all default params
        human = '_HUMAN_'
        # TODO: GLS: map(if s.find(human) != -1) { s.replace(human, '{}'; s.format()})
        # TODO: GLS: ???: also add color?
        if not self.has_due():   # nothing to do
            return u''
        #elif self._due < now.replace(days=-7):
            #return str(self._due.humanize()) # GLS: while testing
            #return str(self._due.format(near_past))
        elif self.is_overdue():
            if self._due > now.replace(days=-7):
                print('here 1')
                return str(self._due.humanize()) # GLS: while testing
            else:
                return str(self._due.format(dist_past))
        # GLS: due in the next week
        elif self._due < now.replace(days=+7):  # GLS: weeks=+1
        #elif self._due < self._due.replace(days=+7):  # GLS: weeks=+1
            print('here 2')
            return str(self._due.format(near_future))
        # due in future, future > 7 days
        print('here 3')
        #return str(self._due.format('ddd\n') + self._due.humanize()) # GLS: works
        #return str(self._due.format('ddd\n') + self._due.humanize(locale='ru'))
        return str(self._due.format(dist_future))

    def clone(self):
        """
        Returns:
            Todo: an exact copy of self"""
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

@Todo._extracts('DTSTAMP')
def created(todo, line):
    if line:
        # get the dict of vtimezones passed to the classmethod
        tz_dict = todo._classmethod_kwargs['tz']
        todo.created = iso_to_arrow(line, tz_dict)


@Todo._extracts('PERCENT_COMPLETE')
def percent(todo, line):
    todo.percent = line.value if line else None


@Todo._extracts('COMPLETED')
def completed(todo, line):
    if line:
        # get the dict of vtimezones passed to the classmethod
        tz_dict = todo._classmethod_kwargs['tz']
        todo._completed = iso_to_arrow(line, tz_dict)

#@Todo._extracts('DTSTART')
#def start(todo, line):
    #if line:
        ## get the dict of vtimezones passed to the classmethod
        #tz_dict = todo._classmethod_kwargs['tz']
        ##print('line: {0}'.format(line))   # GLS: debugging
        #todo.begin = iso_to_arrow(line, tz_dict)
        #todo._begin_precision = iso_precision(line.value)


@Todo._extracts('DURATION')
def duration(todo, line):
    if line:
        #TODO: DRY [1]
        #if todo._due: # pragma: no cover
            #raise ValueError("An todo can't have both DTEND and DURATION")
        todo._duration = parse_duration(line.value)


@Todo._extracts('DUE')
def due(todo, line):
    if line:
        #TODO: DRY [1]
        #if todo._duration:
            #raise ValueError("An todo can't have both DTEND and DURATION")
        # get the dict of vtimezones passed to the classmethod
        tz_dict = todo._classmethod_kwargs['tz']
        todo._due = iso_to_arrow(line, tz_dict)


@Todo._extracts('SUMMARY')
def summary(todo, line):
    todo.name = line.value if line else None


@Todo._extracts('DESCRIPTION')
def description(todo, line):
    todo.description = line.value if line else None


@Todo._extracts('PRIORITY')
def priority(todo, line):
    todo.priority = int(line.value) if line else None


@Todo._extracts('CATEGORIES')
def categories(todo, line): # GLS: ???: want list or just a colon-separated str?
    todo.categories = line.value.split(',') if line else None
    #todo.categories = line.value if line else None


@Todo._extracts('LOCATION')
def location(todo, line):
    todo.location = line.value if line else None


# TODO : make uid required ?
# TODO : add option somewhere to ignore some errors
@Todo._extracts('UID')
def uid(todo, line):
    if line:
        todo.uid = line.value


######################
###### Outputs #######
@Todo._outputs
def o_created(todo, container):
    if todo.created:
        instant = todo.created
    else:
        instant = arrow.now()
    container.append(ContentLine('DTSTAMP', value=arrow_to_iso(instant)))


@Todo._outputs
def o_percent(todo, container):
    if todo.percent:
        container.append(ContentLine('PERCENT_COMPLETE', value=todo.percent))


@Todo._outputs
def o_completed(todo, container):
    if todo._completed:
        instant = todo._completed
    else: # TODO: GLS: I don't think this is correct
        instant = arrow.now()

    container.append(ContentLine('COMPLETED', value=arrow_to_iso(instant)))


#@Todo._outputs
#def o_start(todo, container):
    #if todo.begin:
        #container.append(
            #ContentLine('DTSTART', value=arrow_to_iso(todo.begin)))
    ## TODO : take care of precision


@Todo._outputs
def o_duration(todo, container):
    # TODO : DURATION
    #if todo._duration and todo.begin:
    if todo._duration:
        representation = timedelta_to_duration(todo._duration)
        container.append(ContentLine('DURATION', value=representation))


@Todo._outputs
def o_due(todo, container):
    #if todo.begin and todo._due:
    if todo._due:
        container.append(ContentLine('DUE', value=arrow_to_iso(todo.due)))


@Todo._outputs
def o_summary(todo, container):
    if todo.name:
        container.append(ContentLine('SUMMARY', value=todo.name))


@Todo._outputs
def o_description(todo, container):
    if todo.description:
        container.append(ContentLine('DESCRIPTION', value=todo.description))


@Todo._outputs
def o_priority(todo, container):
    if todo.priority:
        container.append(ContentLine('PRIORITY', value=todo.priority))


@Todo._outputs
def o_categories(todo, container):
    if todo.categories:
        container.append(ContentLine('CATEGORIES', value=todo.categories))


@Todo._outputs
def o_location(todo, container):
    if todo.location:
        container.append(ContentLine('LOCATION', value=todo.location))


@Todo._outputs
def o_uid(todo, container):
    if todo.uid:
        uid = todo.uid
    else:
        uid = uid_gen()

    container.append(ContentLine('UID', value=uid))
