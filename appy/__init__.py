'''Appy is the simpliest way to build complex webapps'''

# ~license~
# ------------------------------------------------------------------------------
class Config:
    '''This class is the root of all configuration options for your app. These
       options are those managed by the app developer: they are not meant to be
       edited during the app lifetime by end users. For such "end-user"
       configuration options, you must extend the appy.model.Tool class,
       designed for that purpose. In short, this Config file represents the
       "RAM" configuration, while the unique appy.model.Tool instance within
       every app contains its "DB" configuration.

       In your app/__init__.py, create a class named "Config" that inherits from
       this one and will override some of the atttibutes defined here, ie:

       import appy
       class Config(appy.Config):
           langages = ('en', 'fr')
    '''

    # Place here a appy.http.server.Config instance defining the configuration
    # of the Appy HTTP server.
    server = None
    # Place here a appy.db.Config instance defining database options
    db = None
    # Place here a appy.db.log.Config instance defining logging options
    log = None
    # Place here a appy.ui.Config instance defining user-interface options
    ui = None
# ------------------------------------------------------------------------------

