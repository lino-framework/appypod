'''Utility modules and functions for Appy'''

# ------------------------------------------------------------------------------
import traceback, mimetypes, subprocess

# ------------------------------------------------------------------------------
class Version:
    '''Appy version'''
    short = '1.0.0'
    verbose = 'Appy %s' % short

    @classmethod
    def get(klass):
        '''Returns a string containing the short and verbose Appy version'''
        if klass.short == 'dev': return 'dev'
        return '%s (%s)' % (klass.short, klass.verbose)

    @classmethod
    def isGreaterThanOrEquals(klass, v):
        '''This method returns True if the current Appy version is greater than
           or equals p_v. p_v must have a format like "0.5.0".'''
        if klass.short == 'dev':
            # We suppose that a developer knows what he is doing
            return True
        else:
            paramVersion = [int(i) for i in v.split('.')]
            currentVersion = [int(i) for i in klass.short.split('.')]
            return currentVersion >= paramVersion

# Global variables -------------------------------------------------------------
sequenceTypes = (list, tuple)
commercial = False

# MIME-related stuff -----------------------------------------------------------
od = 'application/vnd.oasis.opendocument'
ms = 'application/vnd.openxmlformats-officedocument'
ms2 = 'application/vnd.ms'

mimeTypes = {'odt': '%s.text' % od,
             'ods': '%s.spreadsheet' % od,
             'doc': 'application/msword',
             'rtf': 'text/rtf',
             'pdf': 'application/pdf'
             }
mimeTypesExts = {
    '%s.text' % od:        'odt',
    '%s.spreadsheet' % od: 'ods',
    'application/msword':  'doc',
    'text/rtf':            'rtf',
    'application/pdf':     'pdf',
    'image/png':           'png',
    'image/jpeg':          'jpg',
    'image/pjpeg':         'jpg',
    'image/gif':           'gif',
    '%s.wordprocessingml.document' % ms: 'docx',
    '%s.spreadsheetml.sheet' % ms: 'xlsx',
    '%s.presentationml.presentation' % ms: 'pptx',
    '%s-excel' % ms2:      'xls',
    '%s-powerpoint' % ms2: 'ppt',
    '%s-word.document.macroEnabled.12' % ms2: 'docm',
    '%s-excel.sheet.macroEnabled.12' % ms2: 'xlsm',
    '%s-powerpoint.presentation.macroEnabled.12' % ms2: 'pptm'}

def getMimeType(fileName, default='application/octet-stream'):
    '''Tries to guess mime type from p_fileName'''
    res, encoding = mimetypes.guess_type(fileName)
    if not res:
        if fileName.endswith('.po'):
            res = 'text/plain'
            encoding = 'utf-8'
    if not res: return default
    if not encoding: return res
    return '%s;;charset=%s' % (res, encoding)

# ------------------------------------------------------------------------------
class CommercialError(Exception):
    '''Raised when some functionality is called from the commercial version but
       is available only in the free, open source version.'''
    MSG = 'This feature is not available in the commercial version. It is ' \
          'only available in the free, open source (GPL) version of Appy.'
    def __init__(self): Exception.__init__(self, self.MSG)

class MessageException(Exception): pass

# ------------------------------------------------------------------------------
class No:
    '''When you write a workflow condition method and you want to return False
       but you want to give to the user some explanations about why a transition
       can't be triggered, do not return False, return an instance of No
       instead. When creating such an instance, you can specify an error
       message.'''
    def __init__(self, msg): self.msg = msg
    def __nonzero__(self): return False
    def __repr__(self): return '<No: %s>' % self.msg

# ------------------------------------------------------------------------------
def initMasterValue(v):
    '''Standardizes p_v as a list of strings, excepted if p_v is a method'''
    if callable(v): return v
    if not isinstance(v, bool) and not v: res = []
    elif type(v) not in sequenceTypes: res = [v]
    else: res = v
    return [str(v) for v in res]

# ------------------------------------------------------------------------------
def encodeData(data, encoding=None):
    '''Applies some p_encoding to string p_data, but only if an p_encoding is
       specified.'''
    if not encoding: return data
    return data.encode(encoding)

# ------------------------------------------------------------------------------
def copyData(data, target, targetMethod, type='string', encoding=None,
             chunkSize=1024):
    '''Copies p_data to a p_target, using p_targetMethod. For example, it copies
       p_data which is a string containing the binary content of a file, to
       p_target, which can be a HTTP connection or a file object.

       p_targetMethod can be "write" (files) or "send" (HTTP connections) or ...
       p_type can be "string" or "file". In the latter case, one may, in
       p_chunkSize, specify the amount of bytes transmitted at a time.

       If an p_encoding is specified, it is applied on p_data before copying.

       Note that if the p_target is a Python file, it must be opened in a way
       that is compatible with the content of p_data, ie open('myFile.doc','wb')
       if content is binary.'''
    dump = getattr(target, targetMethod)
    if not type or (type == 'string'): dump(encodeData(data, encoding))
    elif type == 'file':
        while True:
            chunk = data.read(chunkSize)
            if not chunk: break
            dump(encodeData(chunk, encoding))

# List/dict manipulations ------------------------------------------------------
def splitList(l, sub):
    '''Returns a list that was build from list p_l whose elements were
       re-grouped into sub-lists of p_sub elements.

       For example, if l = [1,2,3,4,5] and sub = 3, the method returns
       [ [1,2,3], [4,5] ].'''
    res = []
    i = -1
    for elem in l:
        i += 1
        if (i % sub) == 0:
            # A new sub-list must be created
            res.append([elem])
        else:
            res[-1].append(elem)
    return res

class IterSub:
    '''Iterator over a list of lists'''
    def __init__(self, l):
        self.l = l
        self.i = 0 # The current index in the main list
        self.j = 0 # The current index in the current sub-list
    def __iter__(self): return self
    def next(self):
        # Get the next ith sub-list
        if (self.i + 1) > len(self.l): raise StopIteration
        sub = self.l[self.i]
        if (self.j + 1) > len(sub):
            self.i += 1
            self.j = 0
            return self.next()
        else:
            elem = sub[self.j]
            self.j += 1
            return elem

def getElementAt(l, cyclicIndex):
    '''Gets the element within list/tuple p_l that is at index p_cyclicIndex
       (int). If the index out of range, we do not raise IndexError: we continue
       to loop over the list until we reach this index.'''
    return l[cyclicIndex % len(l)]

def flipDict(d):
    '''Flips dict p_d: keys become values, values become keys. p_d is left
       untouched: a new, flipped, dict is returned.'''
    r = {}
    for k, v in d.items(): r[v] = k
    return r

def addPair(name, value, d=None):
    '''Adds key-value pair (name, value) to dict p_d. If this dict is None, it
       returns a newly created dict.'''
    if d: d[name] = value
    else: d = {name: value}
    return d

# ------------------------------------------------------------------------------
class Traceback:
    '''Dumps the last traceback into a string'''
    @staticmethod
    def get(last=None):
        '''Gets the traceback as a string. If p_last is given (must be an
           integer value), only the p_last lines of the traceback will be
           included. It can be useful for pod/px tracebacks: when an exception
           occurs while evaluating a complex tree of buffers, most of the
           traceback lines concern uninteresting buffer/action-related recursive
           calls.'''
        return traceback.format_exc(last)

# ------------------------------------------------------------------------------
def executeCommand(cmd):
    '''Executes command p_cmd and returns a tuple (s_stdout, s_stderr)
       containing the data output by the subprocesss on stdout and stderr. p_cmd
       should be a list of args (the 1st arg being the command in itself, the
       remaining args being the parameters), but it can also be a string, too
       (see subprocess.Popen doc).'''
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.communicate()

# ------------------------------------------------------------------------------
def callMethod(obj, method, klass=None, cache=True):
    '''This function is used to call a p_method on some Appy p_obj. m_method
       can be an instance method on p_obj; it can also be a static method. In
       this latter case, p_obj is the tool and the static method, defined in
       p_klass, will be called with the tool as unique arg.

       A method cache is implemented on the request object (available at
       p_obj.request). So while handling a single request from the ui, every
       method is called only once. Some method calls must not be cached (ie,
       values of Computed fields). In this case, p_cache will be False.'''
    rq = obj.request
    # Create the method cache if it does not exist on the request
    if not hasattr(rq, 'methodCache'): rq.methodCache = {}
    # If m_method is a static method or an instance method, unwrap the true
    # Python function object behind it.
    methodType = method.__class__.__name__
    if methodType == 'staticmethod':
        method = method.__get__(klass)
    elif methodType == 'instancemethod':
        method = method.im_func
    # Call the method if cache is not needed
    if not cache: return method(obj)
    # If first arg of method is named "tool" instead of the traditional "self",
    # we cheat and will call the method with the tool as first arg. This will
    # allow to consider this method as if it was a static method on the tool.
    # Every method call, even on different instances, will be cached in a unique
    # key.
    cheat = False
    if not klass and (method.func_code.co_varnames[0] == 'tool'):
        prefix = obj.klass.__name__
        obj = obj.tool
        cheat = True
    # Build the key of this method call in the cache.
    # First part of the key: the p_obj's uid (if p_method is an instance method)
    # or p_className (if p_method is a static method).
    if not cheat:
        if klass:
            prefix = klass.__name__
        else:
            prefix = obj.uid
    # Second part of the key: p_method name
    key = '%s:%s' % (prefix, method.func_name)
    # Return the cached value if present in the method cache
    if key in rq.methodCache:
        return rq.methodCache[key]
    # No cached value: call the method, cache the result and return it
    res = method(obj)
    rq.methodCache[key] = res
    return res

# ------------------------------------------------------------------------------
def formatNumber(n, sep=',', precision=2, tsep=' ', removeTrailingZeros=False):
    '''Returns a string representation of number p_n, which can be a float
       or integer. p_sep is the decimal separator to use. p_precision is the
       number of digits to keep in the decimal part for producing a nice rounded
       string representation. p_tsep is the "thousands" separator.'''
    if n == None: return ''
    # Manage precision
    if precision == None:
        res = str(n)
    else:
        format = '%%.%df' % precision
        res = format % n
    # Use the correct decimal separator
    res = res.replace('.', sep)
    # Insert p_tsep every 3 chars in the integer part of the number
    splitted = res.split(sep)
    res = ''
    if len(splitted[0]) < 4: res = splitted[0]
    else:
        i = len(splitted[0])-1
        j = 0
        while i >= 0:
            j += 1
            res = splitted[0][i] + res
            if (j % 3) == 0:
                res = tsep + res
            i -= 1
    # Add the decimal part if not 0
    if len(splitted) > 1:
        try:
            decPart = int(splitted[1])
            if decPart != 0:
                res += sep + splitted[1]
            if removeTrailingZeros: res = res.rstrip('0')
        except ValueError:
            # This exception may occur when the float value has an "exp"
            # part, like in this example: 4.345e-05
            res += sep + splitted[1]
    return res

def roundNumber(n, base=5):
    '''Rounds an integer number p_n to an integer value being p_base'''
    return int(base * round(float(n)/base))

# ------------------------------------------------------------------------------
class FileWrapper:
    '''When you get, from an appy object, the value of a File attribute, you
       get an instance of this class.'''
    CONVERSION_ERROR = 'An error occurred. %s'

    def __init__(self, zopeFile):
        '''This constructor is only used by Appy to create a nice File instance
           from a Zope corresponding instance (p_zopeFile). If you need to
           create a new file and assign it to a File attribute, use the
           attribute setter, do not create yourself an instance of this
           class.'''
        d = self.__dict__
        d['_zopeFile'] = zopeFile # Not for you!
        d['name'] = zopeFile.filename
        d['content'] = zopeFile.data
        d['mimeType'] = zopeFile.content_type
        d['size'] = zopeFile.size # In bytes

    def __setattr__(self, name, v):
        d = self.__dict__
        if name == 'name':
            self._zopeFile.filename = v
            d['name'] = v
        elif name == 'content':
            self._zopeFile.update_data(v, self.mimeType, len(v))
            d['content'] = v
            d['size'] = len(v)
        elif name == 'mimeType':
            self._zopeFile.content_type = self.mimeType = v
        else:
            raise 'Impossible to set attribute %s. "Settable" attributes ' \
                  'are "name", "content" and "mimeType".' % name

    def dump(self, filePath=None, format=None, tool=None):
        '''Writes the file on disk. If p_filePath is specified, it is the
           path name where the file will be dumped; folders mentioned in it
           must exist. If not, the file will be dumped in the OS temp folder.
           The absolute path name of the dumped file is returned.
           If an error occurs, the method returns None. If p_format is
           specified, LibreOffice will be called for converting the dumped file
           to the desired format. In this case, p_tool, a Appy tool, must be
           provided. Indeed, any Appy tool contains parameters for contacting
           LibreOffice in server mode.'''
        if not filePath:
            filePath = '%s/file%f.%s' % (getOsTempFolder(), time.time(),
                normalizeString(self.name))
        f = open(filePath, 'w')
        if self.content.__class__.__name__ == 'Pdata':
            # The file content is splitted in several chunks.
            f.write(self.content.data)
            nextPart = self.content.next
            while nextPart:
                f.write(nextPart.data)
                nextPart = nextPart.next
        else:
            # Only one chunk
            f.write(self.content)
        f.close()
        if format:
            if not tool: return
            # Convert the dumped file using OpenOffice
            out, err = tool.convert(filePath, format)
            # Even if we have an "error" message, it could be a simple warning.
            # So we will continue here and, as a subsequent check for knowing if
            # an error occurred or not, we will test the existence of the
            # converted file (see below).
            os.remove(filePath)
            # Return the name of the converted file.
            baseName, ext = os.path.splitext(filePath)
            if (ext == '.%s' % format):
                filePath = '%s.res.%s' % (baseName, format)
            else:
                filePath = '%s.%s' % (baseName, format)
            if not os.path.exists(filePath):
                tool.log(self.CONVERSION_ERROR % err, type='error')
                return
        return filePath

    def copy(self):
        '''Returns a copy of this file'''
        return FileWrapper(self._zopeFile._getCopy(self._zopeFile))
# ------------------------------------------------------------------------------
