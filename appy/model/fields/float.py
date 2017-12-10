# ~license~
# ------------------------------------------------------------------------------
from appy.px import Px
from appy import utils
from appy.model.fields import Field

# ------------------------------------------------------------------------------
class Float(Field):
    allowedDecimalSeps = (',', '.')

    pxView = pxCell = Px('''
     <x><x>:value</x>
      <input type="hidden" if="masterCss" class=":masterCss" value=":value"
             name=":name" id=":name"/>
     </x>''')

    pxEdit = Px('''
     <input type="text" id=":name" name=":name" size=":field.width"
            maxlength=":field.maxChars"
            value=":field.getInputValue(inRequest, requestValue, value)"/>''')

    pxSearch = Px('''
     <!-- From -->
     <x var="fromName='%s*float' % widgetName">
      <label lfor=":fromName">:_('search_from')</label>
      <input type="text" name=":fromName" maxlength=":field.maxChars"
             value=":field.sdefault[0]" size=":field.swidth"/>
     </x>
     <!-- To -->
     <x var="toName='%s_to' % name">
      <label lfor=":toName">:_('search_to')</label>
      <input type="text" name=":toName" maxlength=":field.maxChars"
             value=":field.sdefault[1]" size=":field.swidth"/>
     </x><br/>''')

    def __init__(self, validator=None, multiplicity=(0,1), default=None,
      show=True, page='main', group=None, layouts=None, move=0, indexed=False,
      mustIndex=True, indexValue=None, searchable=False,
      specificReadPermission=False, specificWritePermission=False, width=5,
      height=None, maxChars=13, colspan=1, master=None, masterValue=None,
      focus=False, historized=False, mapping=None, label=None, sdefault=('',''),
      scolspan=1, swidth=None, sheight=None, persist=True, precision=None,
      sep=(',', '.'), tsep=' ', inlineEdit=False, view=None, cell=None,
      xml=None):
        # The precision is the number of decimal digits. This number is used
        # for rendering the float, but the internal float representation is not
        # rounded.
        self.precision = precision
        # The decimal separator can be a tuple if several are allowed, ie
        # ('.', ',')
        if type(sep) not in utils.sequenceTypes:
            self.sep = (sep,)
        else:
            self.sep = sep
        # Check that the separator(s) are among allowed decimal separators
        for sep in self.sep:
            if sep not in Float.allowedDecimalSeps:
                raise Exception('Char "%s" is not allowed as decimal ' \
                                'separator.' % sep)
        self.tsep = tsep
        Field.__init__(self, validator, multiplicity, default, show, page,
          group, layouts, move, indexed, mustIndex, indexValue, searchable,
          specificReadPermission, specificWritePermission, width, height,
          maxChars, colspan, master, masterValue, focus, historized, mapping,
          label, sdefault, scolspan, swidth, sheight, persist, inlineEdit,
          view, cell, xml)
        self.pythonType = float

    def getFormattedValue(self, obj, value, layoutType='view',
                          showChanges=False, language=None):
        return utils.formatNumber(value, sep=self.sep[0],
                                  precision=self.precision, tsep=self.tsep)

    def validateValue(self, obj, value):
        # Replace used separator with the Python separator '.'
        for sep in self.sep: value = value.replace(sep, '.')
        value = value.replace(self.tsep, '')
        try:
            value = self.pythonType(value)
        except ValueError:
            return obj.translate('bad_%s' % self.pythonType.__name__)

    def getStorableValue(self, obj, value):
        if not self.isEmptyValue(obj, value):
            for sep in self.sep: value = value.replace(sep, '.')
            value = value.replace(self.tsep, '')
            return self.pythonType(value)
# ------------------------------------------------------------------------------
