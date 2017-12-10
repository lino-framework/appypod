# ~license~
# ------------------------------------------------------------------------------
from appy.px import Px
from appy.model.fields import Field

# ------------------------------------------------------------------------------
class Integer(Field):
    pxView = pxCell = Px('''
     <x>::field.getInlineEditableValue(obj, value, layoutType)</x>
     <input type="hidden" if="masterCss"
            class=":masterCss" value=":value" name=":name" id=":name"/>''')

    pxEdit = Px('''
     <input type="text" id=":name" name=":name" size=":field.width"
            maxlength=":field.maxChars"
            value=":field.getInputValue(inRequest, requestValue, value)"/>
     <script if="hostLayout">:'prepareForAjaxSave(%s,%s,%s,%s)' % \
      (q(name),q(obj.id),q(obj.url),q(hostLayout))</script>''')

    pxSearch = Px('''
     <!-- From -->
     <x var="fromName='%s*int' % widgetName">
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
      scolspan=1, swidth=None, sheight=None, persist=True, inlineEdit=False,
      view=None, cell=None, xml=None):
        Field.__init__(self, validator, multiplicity, default, show, page,
          group, layouts, move, indexed, mustIndex, indexValue, searchable,
          specificReadPermission, specificWritePermission, width, height,
          maxChars, colspan, master, masterValue, focus, historized, mapping,
          label, sdefault, scolspan, swidth, sheight, persist, inlineEdit, view,
          cell, xml)
        self.pythonType = int

    def validateValue(self, obj, value):
        try:
            value = self.pythonType(value)
        except ValueError:
            return obj.translate('bad_%s' % self.pythonType.__name__)

    def getStorableValue(self, obj, value):
        if not self.isEmptyValue(obj, value): return self.pythonType(value)

    def getFormattedValue(self, obj, value, layoutType='view',
                          showChanges=False, language=None):
        if self.isEmptyValue(obj, value): return ''
        return str(value)
# ------------------------------------------------------------------------------
