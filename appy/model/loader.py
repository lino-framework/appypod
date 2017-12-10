'''Loads and returns a Model instance'''

# ------------------------------------------------------------------------------
from appy.model import Model
from appy.model.meta import Class
from appy.model.fields import Field
from appy.model.utils import importModule
from appy.model.fields.workflow import State

# ------------------------------------------------------------------------------
class Loader:
    '''Reads the application model, completes it and integrates it within the
       global Appy model, and returns a appy.model.Model instance.'''
    NO_SEARCH = "Note that Appy classes and workflows are not searched " \
      "within your app's __init__.py file, nor within sub-modules."
    NO_PYTHON_FILE = 'No Python file was found in your app @%%s. %s' % NO_SEARCH
    NO_APPY_CLASS = 'No Appy class was found in your app @%%s. %s' % NO_SEARCH
    DUPLICATE_NAME = '2 or more Appy classes and/or workflows named "%s" ' \
      'have been found in your model. This is not allowed, even if they are ' \
      'in separate Python modules.'

    def __init__(self, config):
        # The model config (a appy.model.Config instance)
        self.config = config

    def determineAppyType(self, klass):
        '''If p_klass is:
           * a Appy class, this method returns "class";
           * a Appy workflow, this method returns "workflow";
           * none of it, this method returns None.
        '''
        # If p_klass declares at least one static attribute being an instance of
        # appy.fields.Field, it will be considered a Appy class. If it declares
        # at least one static attribute being an instance of
        # appy.fields.workflow.State, it will be considered a Appy workflow.
        for attr in klass.__dict__.values():
            if isinstance(attr, Field): return 'class'
            elif isinstance(attr, State): return 'workflow'

    def run(self):
        '''Loads the model'''
        config = self.config
        # Search Appy classes and workflow, in Python files at the root of the
        # App module, __init__.py excepted.
        pythonFiles = []
        for path in config.appPath.glob('*.py'):
            if path.name != '__init__.py':
                pythonFiles.append(path)
        # Raise an error if no Python file has been found
        if not pythonFiles:
            raise Model.Error(self.NO_PYTHON_FILE % str(config.appPath))
        # Import every found Python file, searching for Appy classes/workflows
        classType = type(Model)
        classes = {} # ~{s_className: Class}~
        for path in pythonFiles:
            module = importModule(path.name, str(path))
            # Find classes within this module
            for element in module.__dict__.values():
                # Ignore non-classes or classes imported from other modules
                if (type(element) != classType) or \
                   (element.__module__ != module.__name__): continue
                # Ignore non-Appy classes
                appyType = self.determineAppyType(element)
                if not appyType: continue
                # Add this Appy class to "classes"
                name = element.__name__
                if name in classes:
                    raise Model.Error(self.DUPLICATE_NAME % name)
                classes[name] = Class(element, appyType)
        # Ensure we have found at least one class
        if not classes:
            raise Model.Error(self.NO_APPY_CLASS % str(config.appPath))
        return Model(classes)
# ------------------------------------------------------------------------------
