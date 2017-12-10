# ------------------------------------------------------------------------------
import re, unicodedata

# ------------------------------------------------------------------------------
charsIgnore = '.,:;*+=~?%^\'’"<>{}[]|\t\\°-'
fileNameIgnore = charsIgnore + ' $£€/\r\n'
extractIgnore = charsIgnore + '/()'
alphaRex = re.compile(b'[a-zA-Z]')
alphanumRex = re.compile(b'[a-zA-Z0-9]')
alphanum_Rex = re.compile(b'[a-zA-Z0-9_]')

def normalizeString(s, usage='fileName'):
    '''Returns a version of string p_s whose special chars (like accents) have
       been replaced with normal chars. Moreover, if p_usage is:
       * fileName: it removes any char that can't be part of a file name;
       * alphanum: it removes any non-alphanumeric char;
       * alpha: it removes any non-letter char.
    '''
    strNeeded = isinstance(s, str)
    # We work in unicode. Convert p_s to unicode if not unicode.
    if isinstance(s, str):
        try:
            s = s.decode('utf-8')
        except UnicodeDecodeError:
            # Another encoding may be in use
            s = s.decode('latin-1')
    elif not isinstance(s, unicode): s = unicode(s)
    # For extracted text, replace any unwanted char with a blank
    if usage == 'extractedText':
        res = u''
        for char in s:
            if char not in extractIgnore: res += char
            else: res += ' '
        s = res
    # Standardize special chars like accents
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore')
    # Remove any other char, depending on p_usage
    if usage == 'fileName':
        # Remove any char that can't be found within a file name under Windows
        # or that could lead to problems with LibreOffice.
        res = ''
        for char in s:
            if char not in fileNameIgnore: res += char
    elif usage.startswith('alpha'):
        exec('rex = %sRex' % usage)
        res = ''
        for char in s:
            if rex.match(char): res += char
    elif usage == 'noAccents':
        res = s
    else:
        res = s
    # Re-code the result as a str if a str was given
    if strNeeded: res = res.encode('utf-8')
    return res

def normalizeText(s, lower=True):
    '''Remove from p_s special chars and lowerize it (if p_lower is True) for
       indexing or other purposes.'''
    r = normalizeString(s, usage='extractedText').strip()
    if lower: r = r.lower()
    return r

def keepDigits(s):
    '''Returns string p_s whose non-number chars have been removed'''
    if s is None: return s
    res = ''
    for c in s:
        if c.isdigit(): res += c
    return res

def keepAlphanum(s):
    '''Returns string p_s whose non-alphanum chars have been removed'''
    if s is None: return s
    res = ''
    for c in s:
        if c.isalnum(): res += c
    return res

def getStringFrom(o):
    '''Returns a string representation for p_o that can be transported over
       HTTP and manipulated in Javascript.'''
    if isinstance(o, dict):
        res = []
        for k, v in o.items():
            res.append("%s:%s" % (getStringFrom(k), getStringFrom(v)))
        return '{%s}' % ','.join(res)
    elif isinstance(o, list) or isinstance(o, tuple):
        return '[%s]' % ','.join([getStringFrom(v) for v in o])
    else:
        if not isinstance(o, basestring): o = str(o)
        return "'%s'" % (o.replace("'", "\\'"))

def getDictFrom(s):
    '''Returns a dict from string representation p_s of the form
       "key1:value1,key2:value2".'''
    res = {}
    if s:
        for part in s.split(','):
            key, value = part.split(':')
            res[key] = value
    return res

def sadd(s, sub, sep=' '):
    '''Adds sub-string p_sub into p_s, which is a list of sub-strings separated
       by p_sep, and returns the updated string.'''
    if not sub: return s
    if not s: return sub
    elems = set(s.split(sep)).union(set(sub.split(sep)))
    return sep.join(elems)

def sremove(s, sub, sep=' '):
    '''Removes sub-string p_sub from p_s, which is a list of sub-strings
       separated by p_sep, and returns the updated string.'''
    if not sub: return s
    if not s: return s
    elems = set(s.split(sep))
    for elem in sub.split(sep):
        if elem in elems:
            elems.remove(elem)
    return sep.join(elems)

def stretchText(s, pattern, char=' '):
    '''Inserts occurrences of p_char within p_s according to p_pattern.
       Example: stretchText("475123456", (3,2,2,2)) returns '475 12 34 56'.'''
    res = ''
    i = 0
    for nb in pattern:
        j = 0
        while j < nb:
            res += s[i+j]
            j += 1
        res += char
        i += nb
    return res

# ------------------------------------------------------------------------------
class PasswordGenerator:
    '''Class used to generate passwords'''
    # No "0" or "1" that could be interpreted as letters "O" or "l"
    passwordDigits = '23456789'
    # No letters i, l, o (nor lowercase nor uppercase) that could be misread
    passwordLetters = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ'

    @classmethod
    def get(k, minLength=5, maxLength=9):
        '''Generates and r_eturns a password whose length is between p_minLength
           and p_maxLength.'''
        # Compute the actual length of the challenge to encode
        length = random.randint(minLength, maxLength)
        r = ''
        for i in range(length):
            j = random.randint(0, 1)
            chars = (j == 0) and k.passwordDigits or k.passwordLetters
            # Choose a char
            r += chars[random.randint(0,len(chars)-1)]
        return r

# ------------------------------------------------------------------------------
def lower(s):
    '''French-accents-aware variant of string.lower.'''
    isUnicode = isinstance(s, unicode)
    if not isUnicode: s = s.decode('utf-8')
    res = s.lower()
    if not isUnicode: res = res.encode('utf-8')
    return res

def upper(s):
    '''French-accents-aware variant of string.upper.'''
    isUnicode = isinstance(s, unicode)
    if not isUnicode: s = s.decode('utf-8')
    res = s.upper()
    if not isUnicode: res = res.encode('utf-8')
    return res

# ------------------------------------------------------------------------------
class WhitespaceCruncher:
    '''Takes care of removing unnecessary whitespace in several contexts'''
    whitechars = u' \r\t\n' # Chars considered as whitespace
    allWhitechars = whitechars + u' ' # nbsp
    @staticmethod
    def crunch(s, previous=None):
        '''Return a version of p_s (expected to be a unicode string) where all
           "whitechars" are:
           * converted to real whitespace;
           * reduced in such a way that there cannot be 2 consecutive
             whitespace chars.
           If p_previous is given, those rules must also apply globally to
           previous+s.'''
        res = ''
        # Initialise the previous char
        if previous:
            previousChar = previous[-1]
        else:
            previousChar = u''
        for char in s:
            if char in WhitespaceCruncher.whitechars:
                # Include the current whitechar in the result if the previous
                # char is not a whitespace or nbsp.
                if not previousChar or \
                   (previousChar not in WhitespaceCruncher.allWhitechars):
                    res += u' '
            else: res += char
            previousChar = char
        # "res" can be a single whitespace. It is up to the caller method to
        # identify when this single whitespace must be kept or crunched.
        return res
# ------------------------------------------------------------------------------
