    # ------------------------------------------------------------------------------
import re
from appy.px import Px
from appy.model.utils import Object

# ------------------------------------------------------------------------------
class Collapsible:
    '''Represents a chunk of HTML code that can be collapsed/expanded via
       clickable icons.'''
    # Various sets of icons can be used. Each one has a CSS class in appy.css
    iconSets = {'expandCollapse': Object(expand='expand', collapse='collapse'),
                'showHide': Object(expand='show', collapse='hide'),
                'showHideInv': Object(expand='hide', collapse='show')}

    # Icon allowing to collapse/expand a chunk of HTML
    px = Px('''
     <img var="coll=collapse; icons=coll.icons"
          id=":'%s_img' % coll.id" align=":coll.align" class=":coll.css"
          onclick=":'toggleCookie(%s,%s,%s,%s,%s)' % (q(coll.id), \
                    q(coll.display), q(coll.default), \
                    q(icons.expand), q(icons.collapse))"
       src=":coll.expanded and url(icons.collapse) or url(icons.expand)"/>''')

    def __init__(self, id, request, default='collapsed', display='block',
                 icons='expandCollapse', align='left'):
        '''p_display is the value of style attribute "display" for the XHTML
           element when it must be displayed. By default it is "block"; for a
           table it must be "table", etc.'''
        self.id = id # The ID of the collapsible HTML element
        self.request = request # The request object
        self.default = default
        self.display = display
        self.align = align
        # Must the element be collapsed or expanded ?
        self.expanded = request.get(id, default) == 'expanded'
        self.style = 'display:%s' % (self.expanded and self.display or 'none')
        # The name of the CSS class depends on the set of applied icons
        self.css = icons
        self.icons = self.iconSets[icons]

# ------------------------------------------------------------------------------
class LinkTarget:
    '''Represents information about the target of an HTML "a" tag'''

    def __init__(self, klass=None, back=None, forcePopup=False):
        '''The HTML "a" tag must lead to a page for viewing or editing an
           instance of some p_klass. If this page must be opened in a popup
           (depends on attribute p_klass.popup), and if p_back is specified,
           when coming back from the popup, we will ajax-refresh a DOM node
           whose ID is specified in p_back.'''
        # The link leads to a instance of some p_klass
        self.klass = klass
        # Does the link lead to a popup ?
        if forcePopup:
            toPopup = True
        else:
            toPopup = klass and hasattr(klass, 'popup')
        # Determine the target of the "a" tag
        self.target = toPopup and 'appyIFrame' or '_self'
        # If the link leads to a popup, a "onClick" attribute must contain the
        # JS code that opens the popup.
        if toPopup:
            # Create the chunk of JS code to open the popup
            size = getattr(klass, 'popup', '350px')
            if isinstance(size, str):
                params = "%s,null" % size[:-2] # Width only
            else: # Width and height
                params = "%s, %s" % (size[0][:-2], size[1][:-2])
            # If p_back is specified, included it in the JS call
            if back: params += ",'%s'" % back
            self.onClick = "openPopup('iframePopup',null,%s)" % params
        else:
            self.onClick = ''

    def getOnClick(self, back):
        '''Gets the "onClick" attribute, taking into account p_back DOM node ID
           that was unknown at the time the LinkTarget instance was created.'''
        # If we must not come back from a popup, return an empty string
        r = self.onClick
        if not r: return r
        return r[:-1] + ",'%s')" % back

# ------------------------------------------------------------------------------
upperLetter = re.compile('[A-Z]')
def produceNiceMessage(msg):
    '''Transforms p_msg into a nice msg.'''
    res = ''
    if msg:
        res = msg[0].upper()
        for c in msg[1:]:
            if c == '_':
                res += ' '
            elif upperLetter.match(c):
                res += ' ' + c.lower()
            else:
                res += c
    return res
# ------------------------------------------------------------------------------
