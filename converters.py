""" OFX element type converters """
# -*- coding: utf-8 -*-

# stdlib imports
import decimal
import datetime
import time
import re


class OFXElement(object):
    """
    Base class of validator/type converter for OFX 'element', i.e. SGML leaf
    node that contains text data.

    OFXElement instances store validation parameters relevant to a particular
    Aggregate subclass (e.g. maximum string length, decimal precision,
    required vs. optional, etc.) - they don't directly store the data
    itself (which lives in the __dict__ of an Aggregate instance).
    """
    def __init__(self, *args, **kwargs):
        required = kwargs.pop('required', False)
        self.required = required
        self._init(*args, **kwargs)

    def _init(self, *args, **kwargs):
        """ Override in subclass """
        if args or kwargs:
            raise ValueError("Unknown args for '%s'- args: %r; kwargs: %r"
                            % (self.__class__.__name__, args, kwargs))

    def convert(self, value, strict=True):
        """ Override in subclass """
        raise NotImplementedError

class OFXbool(OFXElement):
    mapping = {'Y': True, 'N': False}

    def convert(self, value, strict=True):
        if value is None and not self.required:
            return None
        return self.mapping[value]

    def unconvert(self, value):
        if value is None and not self.required:
            return None
        return {v:k for k,v in self.mapping.items()}[value]


class OFXstr(OFXElement):
    def _init(self, *args, **kwargs):
        length = None
        if args:
            length = args[0]
            args = args[1:]
        self.length = length
        super(OFXstr, self)._init(*args, **kwargs)

    def convert(self, value, strict=True):
        if value is None and not self.required:
            return None
        if strict and self.length is not None and len(value) > self.length:
            raise ValueError("'%s' is too long; max length=%s" % (value, self.length))
        return str(value)


class OneOf(OFXElement):
    def _init(self, *args, **kwargs):
        self.valid = set(args)
        super(OneOf, self)._init(**kwargs)

    def convert(self, value, strict=True):
        if value is None and not self.required:
            return None
        if (value in self.valid):
            return value
        raise ValueError("'%s' is not OneOf %r" % (value, self.valid))


class OFXint(OFXElement):
    def _init(self, *args, **kwargs):
        length = None
        if args:
            length = args[0]
            args = args[1:]
        self.length = length
        super(OFXint, self)._init(*args, **kwargs)

    def convert(self, value, strict=True):
        if value is None and not self.required:
            return None
        value = int(value)
        if self.length is not None and value >= 10**self.length:
            raise ValueError('%s has too many digits; max digits=%s' % (value, self.length))
        return int(value)


class OFXdecimal(OFXElement):
    def _init(self, *args, **kwargs):
        precision = 2
        if args:
            precision = args[0]
            args = args[1:]
        self.precision = precision
        super(OFXdecimal, self)._init(*args, **kwargs)

    def convert(self, value, strict=True):
        if value is None and not self.required:
            return None
        value = decimal.Decimal(value)
        precision = decimal.Decimal('0.' + '0'*(self.precision-1) + '1')
        value.quantize(precision)
        return value


class OFXdatetime(OFXElement):
    # Valid datetime formats given by OFX spec in section 3.2.8.2
    tz_re = re.compile(r'\[([-+]?\d{0,2}\.?\d*):?(\w*)\]')
    # strftime formats keyed by the length of the corresponding string
    formats = {18: '%Y%m%d%H%M%S.%f', 14: '%Y%m%d%H%M%S', 8: '%Y%m%d'}

    @classmethod
    def convert(cls, value, strict=True):
        # If it's a datetime or None, don't touch it.
        if isinstance(value, datetime.datetime) or value is None:
            return value

        # Pristine copy of input for error reporting purposes
        orig_value = value

        # Strip out timezone, on which strptime() chokes
        chunks = cls.tz_re.split(value)
        value = chunks.pop(0)
        if chunks:
            gmt_offset, tz_name = chunks[:2]
            # Some FIs *cough* IBKR *cough* write crap for the TZ offset
            if gmt_offset == '-':
                gmt_offset = '0'
            gmt_offset = int(decimal.Decimal(gmt_offset)*3600) # hours -> seconds
        else:
            gmt_offset = 0
        format = cls.formats[len(value)]
        try:
            value = datetime.datetime.strptime(value, format)
        except ValueError:
            raise ValueError("Datetime '%s' does not match OFX formats %s" %
                            (orig_value, cls.formats.values()))

        # Adjust timezone to GMT
        value -= datetime.timedelta(seconds=gmt_offset)
        return value

    @classmethod
    def unconvert(cls, value):
        """ Input datetime.datetime in local time; output str in GMT. """
        # Pristine copy of input for error reporting purposes
        orig_value = value

        try:
            # Transform to GMT
            value = time.gmtime(time.mktime(value.timetuple()))
            # timetuples don't have usec precision
            #value = time.strftime('%s[0:GMT]' % cls.formats[14], value)
            value = time.strftime(cls.formats[14], value)
        except:
            raise # FIXME
        return value

