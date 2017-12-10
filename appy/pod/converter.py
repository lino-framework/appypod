# ~license~
# ------------------------------------------------------------------------------
import sys, os, os.path, re, time
from optparse import OptionParser

htmlFilters = {'odt': 'HTML (StarWriter)',
               'ods': 'HTML (StarCalc)',
               'odp': 'impress_html_Export'}

FILE_TYPES = {'odt': 'writer8',
              'ods': 'calc8',
              'odp': 'impress8',
              'htm': htmlFilters, 'html': htmlFilters,
              'rtf': 'Rich Text Format',
              'txt': 'Text',
              'csv': 'Text - txt - csv (StarCalc)',
              'pdf': {'odt': 'writer_pdf_Export',  'ods': 'calc_pdf_Export',
                      'odp': 'impress_pdf_Export', 'htm': 'writer_pdf_Export',
                      'html': 'writer_pdf_Export', 'rtf': 'writer_pdf_Export',
                      'txt': 'writer_pdf_Export', 'csv': 'calc_pdf_Export',
                      'swf': 'draw_pdf_Export', 'doc': 'writer_pdf_Export',
                      'xls': 'calc_pdf_Export', 'ppt': 'impress_pdf_Export',
                      'docx': 'writer_pdf_Export', 'xlsx': 'calc_pdf_Export'
                      },
              'swf': 'impress_flash_Export',
              'doc': 'MS Word 97',
              'xls': 'MS Excel 97',
              'ppt': 'MS PowerPoint 97',
              'docx': 'MS Word 2007 XML',
              'xlsx': 'Calc MS Excel 2007 XML',
}
# Conversion from odt to odt does not make any conversion, but updates indexes
# and linked documents.

# ------------------------------------------------------------------------------
class ConverterError(Exception): pass

# Constants and messages -------------------------------------------------------
DOC_NOT_FOUND = '"%s" not found.'
URL_NOT_FOUND = 'Doc URL "%s" is wrong. %s'
INPUT_TYPE_ERROR = 'Wrong input type "%s".'
BAD_RESULT_TYPE = 'Bad result type "%s". Available types are %s.'
CANNOT_WRITE_RESULT = 'I cannot write result "%s". %s'
CONNECT_ERROR = "Couldn't not connect to LibreOffice on port %d. %s"
DEFAULT_PORT = 2002

HELP_PORT = "The port on which LibreOffice runs (default is %d)." % DEFAULT_PORT
HELP_TEMPLATE = 'The path to a LibreOffice template from which you may ' \
                'import styles.'
HELP_OPTIMAL_COLUMN_WIDTHS = 'Set this option to "True" if you want ' \
  'LibreOffice to optimize column widths for all tables included in the ' \
  'document. Alternately, specify a regular expression: only tables whose ' \
  'name match will be optimized. And if the expression starts with char "~", ' \
  'only tables not matching it will be optimized.'
HELP_SCRIPT = 'You can specify here (the absolute path to) a Python script ' \
  'containing functions that the converter will call in order to customize ' \
  'the process of manipulating the document via the LibreOffice UNO ' \
  'interface. The following functions can be defined in your script and must ' \
  'all accept a single parameter: the Converter instance. ' \
  '***updateTableOfContents***, if defined, will be called for producing a ' \
  'custom table of contents. At the time this function is called by the ' \
  'converter, converter.toc will contain the table of contents, already ' \
  'updated by LibreOffice. ***finalize*** will be called at the end of the '\
  'process, just before saving the result.'
HELP_VERBOSE = 'Writes more information on stdout.'

# ------------------------------------------------------------------------------
class LoIter:
    '''Iterates over a collection of LibreOffice-UNO objects'''
    def __init__(self, collection, log=None, reverse=False):
        self.collection = collection
        self.count = collection.getCount()
        # Log the number of walked elements when relevant
        if log: log(self.count, cr=False)
        self.reverse = reverse
        if reverse:
            self.i = self.count - 1
        else:
            self.i = 0
        from com.sun.star.lang import IndexOutOfBoundsException
        self.error = IndexOutOfBoundsException

    def __iter__(self): return self

    def __next__(self):
        try:
            elem = self.collection.getByIndex(self.i)
            if self.reverse: self.i -= 1
            else: self.i += 1
            return elem
        except self.error:
            # IndexOutOfBoundsException can be raised because sometimes UNO
            # returns a number higher than the real number of elements. This is
            # because, in documents including sub-documents, it also counts the
            # sections that are present within these sub-documents.
            raise StopIteration
    next = __next__ # Python2-3 compliance

# ------------------------------------------------------------------------------
class Converter:
    '''Converts a document readable by LibreOffice into pdf, doc, txt, rtf...'''
    def __init__(self, docPath, resultType, port=DEFAULT_PORT,
                 templatePath=None, optimalColumnWidths=None, script=None,
                 verbose=False):
        self.port = port
        # The path to the document to convert
        self.docUrl, self.docPath = self.getFilePath(docPath)
        self.inputType = self.getInputType(docPath)
        # "resultType" determines the type of the converted file (=a file
        # extension among FILE_TYPES keys). "resultMultiple" is True if several
        # result files will be produced (like when producing one CSV file for
        # every sheet from an Excel file).
        self.resultType, self.resultMultiple = self.getResultType(resultType)
        self.resultFilter = self.getResultFilter()
        self.resultUrl = self.getResultUrl()
        self.oo = None # The LibreOffice application object
        self.doc = None # The LibreOffice loaded document
        self.version = None # The LibreOffice version
        self.toc = None # The table of contents, if existing
        # The path to a LibreOffice template (ie, a ".ott" file) from which
        # styles can be imported
        self.templateUrl = self.templatePath = None
        if templatePath:
            self.templateUrl, self.templatePath = self.getFilePath(templatePath)
        # Optimal column widths
        self.optimalColumnWidths = optimalColumnWidths
        # Functions extracted from the custom Python script that will be called
        # by the Converter for customizing the result.
        if script:
            self.functions = self.getCustomFunctions(script)
        else:
            self.functions = {}
        # Verbosity
        self.verbose = verbose

    def log(self, msg, cr=True):
        '''Logs some p_msg if we are in verbose mode'''
        if not self.verbose: return
        if not isinstance(msg, str): msg = str(msg)
        sys.stdout.write(msg)
        if cr:
            sys.stdout.write('\n')

    def getInputType(self, docPath):
        '''Extracts the input type from the p_docPath'''
        res = os.path.splitext(docPath)[1][1:].lower()
        if res not in FILE_TYPES: raise ConverterError(INPUT_TYPE_ERROR % res)
        return res

    def getResultType(self, resultType):
        '''If result type ends with char '*', it means that several output files
           will be produced, ie for getting a CSV file from every Excel or Calc
           sheet.'''
        if resultType.endswith('*'): return resultType[:-1], True
        return resultType, False

    def getCustomFunctions(self, script):
        '''Compiles and executes the Python p_script and returns a dict
           containing its namespace.'''
        f = open(script)
        content = f.read()
        f.close()
        names = {}
        exec(compile(content, script, 'exec'), names)
        return names

    def getFilePath(self, filePath):
        '''Returns the absolute path of p_filePath. In fact, it returns a
           tuple with some URL version of the path for LO as the first element
           and the absolute path as the second element.''' 
        import unohelper
        if not os.path.exists(filePath) and not os.path.isfile(filePath):
            raise ConverterError(DOC_NOT_FOUND % filePath)
        docAbsPath = os.path.abspath(filePath)
        # Return one path for OO, one path for me
        return unohelper.systemPathToFileUrl(docAbsPath), docAbsPath

    def getResultFilter(self):
        '''Based on the result type, identifies which OO filter to use for the
           document conversion.'''
        if self.resultType in FILE_TYPES:
            res = FILE_TYPES[self.resultType]
            if isinstance(res, dict):
                res = res[self.inputType]
        else:
            raise ConverterError(BAD_RESULT_TYPE % (self.resultType,
                                                    FILE_TYPES.keys()))
        return res

    def getResultUrl(self):
        '''Returns the path of the result file in the format needed by LO. If
           the result type and the input type are the same (ie the user wants to
           refresh indexes or some other action and not perform a real
           conversion), the result file is named
                           <inputFileName>.res.<resultType>.

           Else, the result file is named like the input file but with a
           different extension:
                           <inputFileName>.<resultType>
        '''
        import unohelper
        baseName = os.path.splitext(self.docPath)[0]
        if self.resultType != self.inputType:
            res = '%s.%s' % (baseName, self.resultType)
        else:
            res = '%s.res.%s' % (baseName, self.resultType)
        try:
            f = open(res, 'w')
            f.write('Hello')
            f.close()
            os.remove(res)
            return unohelper.systemPathToFileUrl(res)
        except (OSError, IOError):
            e = sys.exc_info()[1]
            raise ConverterError(CANNOT_WRITE_RESULT % (res, e))

    def props(self, properties):
        '''Create a UNO-compliant tuple of properties, from tuple p_properties
           containing sub-tuples (s_propertyName, value).'''
        from com.sun.star.beans import PropertyValue
        res = []
        for name, value in properties:
            prop = PropertyValue()
            prop.Name = name
            prop.Value = value
            res.append(prop)
        return tuple(res)

    def getVersion(self, serviceManager):
        '''Returns the LO version'''
        name = 'com.sun.star.configuration.ConfigurationProvider'
        configProvider = serviceManager.createInstance(name)
        prop = self.props([('nodepath', '/org.openoffice.Setup/Product')])
        nodeName = 'com.sun.star.configuration.ConfigurationAccess'
        try:
            node = configProvider.createInstanceWithArguments(nodeName, prop)
            return node.getByName('ooSetupVersion')
        except Exception:
            # LibreOffice 3 raises an exception here
            return '3.0'

    def connect(self):
        '''Connects to LibreOffice'''
        if os.name == 'nt':
            import socket
        import uno
        from com.sun.star.connection import NoConnectException
        try:
            # Get the uno component context from the PyUNO runtime
            context = uno.getComponentContext()
            create = context.ServiceManager.createInstanceWithContext
            # Get the LO version
            self.version = self.getVersion(context.ServiceManager)
            # Create the UnoUrlResolver
            resolver = create('com.sun.star.bridge.UnoUrlResolver', context)
            # Connect to LO running on self.port
            docContext = resolver.resolve(
                'uno:socket,host=localhost,port=%d;urp;StarOffice.' \
                'ComponentContext' % self.port)
            # Is seems that we can't define a timeout for this method. This
            # would be useful because when a non-LO server already listens
            # to self.port, this method blocks.
            self.log('Getting the UNO-LO instance...', cr=False)
            self.oo = docContext.ServiceManager.createInstanceWithContext(
                'com.sun.star.frame.Desktop', docContext)
            # If we must optimize table column widths, create a dispatch helper
            if self.optimalColumnWidths:
                helper = create('com.sun.star.frame.DispatchHelper', context)
                self.dispatchHelper = helper
            self.log(' done.')
        except NoConnectException:
            e = sys.exc_info()[1]
            raise ConverterError(CONNECT_ERROR % (self.port, e))

    def optimizeTableColumnWidths(self, table, viewCursor, frame):
        '''Optimize column widths for this p_table'''
        cursor = table.getCellByName('A1').createTextCursor()
        viewCursor.gotoRange(cursor, False)
        viewCursor.gotoEnd(True)
        viewCursor.gotoEnd(True)
        do = self.dispatchHelper.executeDispatch
        # When column sizes are defined, the "SetOptimalColumnWidth" algorithm
        # could not work optimally. Applying algo "DistributeColumns" before
        # allows to solve this problem.
        do(frame, '.uno:DistributeColumns', '', 0, ())
        # With LibreOffice < 5, range selection must be done again
        if self.version < '5.0':
            viewCursor.gotoRange(cursor, False)
            viewCursor.gotoEnd(True)
            viewCursor.gotoEnd(True)
        do(frame, '.uno:SetOptimalColumnWidth', '', 0, ())

    def updateOdtDocument(self):
        '''If the input file is an ODT document, we will perform those tasks:
           1) update all indexes;
           2) update sections (if sections refer to external content, we try to
              include the content within the result file);
           3) update table column's widths when relevant;
           4) load styles from an external template if given.
        '''
        log = self.log
        # Getting some base LO objects is required
        controller = self.doc.getCurrentController()
        viewCursor = controller.getViewCursor()
        # 1) Update all indexes
        for index in LoIter(self.doc.getDocumentIndexes(), log):
            index.update()
            if index.ServiceName == 'com.sun.star.text.ContentIndex':
                # Allow easy access to the table of contents
                self.toc = index
                # Call custom code to update the TOC when relevant
                fun = self.functions.get('updateTableOfContents')
                if fun: fun(self)
        # Future: allow to update/resolve text fields
        #for field in self.doc.TextFields:
        #    anchor = field.getAnchor()
        #    cursor = anchor.getText().createTextCursorByRange(anchor)
        #    fieldContent = field.getPresentation(False)
        #    viewCursor.gotoRange(cursor, False)
        #    viewCursor.setString(fieldContent)
        # Avoid doing this if field.SubType.value ==
        #         "com.sun.star.text.PageNumberType" (and is in a footer).
        log(' index(es) updated.')
        # 2) Update sections
        self.doc.updateLinks()
        for section in LoIter(self.doc.getTextSections(), log, reverse=True):
            # I must walk into the section from last one to the first one. Else,
            # when "disposing" sections, I remove sections and the remaining
            # ones get another index.
            if section.FileLink and section.FileLink.FileURL:
                # This call removes the <section></section> tags without
                # removing the content of the section. Else, it won't appear.
                section.dispose()
        log(' section(s) updated.')
        # 3) Update tables
        count = 0
        if self.optimalColumnWidths:
            optimal = self.optimalColumnWidths
            if isinstance(optimal, bool):
                rex = None
            else: # A regular expression
                if optimal.startswith('~'):
                    rex = optimal[1:]
                    inverse = True
                else:
                    rex = optimal
                    inverse = False
                rex = re.compile(rex)
            # Browse tables
            frame = controller.getFrame()
            for table in LoIter(self.doc.getTextTables()):
                # Must column sizes be optimized for this table ?
                if not rex:
                    optimize = True
                else:
                    optimize = rex.match(table.Name)
                    if inverse: optimize = not optimize
                if optimize:
                    self.optimizeTableColumnWidths(table, viewCursor, frame)
                    count += 1
        log('%d table(s) with optimized widths.' % count)
        # 4) Import styles from an external file when required
        if self.templateUrl:
            params = self.props((('OverwriteStyles', True),
                                 ('LoadPageStyles', False)))
            self.doc.StyleFamilies.loadStylesFromURL(self.templateUrl, params)
            log('Styles loaded from %s.' % self.templateUrl)

    def loadDocument(self):
        from com.sun.star.lang import IllegalArgumentException
        try:
            # Loads the document to convert in a new hidden frame
            self.log('Loading in LO file %s...' % self.docUrl, cr=False)
            props = [('Hidden', True)]
            if self.inputType == 'csv':
                # Give some additional params if we need to open a CSV file
                props.append(('FilterFlags', '59,34,76,1'))
                #props.append(('FilterData', 'Any'))
            self.doc = self.oo.loadComponentFromURL(self.docUrl, "_blank", 0,
                                                    self.props(props))
            self.log(' done.')
            # Perform additional tasks for odt documents
            if self.inputType == 'odt': self.updateOdtDocument()
            try:
                self.doc.refresh()
            except AttributeError:
                pass
        except IllegalArgumentException:
            e = sys.exc_info()[1]
            raise ConverterError(URL_NOT_FOUND % (self.docPath, e))

    def convertDocument(self):
        '''Calls LO to perform a document conversion. Note that the conversion
           is not really done if the source and target documents have the same
           type.'''
        self.log('Saving the result in %s...' % self.resultUrl, cr=False)
        props = [('FilterName', self.resultFilter)]
        if self.resultType == 'csv': # Add options for CSV export
            props.append(('FilterOptions', '59,34,76,1')) # 59=; 34=" 
        elif self.resultType == 'pdf':
            props.append(('ExportNotes', True))
        if not self.resultMultiple:
            self.doc.storeToURL(self.resultUrl, self.props(props))
            self.log(' done.')
        else:
            # Dump one CSV file for every sheet in the input document
            import unicodedata
            doc = self.doc
            sheets = self.doc.getSheets()
            sheetsCount = sheets.getCount()
            controller = doc.getCurrentController()
            props = self.props(props)
            for i in range(sheetsCount):
                sheet = sheets.getByIndex(i)
                # Compute the csv output file name
                name = unicodedata.normalize('NFKD', sheet.getName())
                splitted = os.path.splitext(self.resultUrl)
                resultUrl = '%s.%s%s' % (splitted[0], name, splitted[1])
                controller.setActiveSheet(sheet)
                doc.storeToURL(resultUrl, props)

    def run(self):
        '''Connects to LO, does the job and disconnects'''
        if self.verbose: start = time.time()
        self.connect()
        self.loadDocument()
        # Call custom code to modify the document when relevant
        fun = self.functions.get('finalize')
        if fun: fun(self)
        # Store the (converted) result
        self.convertDocument()
        self.doc.close(True)
        if self.verbose:
            self.log('Done in %.2f second(s).' % (time.time() - start))

# ConverterScript constants ----------------------------------------------------
WRONG_NB_OF_ARGS = 'Wrong number of arguments.'
ERROR_CODE = 1
usage = '''usage: python converter.py fileToConvert outputType [options]

   "fileToConvert" is the absolute or relative pathname of the file you
   want to convert (or whose content like indexes need to be refreshed)
   
   "outputType" is the output format, that must be one of:
   %s

   "python" should be a UNO-enabled Python interpreter (ie the one which is
   included in the LibreOffice distribution).''' % str(FILE_TYPES.keys())

# ------------------------------------------------------------------------------
class ConverterScript:
    '''The command-line program'''
    def run(self):
        optParser = OptionParser(usage=usage)
        add = optParser.add_option
        add('-p', '--port', dest='port', default=DEFAULT_PORT,
            metavar='PORT', type='int', help=HELP_PORT)
        add('-t', '--template', dest='template', default=None,
            metavar='TEMPLATE', type='string', help=HELP_TEMPLATE)
        add('-o', '--optimalColumnWidths', dest='optimalColumnWidths',
            default=None, metavar='OPTIMAL_COL_WIDTHS', type='string',
            help=HELP_OPTIMAL_COLUMN_WIDTHS)
        add('-s', '--script', dest='script', default=None, metavar='SCRIPT',
            type='string', help=HELP_SCRIPT)
        add('-v', '--verbose', action='store_true', help=HELP_VERBOSE)
        (options, args) = optParser.parse_args()
        if len(args) != 2:
            sys.stderr.write(WRONG_NB_OF_ARGS)
            sys.stderr.write('\n')
            optParser.print_help()
            sys.exit(ERROR_CODE)
        optimal = options.optimalColumnWidths
        if optimal in ('True', 'False'):
            optimal = eval(optimal)
        verbose = options.verbose == True
        converter = Converter(args[0], args[1], options.port, options.template,
                              optimal, options.script, verbose)
        try:
            converter.run()
        except ConverterError:
            e = sys.exc_info()[1]
            sys.stderr.write(str(e))
            sys.stderr.write('\n')
            optParser.print_help()
            sys.exit(ERROR_CODE)

# ------------------------------------------------------------------------------
if __name__ == '__main__':
    ConverterScript().run()
# ------------------------------------------------------------------------------
