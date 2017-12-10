'''Classes representing meta-information about the model'''

# ------------------------------------------------------------------------------
import collections
import persistent
from appy.model.base import Base
from appy.model.fields import Field
from appy.model.fields.workflow import State, Transition

# ------------------------------------------------------------------------------
class MetaClass(type):
    '''The meta-class of all Appy classes'''
    # Appy-specific attributes added to any Appy class
    appyAttributes = ('fields', 'states', 'transitions')

    def __new__(meta, name, bases, classdict):
        # Create the class definition
        klass = type.__new__(meta, name, bases, classdict)
        # Add Appy-specific attributes to the class
        for attributeName in MetaClass.appyAttributes:
            setattr(klass, attributeName, collections.OrderedDict())
        # Put Appy fields in Appy-specific attributes
        for k, v in bases[0].__dict__.items():
            if k.startswith('__'): continue
            if isinstance(v, Field):
                klass.fields[k] = v
            elif isinstance(v, State):
                klass.states[k] = v
            elif isinstance(v, Transition):
                klass.transitions[k] = v
        return klass

    def __repr__(self):
        r = '<Class %s.%s' % (self.__module__, self.__name__)
        if not hasattr(self, 'fields'): return r + '>'
        for name in self.appyAttributes:
            attr = getattr(self, name)
            for k in attr.keys():
                r += '\n  %s : %s' % (k, attr[k])
        return '%s\n>' % r

# ------------------------------------------------------------------------------
class Class:
    '''Represents an Appy class'''
    def __init__(self, klass, type):
        # p_klass is the Python class found in the Appy app. Its full name is
        #              <Python file name>.py.<class name>
        self.python = klass
        # Its name
        name = klass.__name__
        self.name = name
        # Its type ("class" or "workflow")
        self.type = type
        # The concrete class from which instances will be created. Indeed, In
        # order to bring all Appy functionalities to the class defined by the
        # developer (in self.python), we need to create a new class, with a
        # specific meta-class and inheriting from a few base classes
        # (including self.python of course).
        exec('class %s(self.python, Base, persistent.Persistent, ' \
             'metaclass=MetaClass): pass' % name)
        # This concrete class will have a full name being
        #            appy.model.meta.<class name>
        exec('self.concrete = %s' % name)
        print(self.concrete)

    def __repr__(self):
        return '<%s::%s (%s)>' % (self.python.__module__, self.name, self.type)
# ------------------------------------------------------------------------------
