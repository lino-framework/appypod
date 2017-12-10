'''Management of the conceptual model behind a Appy application'''

# ------------------------------------------------------------------------------
class Config:
    '''Model configuration'''
    def __init__(self, appPath):
        # The absolute path to the app as a pathlib.Path instance
        self.appPath = appPath
        # The application name
        self.appName = appPath.name

    def get(self):
        '''Creates and returns a Model instance (see below)'''
        from appy.model.loader import Loader
        return Loader(self).run()

# ------------------------------------------------------------------------------
class Model:
    '''Represents an application's conceptual model = the base Appy model,
       completed and extended by the application model.'''
    class Error(Exception): pass

    def __init__(self, classes):
        '''The unique Model instance is created by the
           appy.model.loader.Loader.'''
        # All Appy classes and workflows, keyed by their name
        self.classes = classes # ~{s_className: appy.model.class.Class}~

    def getClasses(self, type=None):
        '''Returns a list of classes (sorted by alphabetical order or their
           name) from self.classes. If p_type is:
           - None:       all classes are returned;
           - "class":    only Appy classes are iterated;
           - "workflow": only Appy workflows are iterated.
        '''
        r = []
        for klass in self.classes.values():
            if (type == None) or (type == klass.type):
                r.append(klass)
        r.sort(key=lambda k: k.name.lower())
        return r
# ------------------------------------------------------------------------------
