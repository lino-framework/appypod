# -*- coding: utf-8 -*-
# ~license~
# ------------------------------------------------------------------------------
import re, os.path
from collections import UserDict
from appy import utils
from appy.pod import *
from appy.pod.odf_parser import OdfEnvironment, OdfParser
from appy.pod.doc_importers import px2cm as px2cmRatio
from appy.ui.css import parseStyleAttribute, CssStyles, CssValue

# Possible states for the parser
READING = 0 # Default state
PARSING_STYLE = 1 # Parsing a style definition
PARSING_MASTER_STYLES = 2 # Parsing section "master-styles"
PARSING_PAGE_LAYOUT = 3 # Parsing a page layout

# Error-related constants ------------------------------------------------------
MAPPING_NOT_DICT = 'The styles mapping must be a dictionary or a UserDict ' \
  'instance.'
MAPPING_KEY_NOT_STRING = "The styles mapping dictionary's keys must be strings."
MAPPING_ELEM_NOT_STRING = 'The styles mapping value for key "%s" must be a ' \
  'string.'
MAPPING_ELEM_EMPTY = 'In your styles mapping, you inserted an empty key ' \
  'and/or value.'
MAPPING_WRONG_VALUE_TYPE = 'For key "%s", the value must be of type "%s".'
UNSTYLABLE_TAG = 'You can\'t associate a style to element "%s". Unstylable ' \
  'elements are: %s'
STYLE_NOT_FOUND = 'OpenDocument style "%s" was not found in your template. ' \
  'Note that the styles names ("Heading 1", "Standard"...) that appear when ' \
  'opening your template with OpenOffice, for example, are a super-set of ' \
  'the styles that are really recorded into your document. Indeed, only ' \
  'styles that are in use within your template are actually recorded into ' \
  'the document. You may consult the list of available styles ' \
  'programmatically by calling your pod renderer\'s "getStyles" method.'
HTML_PARA_ODT_TEXT = 'For XHTML element "%s", you must associate a ' \
  'paragraph-wide OpenDocument style. "%s" is a "text" style (that applies ' \
  'to only a chunk of text within a paragraph).'
HTML_TEXT_ODT_PARA = 'For XHTML element "%s", you must associate an ' \
  'OpenDocument "text" style (that applies to only a chunk of text within a ' \
  'paragraph). "%s" is a paragraph-wide style.'

# ------------------------------------------------------------------------------
class Properties:
    '''Abstract base class for table and list properties'''
    # HTML elements whose styles are defined by Property instances instead of
    # Style instances.
    elems = ('table', 'ol', 'ul')

class TableProperties(Properties):
    '''In a styles mapping, the value @key "table" must be an instance of this
       class.'''
    def __init__(self, pageWidth=None, px2cm=px2cmRatio, cellPx2cm=10.0,
                 wideAbove=495, minColumnWidth=0.07, optimalColumnWidths=False,
                 minCellPadding=0.0, cellContentStyle='podCellContent',
                 headerContentStyle='podHeaderCellContent'):
        # pod computes, in cm, the width of the master page for a pod template.
        # Table widths expressed as percentages will be based on it. But if your
        # XHTML table(s) lie(s) within a section that has a specific page style
        # with another width, specify it here (as a float value, in cm).
        self.pageWidth = pageWidth
        # Table widths expressed as pixels will use a "pixels to cm" ratio as
        # defined in appy.pod.doc_importers.px2cm. If this is wrong for you,
        # specify another ratio here. The width in cm will be computed as:
        #             (table width in pixels) / px2cm
        self.px2cm = px2cm
        # Table cell paddings may use another px / cm ratio. Indeed,
        # cellspacing="1" is converted to 0.02cm with the standard ratio, which
        # is low.
        self.cellPx2cm = cellPx2cm
        # Every table with no specified width will be "wide" (=100% width).
        # If a table width is specified in px and is above the value defined
        # here, it will be forced to 100%.
        self.wideAbove = wideAbove
        # pod ensures that every column will at least get a minimum width
        # (expressed as a percentage: a float value between 0.0 and 1.0). You
        # can change this minimum here.
        self.minColumnWidth = minColumnWidth
        # If this boolean is True, any parameter related to table and column
        # widths is ignored: we will let LibreOffice (LO) compute himself the
        # table and column widths via its algorithm "SetOptimalColumnWidths".
        # This requires LO to run in server mode and the
        # appy.pod.renderer.Renderer being launched with parameter
        #                    optimalColumnWidths="OCW_.*
        self.optimalColumnWidths = optimalColumnWidths
        # When cell padding is defined (table CSS table property
        # "border-spacing" or HTML table attribute "cellspacing"), a minimum
        # value can be defined here, as a float value (cm). If no padding is
        # defined, the default one from pod default style "podCell" is used and
        # is 0.1cm.
        self.minCellPadding = minCellPadding
        # The styles to use for cell and cell header content. The default values
        # correspond to styles defined in styles.xmlt.
        self.cellContentStyle = cellContentStyle
        self.headerContentStyle = headerContentStyle

    def getWidth(self, attrs, original=False):
        '''Return the table width as a appy.shared.css.CssValue instance.
           p_attrs is a CssStyles instance containing parsed table attributes.
           If p_original is False, self.wideAbove is not taken into account.'''
        # Widths being "0" are simply ignored
        if not hasattr(attrs, 'width') or (attrs.width.value == 0):
            return CssValue('width', '100%')
        res = attrs.width
        if original: return res
        if (self.wideAbove != None) and (res.unit == 'px') and \
           (res.value > self.wideAbove):
            return CssValue('width', '100%')
        return res

    def getCellPadding(self, value):
        '''CSS "border-spacing" is defined in p_value. This method gets the
           final value, taking into account self.minCellPadding.'''
        unit = value.unit
        # We must get p_value in cm
        if unit == 'cm':
            val = value.value
        elif unit == 'px':
            val = float(value.value) / self.cellPx2cm
        else:
            # We do not support this
            val = self.minCellPadding
        # Return the max between the p_value and the minimum value
        return max(val, self.minCellPadding)

    @classmethod
    def initStylesMapping(klass, stylesMapping, optimalColumnWidths):
        '''If column widths optimization must be enabled, we must inject some
           entries in p_stylesMapping.'''
        # If our regular expression is in use, we provide 2 CSS classes for
        # "flagging", in XHTML chunks, tables whose columns will be optimized or
        # not.
        if optimalColumnWidths == klass.ocwRex:
            stylesMapping.update(klass.ocwStylesMapping)
        elif optimalColumnWidths == True:
            # All tables (including those converted by html2odt) must be
            # optimized.
            if 'table' in stylesMapping:
                stylesMapping['table'].optimalColumnWidths = True
            else:
                stylesMapping['table'] = klass.ocw

    @classmethod
    def init(klass):
        '''Sets, on this p_klass, some static attributes related to column
           width optimization.'''
        # The regular expression to give to converter.py for it to recognize
        # tables whose column widths must be optimized.
        klass.ocwRex = 'OCW_.*'
        # The default TableProperties instance
        klass.default = TableProperties()
        # A TableProperties instance with OCW enabled
        klass.ocw = TableProperties(optimalColumnWidths=True)
        # Styles mapping to use for enabling OCW
        klass.ocwStylesMapping = {
          'table[table-layout=auto]': TableProperties.ocw,
          'table[table-layout=fixed]': TableProperties.default }
TableProperties.init()

class ListProperties(Properties):
    '''Base abstract class for defining properties of a XHTML list'''
    def __init__(self, levels, formats, delta, space, paraStyle):
        # The number of indentation levels supported
        self.levels = levels
        # The list of formats for bullets/numbers
        self.formats = formats
        # The number of inches to increment at each level (as a float)
        self.delta = delta
        # The space, in inches (as a float), between the bullet/number and the
        # text.
        self.space = space
        # A specific style to apply to the inner paragraphs
        self.paraStyle = paraStyle
        # The number of levels can > or < to the number of formats. In those
        # cases, formats will be applied partially or cyclically to levels.

    def dumpStyle(self, name, ns):
        '''Returns the OpenDocument style definition corresponding to this
           instance.'''
        nsText = ns['text']
        nsStyle = ns['style']
        res = []
        spaceBefore = 0
        space = utils.formatNumber(self.space, sep='.',removeTrailingZeros=True)
        for i in range(self.levels):
            spaceBefore += self.delta
            sb = utils.formatNumber(spaceBefore, sep='.',
                                    removeTrailingZeros=True)
            level = u'  <%s:list-level-style-%s %s:level="%d" ' \
              '%s:style-name="%s" %s>\n    <%s:list-level-properties ' \
              '%s:space-before="%sin" %s:min-label-width="%sin"/>%s' \
              '\n  </%s:list-level-style-%s>' % (nsText, self.type, nsText, i+1,
              nsText, self.textStyle, self.getLevelAttributes(i,nsText,nsStyle),
              nsStyle, nsText, sb, nsText, space,
              self.getTextProperties(i, nsText, nsStyle), nsText, self.type)
            res.append(level)
        res = u'<%s:list-style %s:name="%s">\n%s\n</%s:list-style>' % \
               (nsText, nsStyle, name, u'\n'.join(res), nsText)
        return res.encode('utf-8')

class BulletedProperties(ListProperties):
    '''In a styles mapping, the value @key "ul" must be an instance of this
       class.'''
    type = 'bullet'
    defaultFormats = ('•', '◦', '▪')
    textStyle = 'podBulletStyle'
    def __init__(self, levels=4, formats=defaultFormats,
                 delta=0.25, space=0.25, paraStyle=None):
        ListProperties.__init__(self, levels, formats, delta, space, paraStyle)

    def getLevelAttributes(self, i, nsText, nsStyle):
        '''Dumps bullet-specific attributes for level p_i'''
        # Get the bullet to render at this level
        return '%s:bullet-char="%s"' % \
               (nsText, utils.getElementAt(self.formats, i))

    def getTextProperties(self, i, nsText, nsStyle):
        '''Gets the text properties at level p_i.'''
        return '\n    <%s:text-properties %s:font-name="PodStarSymbol"/>' % \
               (nsStyle, nsStyle)

class NumberedProperties(ListProperties):
    '''In a styles mapping, the value @key "ol" must be an instance of this
       class.'''
    type = 'number'
    defaultFormats = ('1',)
    defaultSuffixes = ('.',)
    textStyle = 'podNumberStyle'
    def __init__(self, levels=4, formats=defaultFormats,
              suffixes=defaultSuffixes, delta=0.25, space=0.25, paraStyle=None):
        ListProperties.__init__(self, levels, formats, delta, space, paraStyle)
        # The list of suffixes
        self.suffixes = suffixes

    def getLevelAttributes(self, i, nsText, nsStyle):
        '''Dumps number-specific attributes for level p_i'''
        # Get the number type and suffix to render at this level
        return '%s:num-suffix="%s" %s:num-format="%s"' % \
               (nsStyle, utils.getElementAt(self.suffixes, i),
                nsStyle, utils.getElementAt(self.formats, i))

    def getTextProperties(self, i, nsText, nsStyle): return ''

# ------------------------------------------------------------------------------
class Style:
    '''Represents an ODF style. Either parsed from an ODF file or used for
       dumping a style into an ODF file.'''
    numberRex = re.compile('(\d+)(.*)')

    def __init__(self, name, family, defaults=None, outlineLevel=None):
        self.name = name
        self.family = family # May be 'paragraph', etc.
        self.displayName = name
        self.styleClass = None # May be 'text', 'list', etc.
        self.fontSize = None
        self.fontSizeUnit = None # May be pt, %, ...
        # Were the styles lies within styles and substyles hierarchy
        self.outlineLevel = outlineLevel
        # Namespace for the ODF "style-name" attribute corresponding to this
        # style
        self.styleNameNs = (family == 'table-cell') and 'table' or 'text'
        # Default ODF attributes for this style
        self.defaults = defaults
        # For some unknown reason, ODF parent-child links don't work
        self.inheritWorks = family != 'table-cell'

    def setFontSize(self, fontSize):
        rexRes = self.numberRex.search(fontSize)
        self.fontSize = int(rexRes.group(1))
        self.fontSizeUnit = rexRes.group(2)

    def __repr__(self):
        res = '<Style %s|family %s' % (self.name, self.family)
        if self.displayName != None: res += '|displayName "%s"'%self.displayName
        if self.styleClass != None: res += '|class %s' % self.styleClass
        if self.fontSize != None:
            res += '|fontSize %d%s' % (self.fontSize, self.fontSizeUnit)
        if self.outlineLevel != None: res += '|level %s' % self.outlineLevel
        return ('%s>' % res).encode('utf-8')

    def getOdfAttributes(self, attrs=None, withName=True, withDefaults=False,
                         exclude=None):
        '''Gets the ODF attributes corresponding to this style. p_attrs, when
           given, are attributes of an XHTML tag.'''
        # Style name
        res = ''
        if withName:
            res = ' %s:style-name="%s"' % (self.styleNameNs, self.name)
        # Outline level when relevant
        if self.outlineLevel != None:
            res += ' text:outline-level="%d"' % self.outlineLevel
        # Colspan and rowspan when relevant
        if attrs and ('colspan' in attrs):
            res += ' table:number-columns-spanned="%s"' % attrs['colspan']
        if attrs and ('rowspan' in attrs):
            res += ' table:number-rows-spanned="%s"' % attrs['rowspan']
        # Additional parameters as stored in self.defaults
        if withDefaults and self.defaults:
            for name, value in self.defaults.items():
                if exclude and (name in exclude): continue
                res += ' %s="%s"' % (name, value)
        return res

    def getOdfParentAttributes(self, childAttrs=None):
        '''If style inheritance works, this method simply returns the attribute
           "style:parent-style-name" allowing to define some style as child from
           this one. If inheritance does not work (like for "table-cell"
           styles), this method returns, in extenso, the parent ODF properties,
           so they will be entirely copied into the child style.'''
        if self.inheritWorks:
            return ' style:parent-style-name="%s"' % self.name
        else:
            return self.getOdfAttributes(withName=False, withDefaults=True,
                                         exclude=childAttrs)

# Default ODF styles for XHTML elements. They correspond to styles from
# content.xmlt or styles.xmlt. Default cell and header attributes are repeated
# here because (a) for an unknown reason, they are not inherited from default
# styles defined in styles.xmlt when generating a child sub-style, and (b) they
# slightly differ. For example, default vertical alignment for XHTML is not the
# same as for ODF. "podCell" here will use the XHTML standard, while "podCell"
# in content.xmlt will use the ODF standard.
DEFAULT_CELL_PARAMS = {'fo:padding':'0.1cm',
  'fo:border':'0.018cm solid #000000', 'style:vertical-align': 'middle'}
DEFAULT_HEADER_PARAMS = DEFAULT_CELL_PARAMS.copy()
DEFAULT_HEADER_PARAMS['fo:background-color'] = '#e6e6e6'
DEFAULT_STYLES = {
  'table': TableProperties.default,
  'td': Style('podCell', 'table-cell', DEFAULT_CELL_PARAMS),
  'th': Style('podHeader', 'table-cell', DEFAULT_HEADER_PARAMS),
}
for i in range(1,7):
    DEFAULT_STYLES['h%d'%i] = Style('podH%d'%i, 'paragraph', outlineLevel=i)

# ------------------------------------------------------------------------------
class PageLayout:
    '''Represents a kind of page-level style.'''
    def __init__(self, name):
        self.name = name

    def getFloat(self, value):
        '''Extract the float value from the string p_value'''
        res = ''
        for c in value:
            if c.isdigit() or (c == '.'):
                res += c
        return float(res)

    def setProperties(self, e, attrs):
        '''Sets properties of this page layout based on parsed p_attrs from tag
           "page-layout-properties".'''
        # Compute page dimensions. May be missing for ods files.
        widthAttr = e.tags['page-width']
        if widthAttr not in attrs: return
        self.width = self.getFloat(attrs[widthAttr])
        heightAttr = e.tags['page-height']
        if heightAttr not in attrs: return
        self.height = self.getFloat(attrs[heightAttr])
        # Compute margins
        marginAttr = e.tags['margin']
        if marginAttr not in attrs:
            defaultMargin = '2cm'
        else:
            defaultMargin = attrs[marginAttr]
        for margin in ('top', 'right', 'bottom', 'left'):
            key = e.tags['margin-%s' % margin]
            value = (key in attrs) and attrs[key] or defaultMargin
            marginAttr = 'margin%s' % margin.capitalize()
            setattr(self, marginAttr, self.getFloat(value))

    def getWidth(self, substractMargins=True):
        '''Return, as a float, the page width in cm'''
        res = self.width
        if substractMargins: res -= self.marginLeft + self.marginRight
        return res

    def __repr__(self): return '<Page layout %s>' % self.name

# ------------------------------------------------------------------------------
class Styles(UserDict):
    def getParagraphStyleAtLevel(self, level):
        '''Tries to find a style which has level p_level. Returns None if no
           such style exists.'''
        for style in self.values():
            if (style.family == 'paragraph') and (style.outlineLevel == level):
                return style

    def getStyle(self, displayName):
        '''Gets the style that has this p_displayName. Returns None if not
           found.'''
        res = None
        for style in self.values():
            if style.displayName == displayName:
                res = style
                break
        return res

    def getStyles(self, stylesType='all'):
        '''Returns a list of all the styles of the given p_stylesType'''
        res = []
        if stylesType == 'all':
            res = self.values()
        else:
            for style in self.values():
                if (style.family == stylesType) and style.displayName:
                    res.append(style)
        return res

# ------------------------------------------------------------------------------
class StylesEnvironment(OdfEnvironment):
    def __init__(self):
        OdfEnvironment.__init__(self)
        # Namespace definitions are not already encountered
        self.gotNamespaces = False
        # Names of some tags, that we will compute after namespace propagation
        self.tags = None
        self.styles = Styles()
        self.currentStyle = None # The currently parsed style definition
        # The found page layouts, keyed by their name
        self.pageLayouts = {}
        self.currentPageLayout = None # The currently parsed page layout
        # The name of the page layout defined for the whole document
        self.masterLayoutName = None
        self.state = READING
        # Names of the page styles
        self.pageStyleNames = []

    def onStartElement(self):
        ns = self.namespaces
        if not self.gotNamespaces:
            # We suppose that all the interesting (from the POD point of view)
            # XML namespace definitions are defined at the root XML element.
            # Here we propagate them in XML element definitions that we use
            # throughout POD.
            self.gotNamespaces = True
            self.propagateNamespaces()
        return ns

    def propagateNamespaces(self):
        '''Propagates the namespaces in all XML element definitions that are
           used throughout POD.'''
        ns = self.namespaces
        # Create a table of names of used tags and attributes (precomputed,
        # including namespace, for performance).
        style = ns[self.NS_STYLE]
        fo = ns[self.NS_FO]
        office = ns[self.NS_OFFICE]
        tags = {
          'style': '%s:style' % style,
          'name': '%s:name' % style,
          'family': '%s:family' % style,
          'class': '%s:class' % style,
          'display-name': '%s:display-name' % style,
          'default-outline-level': '%s:default-outline-level' % style,
          'text-properties': '%s:text-properties' % style,
          'font-size': '%s:font-size' % fo,
          'master-styles': '%s:master-styles' % office,
          'master-page': '%s:master-page' % style,
          'page-layout-name': '%s:page-layout-name' % style,
          'page-layout': '%s:page-layout' % style,
          'page-layout-properties': '%s:page-layout-properties' % style,
          'page-width': '%s:page-width' % fo,
          'page-height': '%s:page-height' % fo,
          'margin': '%s:margin' % fo,
          'margin-top': '%s:margin-top' % fo,
          'margin-right': '%s:margin-right' % fo,
          'margin-bottom': '%s:margin-bottom' % fo,
          'margin-left': '%s:margin-left' % fo,
        }
        self.tags = tags

# ------------------------------------------------------------------------------
class StylesParser(OdfParser):
    def __init__(self, env, caller):
        OdfParser.__init__(self, env, caller)

    def endDocument(self):
        e = OdfParser.endDocument(self)
        self.caller.styles = e.styles
        self.caller.pageLayout = e.pageLayouts[e.masterLayoutName]

    def startElement(self, elem, attrs):
        e = OdfParser.startElement(self, elem, attrs)
        ns = e.onStartElement()
        if elem == e.tags['style']:
            e.state = PARSING_STYLE
            # Create the style
            style = Style(name=attrs[e.tags['name']],
                          family=attrs[e.tags['family']])
            classAttr = e.tags['class']
            if classAttr in attrs: style.styleClass = attrs[classAttr]
            dnAttr = e.tags['display-name']
            if dnAttr in attrs: style.displayName = attrs[dnAttr]
            dolAttr = e.tags['default-outline-level']
            if dolAttr in attrs and attrs[dolAttr].strip():
                style.outlineLevel = int(attrs[dolAttr])
            # Record this style in the environment
            e.styles[style.name] = style
            e.currentStyle = style

        elif elem == e.tags['page-layout']:
            e.state = PARSING_PAGE_LAYOUT
            pageLayout = PageLayout(attrs[e.tags['name']])
            # Record this page layout in the environment
            e.pageLayouts[pageLayout.name] = pageLayout
            e.currentPageLayout = pageLayout

        elif elem == e.tags['master-styles']:
            e.state = PARSING_MASTER_STYLES

        elif e.state == PARSING_STYLE:
            # Find properties within this style definition
            if elem == e.tags['text-properties']:
                fontSizeAttr = e.tags['font-size']
                if fontSizeAttr in attrs:
                    e.currentStyle.setFontSize(attrs[fontSizeAttr])

        elif e.state == PARSING_PAGE_LAYOUT:
            # Find properties within this page layout definition
            if elem == e.tags['page-layout-properties']:
                e.currentPageLayout.setProperties(e, attrs)

        elif e.state == PARSING_MASTER_STYLES:
            # I am parsing section "master-styles"
            if elem == e.tags['master-page']:
                plnAttr = e.tags['page-layout-name']
                if plnAttr in attrs:
                    e.masterLayoutName = attrs[plnAttr]
                e.pageStyleNames.append(attrs['style:name'])

    def endElement(self, elem):
        e = OdfParser.endElement(self, elem)
        if elem == e.tags['style']:
            e.state = READING
            e.currentStyle = None
        elif elem == e.tags['page-layout']:
            e.state = READING
            e.currentPageLayout = None
        elif elem == e.tags['master-styles']:
            e.state = READING

# ------------------------------------------------------------------------------
class Css2odf:
    '''Allows to get a OpenDocument attribute from a CSS attribute'''
    # Map CSS attribute names to ODF attribute names. CSS attributes names
    # have lost their inner dashes (margin-left => marginleft) because they are
    # used as Python attributes on CssStyles instances.
    namesMap = {
      'marginleft': 'fo:margin-left', 'marginright': 'fo:margin-right',
      'margintop': 'fo:margin-top', 'marginbottom': 'fo:margin-bottom',
      'textalign': 'fo:text-align', 'textindent': 'fo:text-indent',
      'backgroundcolor': 'fo:background-color', 'color': 'fo:color',
      'fontsize': 'fo:font-size', 'fontvariant': 'fo:font-variant',
      'fontweight': 'fo:font-weight', 'fontstyle': 'fo:font-style',
      'border': 'fo:border', 'borderspacing': 'fo:padding',
      # Vertical-align map to different ODF attributes depending on its use:
      # aligning table cell content or text (sub or sup).
      'verticalalign': {
        'top': ('style:vertical-align', 'top'),
        'middle': ('style:vertical-align', 'middle'),
        'bottom': ('style:vertical-align', 'bottom'),
        'super': ('style:text-position', 'super 58%'),
        'sub': ('style:text-position', 'sub 58%'),
      },
      # CSS text-decoration corresponds to a different ODF attribute, depending
      # on its value.
      'textdecoration': {
        'underline': ('style:text-underline-style', 'solid'),
        'line-through': ('style:text-line-through-style', 'solid'),
        'overline': ('style:text-overline-style', 'solid')},
      # Idem for the following attributes
      'pagebreakafter': {'always': ('fo:break-after', 'page')},
      'pagebreakbefore': {'always': ('fo:break-before', 'page')},
    }
    # Map XHTML CSS values to values of their corresponding ODF attributes when
    # they are different.
    valuesMap = {
      'textalign': {'left': 'start', 'start': 'start', 'center': 'center',
                    'right': 'end', 'end': 'end', 'justify': 'justify',
                    'match-parent': 'start'},
      'border': {'0': 'none'},
      'fontsize': {'medium': '100%', 'xx-small': '55%', 'x-small': '70%',
                   'small': '85%', 'large': '115%', 'x-large': '130%',
                   'xx-large': '145%', 'smaller': '85%', 'larger': '115%',
                   'initial': '100%', 'inherit': '100%'}
    }
    # CSS properties representing combinations of CSS properties
    combined = ('background', 'border')

    def getOdf(self, name, value, sub=None):
        '''Get the ODF attribute, as a tuple (name, value), corresponding to
           CSS attribute p_name having some p_value (and the specific
           p_sub-value if p_value is multiple).'''
        # Is there an ODF attribute corresponding to this CSS attribute ?
        odfName = self.namesMap.get(name)
        if not odfName: return
        val = sub or value.value
        # Is the ODF attribute different according to CSS value ?
        if isinstance(odfName, dict):
            # "val" can be absent from the list of values that must be mapped to
            # an ODF style (ie, "none").
            return odfName.get(val)
        # Standardize the attribute for use within an ODF document
        unit = value.unit or ''
        if unit == 'px': # Convert pixels to cm
            val = val / px2cmRatio
            val = utils.formatNumber(val, sep='.', precision=3)
            unit = 'cm'
        # Convert the value to the ODF equivalent when needed
        if not unit and (name in self.valuesMap):
            # The value in valuesMap can add a unit
            val = self.valuesMap[name][val]
        return odfName, '%s%s' % (val, unit)

    def isCombined(self, name, value):
        '''Returns True if the CSS property p_name is a combined CSS property,
           ie, a property representing a set of CSS properties.'''
        return (name in self.combined) and (' ' in value.value)

# ------------------------------------------------------------------------------
class StylesGenerator:
    '''Analyse, for a given XHTML tag, its attributes (including CSS attributes
       within the "style" attribute) and possibly generate a custom style.'''
    prefix = 'CS' # Stands for *C*ustom *S*tyle
    # Map HTML tags to ODF style families. Any tag not present in this list is
    # supposed to have family "text".
    styleFamilies = {'p': 'paragraph', 'div': 'paragraph', 'td': 'table-cell',
                     'th': 'table-cell'}
    # For paragraph styles, there are 2 kinds of properties: paragraph and text
    # properties. Any property not being listed as a text property below will be
    # considered as a paragraph property.
    textProperties = {
      'fo:color': True, 'fo:font-size': True, 'fo:font-variant': True,
      'fo:font-weight': True, 'fo:font-style': True,
      'style:text-underline-style': True,
      # For this one, this is more subtle: the property will be considered a
      # text property only if the HTML tag is not of type "para" nor "list".
      'fo:background-color': {'para': False, 'list': False, 0: True},
      'style:text-line-through-style': True, 'style:text-overline-style': True,
      'style:text-position': True}
    # Properties applying to table cells and that are not transferred to inner
    # paragraphs.    
    cellProperties = ('fo:padding', 'fo:border', 'fo:background-color',
                      'style:vertical-align')
    # Default parent styles to apply for generated styles. Those styles are not
    # listed among DEFAULT_STYLES because, when there is no custom style to
    # generate, they must not be specified, it is implicit.
    standardStyle = Style('Standard', 'paragraph')
    defaultParents = {'p': standardStyle, 'div': standardStyle}

    def __init__(self, stylesManager):
        # The number attributed to the last generated style
        self.last = 0
        # The names of the styles that were already generated, keyed by some
        # hash value.
        self.generated = {}
        self.stylesManager = stylesManager
        # Allows to convert CSS to ODF attributes
        self.css2odf = Css2odf()

    def addStyle(self, style, target):
        '''Adds the style definition to the renderer's dynamic styles.
           Target is "styles" (styles.xml) or "content" (content.xml).'''
        dynamicStyles = self.stylesManager.renderer.dynamicStyles[target]
        dynamicStyles.append(style.encode('utf-8'))

    def getStyleHash(self, xhtmlElem, odfAttrs, baseStyle):
        '''Returns a string uniquely representing the given set of ODF
           attributes p_odfAttrs that will be used to create/retrieve a style to
           be applied to the ODF element corresponding to p_xhtmlElem.'''
        odfAttrs.sort()
        attrs = self.flattenOdfAttributes(odfAttrs, forHash=True)
        r = '%s%s' % (xhtmlElem.elem, ''.join(attrs))
        if baseStyle:
            # The base style must be part of the hash; else, the same set of
            # attributes on the same tag, but with 2 different base styles,
            # would be considered equal.
            r += '*%s' % baseStyle.name
        return r

    def getStyleFamily(self, xhtmlElem):
        '''Returns the ODF family style corresponding to p_xhtmlElem'''
        return self.styleFamilies.get(xhtmlElem.elem, 'text')

    def getStyleName(self, xhtmlElem, odfAttrs, baseStyle):
        '''Return the ODF style name for the style that will be applied to ODF
           element corresponding to the given XHTML element (p_xhtmlElem). We
           have already computed attributes for the ODF style in p_odfAttrs. If
           a style has already been generated by this styles generator, for this
           tag and with this combination of attributes, we simply return its
           name. Else, we note that we must generate a new style; we compute a
           new (incremental) name for it and we return this name.

           More precisely, this method returns a tuple (createNew, styleName):
            - "createNew" is a boolean indicating if a new style must be
                          generated;
            - "styleName" is the style name.'''
        # If the style hash corresponds to an existing style, simply return
        # its name
        hash = self.getStyleHash(xhtmlElem, odfAttrs, baseStyle)
        if hash in self.generated:
            return False, self.generated[hash]
        # We must generate a new style
        self.last += 1
        res = '%s%d' % (self.prefix, self.last)
        self.generated[hash] = res
        return True, res

    def flattenOdfAttributes(self, odfAttrs, forHash=False):
        '''Produce a string from the list of (name, value) pairs in
           p_odfAttrs.'''
        fmt = forHash and '%s%s' or '%s="%s"'
        return [fmt % (name, value) for name, value in odfAttrs]

    def isTextProperty(self, xhtmlElem, name):
        '''Is property p_name a text property ?'''
        if name in self.textProperties:
            r = self.textProperties[name]
            if isinstance(r, dict):
                # It depends on p_xhtmlElem
                if xhtmlElem.elemType in r:
                    r = r[xhtmlElem.elemType]
                else:
                    r = r[0]
        else:
            r = False
        return r

    # This method generates most of the tags. If no specific method is found for
    # some tag, this method is used.
    def get_any(self, xhtmlElem, odfAttrs, baseStyle):
        '''Generates a paragraph style'''
        createNew, styleName = self.getStyleName(xhtmlElem, odfAttrs, baseStyle)
        if not createNew: return styleName
        # Generate a new style. Is there a parent style ?
        baseStyle = baseStyle or self.defaultParents.get(xhtmlElem.elem)
        names = [name for name, value in odfAttrs]
        parent = baseStyle and baseStyle.getOdfParentAttributes(names) or ''
        # Among p_odfAttrs, distinguish "paragraph" and "text" properties
        paraAttrs = []
        textAttrs = []
        for name, value in odfAttrs:
            if self.isTextProperty(xhtmlElem, name):
                textAttrs.append((name, value))
            else:
                paraAttrs.append((name, value))
        paraProps = textProps = ''
        if paraAttrs:
            paraProps = '<style:paragraph-properties %s/>' % \
                        ' '.join(self.flattenOdfAttributes(paraAttrs))
        if textAttrs:
            textProps = '<style:text-properties %s/>' % \
                        ' '.join(self.flattenOdfAttributes(textAttrs))
        family = self.getStyleFamily(xhtmlElem)
        style = '<style:style style:name="%s" style:family="%s"%s>%s%s' \
                '</style:style>' % (styleName,family,parent,textProps,paraProps)
        # I could have added this style in content.xml. But in some cases it
        # does not work properly. For example, a percentage value for attribute
        # "fo-font-size" will be ignored if the style is dumped in content.xml.
        self.addStyle(style, 'styles')
        return styleName

    def get_td(self, xhtmlElem, odfAttrs, baseStyle):
        '''Generates a table cell style'''
        # If there is a "text-related" property among p_odfAttrs, we must
        # generate a style for the inner-paragraph within this cell. Indeed, in
        # XHTML, this kind of information can be defined at the "td" tag level,
        # while, in ODF, it must be defined at the inner-paragraph level. A cell
        # style will only be generated if there is a "cell-related" property
        # among p_odfAttrs.
        paraAttrs = []
        cellAttrs = []
        for name, value in odfAttrs:
            if name == 'fo:text-align': paraAttrs.append((name, value))
            elif name in self.cellProperties: cellAttrs.append((name, value))
            elif name in self.textProperties: paraAttrs.append((name, value))
        # Generate a paragraph style to be applied on this td's inner paragraph
        if paraAttrs:
            xhtmlElem.innerStyle = self.get_any(xhtmlElem.protos['p'],paraAttrs,
                                       Style(xhtmlElem.innerStyle, 'paragraph'))
        # Generate a cell style
        if cellAttrs:
            # Generate (or retrieve) a table-cell style, based on the standard
            # Appy cell style.
            createNew, styleName = self.getStyleName(xhtmlElem,
                                                     cellAttrs, baseStyle)
            if not createNew: return styleName
            # Generate a new style. For table cells there is always a baseStyle.
            names = [name for name, value in cellAttrs]
            style = '<style:style style:name="%s" style:family="%s">' \
              '<style:table-cell-properties%s %s/></style:style>' % \
              (styleName, self.getStyleFamily(xhtmlElem),
               baseStyle.getOdfParentAttributes(names),
               ' '.join(self.flattenOdfAttributes(cellAttrs)))
            self.addStyle(style, 'content')
            return styleName
    get_th = get_td

    def get(self, xhtmlElem, baseStyle):
        '''Generates a custom style when relevant. p_baseStyle is a Style
           instance that could have been found from a style mapping. In this
           case, the generated style will get it as parent style.'''
        # If no CSS styles are defined, no custom style can be defined
        cssStyles = xhtmlElem.cssStyles
        if not cssStyles: return baseStyle
        # If the elem is a table or list, return the base style (None or a
        # "Properties" instance). The caller will generate the style himself.
        if xhtmlElem.elem in Properties.elems: return baseStyle
        # Analyse CSS styles
        elem = xhtmlElem.elem
        # Collect ODF attributes corresponding to CSS attributes
        odfAttrs = []
        for name, value in cssStyles.get().items():
            if name == 'classes': continue
            if self.css2odf.isCombined(name, value):
                # Combined values are currently ignored
                pass
            elif value.isMultiple():
                for v in value.value.split(' '):
                    odf = self.css2odf.getOdf(name, value, v)
                    if odf: odfAttrs.append(odf)
            else:
                odf = self.css2odf.getOdf(name, value)
                if odf: odfAttrs.append(odf)
        if not odfAttrs: return baseStyle
        # I have attributes to apply. Call the corresponding "get_[tag]" method
        # for generating a custom style, or "get_any" if here is no specific
        # method for this tag.
        method = 'get_%s' % elem
        if not hasattr(self, method): method = 'get_any'
        styleName = getattr(self, method)(xhtmlElem, odfAttrs, baseStyle)
        # "styleName" may be empty. For example, it may not be necessary to
        # generate a custom style for a "td", although we must generate, from
        # its attrs, a custom style for its inner-paragraph.
        if not styleName: return baseStyle
        return Style(styleName, self.getStyleFamily(xhtmlElem))

# ------------------------------------------------------------------------------
class StylesManager:
    '''Reads the paragraph styles from styles.xml within an ODT file, and
       updates styles.xml with some predefined POD styles.'''
    podSpecificStyles = {
      'ParaKWN': Style('ParaKWN', 'paragraph'),
      # This style is common to bullet and number items. Behind the scenes,
      # there are 2 concrete ODT styles: podBulletItemKeepWithNext and
      # podNumberItemKeepWithNext. pod chooses the right one.
      'podItemKeepWithNext': Style('podItemKeepWithNext', 'paragraph'),
    }
    # Valid value types for some keys within style mappings
    mappingValueTypes = {'h*': int, 'table': TableProperties,
                         'ol': NumberedProperties, 'ul': BulletedProperties}
    def __init__(self, renderer):
        self.renderer = renderer
        self.stylesString = renderer.stylesXml
        # The collected styles, as a list of Style instances
        self.styles = None
        # The main page layout, as a PageLayout instance
        self.pageLayout = None
        # Global styles mapping
        self.stylesMapping = None
        self.stylesParser = StylesParser(StylesEnvironment(), self)
        self.stylesParser.parse(self.stylesString)
        # Now self.styles contains the styles.
        # Text styles from self.styles
        self.textStyles = self.styles.getStyles('text')
        # Paragraph styles from self.styles
        self.paragraphStyles = self.styles.getStyles('paragraph')
        # The custom styles generator
        self.stylesGenerator = StylesGenerator(self)

    def checkStylesAdequation(self, htmlStyle, odtStyle):
        '''Checks that p_odtStyle may be used for style p_htmlStyle'''
        if (htmlStyle in XHTML_PARA_TAGS) and (odtStyle in self.textStyles):
            raise PodError(
                HTML_PARA_ODT_TEXT % (htmlStyle, odtStyle.displayName))
        if (htmlStyle in XHTML_INNER_TAGS) and \
            (odtStyle in self.paragraphStyles):
            raise PodError(HTML_TEXT_ODT_PARA % (
                htmlStyle, odtStyle.displayName))

    def addStyleEntry(self, stylesMapping, key, value, cssAttrs):
        '''Adds, in dict p_stylesMapping (the output of m_checkStylesMapping
           below), a p_key:p_value entry.'''
        alreadyIn = key in stylesMapping
        if cssAttrs or alreadyIn:
            # I must create a complex structure for this mapping
            if not alreadyIn:
                stylesMapping[key] = [(cssAttrs, value)]
            else:
                val = stylesMapping[key]
                if not isinstance(val, list):
                    stylesMapping[key] = [(cssAttrs, value), (None, val)]
                else:
                    val.insert(0, (cssAttrs, value))
        else:
            stylesMapping[key] = value

    def checkStylesMapping(self, stylesMapping):
        '''Checks that the given p_stylesMapping is correct, and returns the
           internal representation of it. p_stylesMapping is a dict where:
           * every key can be:
             (1) the name of a XHTML 'paragraph-like' tag (p, h1, h2...) or
                 "para", representing "p", "div" or "blokquote";
             (2) the name of a XHTML 'text-like' tag (span, b, i, em...);
             (3) the name of a CSS class;
             (4) string 'h*';
             (5) 'table';
             (6) 'ol' or 'ul'.
           * every value must be:
             (a) if the key is (1), (2) or (3), value must be the display name
                 of an ODT style;
             (b) if the key is (4), value must be an integer indicating how to
                 map the outline level of outlined styles (ie, for mapping XHTML
                 tag "h1" to the OD style with outline-level=2, value must be
                 integer "1". In that case, h2 will be mapped to the ODT style
                 with outline-level=3, etc.). Note that this value can also be
                 negative;
             (c) if key is "table", the value must be a TableProperties instance
                 (this class is defined hereabove);
             (d) if key is "ol", the value must be an instance of the
                 hereabove-defined NumberedProperties class; if key is "ul", the
                 value must be an instance of the hereabove-defined
                 BulletedProperties class.
           * Some precision now about about keys. If key is (1) or (2),
             parameters can be given between square brackets. Every such
             parameter represents a CSS attribute and its value. For example, a
             key can be:
                             p[text-align=center,color=blue]

             This feature allows to map XHTML tags having different CSS
             attributes to different ODT styles.

           The method returns a dict which is the internal representation of
           the styles mapping:
           * every key can be:
             (I) the name of a XHTML tag, corresponding to (1), (2), (5) or (6)
                 whose potential parameters have been removed;
             (II) the name of a CSS class (=(3))
             (III) string 'h*' (=(4))
           * every value can be:
             (i) a Style instance that was found from the specified ODT style
                 display name in p_stylesMapping, if key is (I) and if only one
                 non-parameterized XHTML tag was defined in p_stylesMapping;
             (ii) a list of the form [ (params, Style), (params, Style),...]
                  if key is (I) and if one or more parameterized (or not) XHTML
                  tags representing the same tag were found in p_stylesMapping.
                  params, which can be None, is a dict whose pairs are of the
                  form (cssAttribute, cssValue).
             (iii) an integer value (=(b));
             (iv) a [x]Properties instance if cases (5) or (6).
        '''
        res = {}
        if not isinstance(stylesMapping, dict) and \
           not isinstance(stylesMapping, UserDict):
            raise PodError(MAPPING_NOT_DICT)
        for xhtmlStyleName, odtStyleName in stylesMapping.items():
            if not isinstance(xhtmlStyleName, basestring):
                raise PodError(MAPPING_KEY_NOT_STRING)
            # Separate CSS attributes if any
            cssAttrs = None
            if '[' in xhtmlStyleName:
                xhtmlStyleName, attrs = xhtmlStyleName.split('[')
                xhtmlStyleName = xhtmlStyleName.strip()
                attrs = attrs.strip()[:-1].split(',')
                cssAttrs = {}
                for attr in attrs:
                    name, value = attr.split('=')
                    cssAttrs[name.strip()] = value.strip()
            # Using CSS attrs is only allowed in the open source version
            if cssAttrs and utils.commercial: raise utils.CommercialError()
            # Continue checks
            if xhtmlStyleName in StylesManager.mappingValueTypes:
                # Using these keys is only granted to open source users
                if utils.commercial: raise utils.CommercialError()
                vType = StylesManager.mappingValueTypes[xhtmlStyleName]
                if not isinstance(odtStyleName, vType):
                    raise PodError(MAPPING_WRONG_VALUE_TYPE % \
                                   (xhtmlStyleName, vType.__name__))
            else:
                if not isinstance(odtStyleName, basestring):
                    raise PodError(MAPPING_ELEM_NOT_STRING % xhtmlStyleName)
                if not xhtmlStyleName or not odtStyleName:
                    raise PodError(MAPPING_ELEM_EMPTY)
            if xhtmlStyleName in XHTML_UNSTYLABLE_TAGS:
                raise PodError(UNSTYLABLE_TAG % (xhtmlStyleName,
                                                 XHTML_UNSTYLABLE_TAGS))
            # Add the entry in the result
            if xhtmlStyleName not in StylesManager.mappingValueTypes:
                odtStyle = self.styles.getStyle(odtStyleName)
                if not odtStyle:
                    if odtStyleName in self.podSpecificStyles:
                        odtStyle = self.podSpecificStyles[odtStyleName]
                    else:
                        raise PodError(STYLE_NOT_FOUND % odtStyleName)
                self.checkStylesAdequation(xhtmlStyleName, odtStyle)
                odtTarget = odtStyle
            else:
                # In this case (iii, iv), it is the outline level or a
                # [x]Properties instance.
                odtTarget = odtStyleName
            self.addStyleEntry(res, xhtmlStyleName, odtTarget, cssAttrs)
        return res

    def styleMatch(self, cssStyles, matchingAttrs):
        '''p_cssStyles are CSS attributes found on some HTML element.
           p_matchingAttrs is a dict of attributes corresponding to some style
           (or can be None). This method returns True if p_cssStyles contains
           the winning (name, value) pairs that match those in p_matchingAttrs.
           Note that ALL attrs in p_matchingAttrs must be present in p_attrs.'''
        if not matchingAttrs: return True
        for name, value in matchingAttrs.items():
            cssValue = cssStyles.get(name)
            if not cssValue: return
            if value != cssValue.value: return
        return True

    def getMatchingStyle(self, xhtmlElem, styles):
        '''p_styles is a value from a styles mapping as transformed by
           m_checkStylesMapping above. If it represents a list of styles
           (see case (ii) in m_checkStylesMapping), this method must return the
           relevant Style instance from this list, depending on CSS attributes
           found on p_xhtmlElem.'''
        if not isinstance(styles, list): return styles
        cssStyles = xhtmlElem.cssStyles
        if not cssStyles:
            # If I have, at the last position in p_styles, the style related to
            # no attribute at all, I return it.
            lastAttrs, lastStyle = styles[-1]
            if lastAttrs == None: return lastStyle
            else: return
        # If I am here, I have style info. Check if it corresponds to some style
        # in p_styles.
        for matchingAttrs, style in styles:
            if self.styleMatch(cssStyles, matchingAttrs):
                return style

    def getStyleFromMapping(self, stylesMapping, xhtmlElem, elem=None,
                            checkMetaElems=True):
        '''If p_stylesMapping contains a style corresponding to p_xhtmlElem, it
           returns it. This method takes care of meta-elems like "para"
           representing several elements. This method is recursive: when called
           to get a style from a meta-element, it is done via p_elem.'''
        # The first time m_getStyleFromMapping is called, p_elem i None. It
        # means that the element itself has priority over its meta-element.
        elem = elem or xhtmlElem.elem
        styles = stylesMapping.get(elem)
        if styles:
            # Is there a matching style among "styles" ?
            r = self.getMatchingStyle(xhtmlElem, styles)
            if r or not checkMetaElems:
                return r
        # Check if a style exists for p_elem's meta-tag
        meta = XHTML_META_TAGS.get(elem)
        if meta:
            return self.getStyleFromMapping(stylesMapping, xhtmlElem,
                                            elem=meta, checkMetaElems=False)

    def findStyle(self, xhtmlElem, localStylesMapping):
        '''Finds the ODT style that must be applied to XHTML p_elem (as a
           xhtml2odt:HtmlElement instance).

           The global styles mapping is in self.stylesMapping; the local styles
           mapping is in p_localStylesMapping.

           Here are the places where we will search, ordered by
           priority (highest first):
           (1) local styles mapping (CSS style in "class" attr)
           (2)         "            (HTML elem)
           (3) global styles mapping (CSS style in "class" attr)
           (4)          "            (HTML elem)
           (5) ODT style that has the same name as CSS style in "class" attr
           (6) Predefined pod-specific ODT style that has the same name as
               CSS style in "class" attr
           (7) ODT style that has the same outline level as HTML elem
           (8) a default Appy ODT style

        After this step, we have (or not) a base ODT style. In a final step we
        will analyse XHTML attributes (including CSS attributes within the
        "style" attribute) to get more elements and possibly generate, via the
        styles generator define hereabove, a custom style based on the base
        ODT style.'''
        res = None
        elem = xhtmlElem.elem
        cssStyles = xhtmlElem.cssStyles
        cssStyleName = cssStyles and cssStyles.classes or None
        # (1)
        if cssStyleName in localStylesMapping:
            res = localStylesMapping[cssStyleName]
        # (2)
        if not res:
            res = self.getStyleFromMapping(localStylesMapping, xhtmlElem)
        # (3)
        if not res and (cssStyleName in self.stylesMapping):
            res = self.stylesMapping[cssStyleName]
        # (4)
        if not res:
            res = self.getStyleFromMapping(self.stylesMapping, xhtmlElem)
        # (5)
        if not res and (cssStyleName in self.styles):
            res = self.styles[cssStyleName]
        # (6)
        if not res and (cssStyleName in self.podSpecificStyles):
            res = self.podSpecificStyles[cssStyleName]
        # (7)
        if not res and (elem in XHTML_HEADINGS):
            # Try to find a style with the correct outline level. Is there a
            # delta that must be taken into account ?
            outlineDelta = 0
            if 'h*' in localStylesMapping:
                outlineDelta += localStylesMapping['h*']
            elif 'h*' in self.stylesMapping:
                outlineDelta += self.stylesMapping['h*']
            outlineLevel = int(elem[1]) + outlineDelta
            # Normalize the outline level
            if outlineLevel < 1: outlineLevel = 1
            res = self.styles.getParagraphStyleAtLevel(outlineLevel)
        # (8)
        if res and (elem in Properties.elems) and \
           not isinstance(res, Properties):
            res = None
        if not res and (elem in DEFAULT_STYLES): res = DEFAULT_STYLES[elem]
        # Check styles adequation
        if res: self.checkStylesAdequation(elem, res)
        # Get or generate a custom style if there are specific CSS attributes
        return self.stylesGenerator.get(xhtmlElem, res)
# ------------------------------------------------------------------------------
