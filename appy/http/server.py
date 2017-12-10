'''Appy HTTP server'''

# ~license~
# ------------------------------------------------------------------------------
import os, sys, traceback, socket, socketserver, logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from appy.utils import Version
from appy.model import Model
from appy.model.utils import Object

# ------------------------------------------------------------------------------
class Config:
    '''HTTP server configuration for a Appy site'''
    def __init__(self, address='127.0.0.1', port=8000):
        # The server address
        self.address = address
        # The server port
        self.port = port

    def inUse(self):
        '''Returns True if (self.address, self.port) is already in use'''
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind((self.address, self.port))
        except socket.error as e:
            if e.errno == 98:
                return True
        s.close()

# ------------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    '''Handles incoming HTTP requests'''
    server_version = 'Appy/%s' % Version.short

    # This dict allows to find the data that needs to be logged
    logAttributes = {'ip': 'self.client_address[0]',
      'port': 'str(self.client_address[1])', 'command': 'self.command',
      'path': 'self.path', 'protocol': 'self.request_version',
      'message': 'message', 'user': 'server.user',
      'agent': 'self.headers.get("User-Agent")'}

    def do_GET(self):
        # Opens a connection to the database
        dbConnection = self.server.db.open()
        # Send response code
        code = 200
        self.send_response(code)
        # Log this hit and the response code on the site log
        self.log('site', 'info', str(code))
        # Send headers
        self.send_header('Content-type','text/html')
        self.end_headers()
        # Send message
        message = "<p>Appy %s</p><p>Root obj is %s</p>" % \
                  (self.path, str(dbConnection.root))
        # Write content as utf-8 data
        self.wfile.write(bytes(message, 'utf8'))
        # Close the database connection
        dbConnection.close()

    def do_POST(self): self.do_GET()

    # Overridden methods -------------------------------------------------------
    def send_response(self, code, message=None):
        '''Add the response header to the headers buffer and 2 basic headers'''
        self.send_response_only(code, message)
        self.send_header('Server', self.version_string())
        self.send_header('Date', self.date_time_string())

    # Log methods --------------------------------------------------------------
    def log(self, type, level, message=None):
        '''Logs, in the logger determined by p_type, a p_message at some
           p_level, that can be "debug", "info", "warning", "error" or
           "critical". p_message can be empty: in this case, the log entry will
           only contain the predefined attributes as defined by the
           appy.db.log.Config.'''
        server = self.server
        logger = getattr(server.loggers, type)
        cfg = getattr(server.config.log, type)
        # Get the parts of the message to dump
        r = []
        for part in cfg.messageParts:
            value = eval(Handler.logAttributes[part])
            if value != None:
                r.append(value)
        # Call the appropriate method on the logger object corresponding to the
        # log p_level.
        getattr(logger, level)(cfg.sep.join(r))

    # Overridden log methods
    def log_message(self, format, *args):
        '''Standard method for logging messages: log it to the app log'''
        self.log('app', 'info', format % args)

    def log_error(self, format, *args):
        '''Standard method for logging errors: log it to the app log'''
        self.log('app', 'error', format % args)

# ------------------------------------------------------------------------------
class Server(socketserver.ThreadingMixIn, HTTPServer):
    '''Appy HTTP server'''
    READY = '%s:%s ready (process ID %d).'
    STOP = '%s:%s stopped.'
    # Terminate threads when the main process is terminated
    daemon_threads = True

    def __init__(self, config, mode):
        # "config" is the main Appy config
        self.config = config
        # "mode" can be "fg" (foreground, debug mode) or "bg" (background)
        self.mode = mode
        # Initialise the loggers
        cfg = config.log
        self.loggers = Object(site=cfg.getLogger('site'),
                              app=cfg.getLogger('app', mode == 'fg'))
        try:
            # Load the application model
            self.model = config.model.get()
            # Initialise the HTTP server
            cfg = config.server
            HTTPServer.__init__(self, (cfg.address, cfg.port), Handler)
            # Initialise the database
            self.db = config.db.getDatabase(self.loggers.app)
        except Model.Error as err:
            self.loggers.app.error(err)
            logging.shutdown()
            sys.exit(1)
        except Exception as e:
            self.logTraceback()
            logging.shutdown()
            sys.exit(1)
        # The current user login
        self.user = 'system'
        # The server is ready
        self.loggers.app.info(self.READY % (cfg.address, cfg.port, os.getpid()))

    def handle_error(self, request, client_address):
        '''Handles an exception raised while a handler processes a request'''
        self.logTraceback()

    def logTraceback(self):
        '''Logs a traceback'''
        self.loggers.app.error(traceback.format_exc().strip())

    def shutdown(self):
        '''Shutdowns the server'''
        # Logs the shutdown
        cfg = self.config.server
        self.loggers.app.info(self.STOP % (cfg.address, cfg.port))
        # Shutdown the loggers
        logging.shutdown()
        # Shutdown the database
        self.db.close()
        # Call the base method
        HTTPServer.shutdown(self)
# ------------------------------------------------------------------------------
