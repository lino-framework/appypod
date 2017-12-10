# ~license~
# ------------------------------------------------------------------------------
from appy.px import Px
from appy.ui.layout import Table
from appy.model.fields import Field

# ------------------------------------------------------------------------------
class Boolean(Field):
    '''Field for storing boolean values'''
    yesNo = {'true': 'yes', 'false': 'no', True: 'yes', False: 'no'}
    trueFalse = {True: 'true', False: 'false'}

    # Default layout (render = "checkbox") ("b" stands for "base"), followed by
    # the 'grid' variant (if the field is in a group with 'grid' style).
    bLayouts = {'view': 'lf', 'edit': Table('f;lrv;-', width=None),
                'search': 'l-f', 'cell': Table('f|', align='center')}
    gLayouts = {'view': 'fl', 'edit': Table('frvl', width=None),
                'search': 'l-f', 'cell': Table('f|', align='center')}
    # Layout including a description (followed by grid variant)
    dLayouts = {'view': 'lf', 'edit': Table('flrv;=d', width=None)}
    # *d*escription also visible on "view"
    dvLayouts = {'view': 'lf-d', 'edit': dLayouts['edit']}
    gdLayouts = {'view': 'fl', 'edit': Table('f;dv-', width=None)}
    # Centered layout, no description
    cLayouts = {'view': 'lf|', 'edit': 'flrv|'}
    # Layout for radio buttons (render = "radios")
    rLayouts = {'edit': 'f', 'view': 'f', 'search': 'l-f'}
    rlLayouts = {'edit': 'l-f', 'view': 'lf', 'search': 'l-f'}
    grlLayouts = {'edit': 'fl', 'view': 'fl', 'search': 'l-f'}

    pxView = pxCell = Px('''
    <x>::field.getInlineEditableValue(obj, value, layoutType)</x>
    <input type="hidden" if="masterCss"
           class=":masterCss" value=":rawValue" name=":name" id=":name"/>''')

    pxEdit = Px('''<x var="isTrue=field.isTrue(zobj, rawValue)">
     <x if="field.render == 'checkbox'">
      <input type="checkbox" name=":name + '_visible'" id=":name"
             class=":masterCss" checked=":isTrue"
             onclick=":'toggleCheckbox(this); %s' % \
                        field.getOnChange(zobj, layoutType)"/><input
       type="hidden" name=":name" id=":'%s_hidden' % name"
       value=":isTrue and 'True' or 'False'"/>
     </x>
     <x if="field.render == 'radios'"
        var2="falseId='%s_false' % name;
              trueId='%s_true' % name">
      <input type="radio" name=":name" id=":falseId" class=":masterCss"
             value="False" checked=":not isTrue"/>
      <label lfor=":falseId">:_(field.labelId + '_false')</label><br/>
      <input type="radio" name=":name" id=":trueId" class=":masterCss"
             value="True" checked=":isTrue"/>
      <label lfor=":trueId">:_(field.labelId + '_true')</label>
     </x>
     <script if="hostLayout">:'prepareForAjaxSave(%s,%s,%s,%s)' % \
      (q(name),q(obj.id),q(obj.url),q(hostLayout))</script></x>''')

    pxSearch = Px('''<x var="typedWidget='%s*bool' % widgetName">
      <x var="valueId='%s_yes' % name">
       <input type="radio" value="True" name=":typedWidget" id=":valueId"/>
       <label lfor=":valueId">:_(field.getValueLabel(True))</label>
      </x>
      <x var="valueId='%s_no' % name">
       <input type="radio" value="False" name=":typedWidget" id=":valueId"/>
       <label lfor=":valueId">:_(field.getValueLabel(False))</label>
      </x>
      <x var="valueId='%s_whatever' % name">
       <input type="radio" value="" name=":typedWidget" id=":valueId"
              checked="checked"/>
       <label lfor=":valueId">:_('whatever')</label>
      </x><br/></x>''')

    def __init__(self, validator=None, multiplicity=(0,1), default=None,
      show=True, page='main', group=None, layouts = None, move=0, indexed=False,
      mustIndex=True, indexValue=None, searchable=False,
      specificReadPermission=False, specificWritePermission=False, width=None,
      height=None, maxChars=None, colspan=1, master=None, masterValue=None,
      focus=False, historized=False, mapping=None, label=None, sdefault=False,
      scolspan=1, swidth=None, sheight=None, persist=True, render='checkbox',
      inlineEdit=False, view=None, cell=None, xml=None):
        # By default, a boolean is edited via a checkbox. It can also be edited
        # via 2 radio buttons (p_render="radios").
        self.render = render
        Field.__init__(self, validator, multiplicity, default, show, page,
          group, layouts, move, indexed, mustIndex, indexValue, searchable,
          specificReadPermission, specificWritePermission, width, height, None,
          colspan, master, masterValue, focus, historized, mapping, label,
          sdefault, scolspan, swidth, sheight, persist, inlineEdit, view, cell,
          xml)
        self.pythonType = bool

    def getDefaultLayouts(self):
        if self.render == 'radios': return Boolean.rLayouts
        return self.inGrid() and Boolean.gLayouts or Boolean.bLayouts

    def getValue(self, obj, name=None):
        '''Never returns "None". Returns always "True" or "False", even if
           "None" is stored in the DB.'''
        value = Field.getValue(self, obj, name)
        if value == None: return False
        return value

    def getValueLabel(self, value):
        '''Returns the label for p_value (True or False): if self.render is
           "checkbox", the label is simply the translated version of "yes" or
           "no"; if self.render is "radios", there are specific labels.'''
        if self.render == 'radios':
            return '%s_%s' % (self.labelId, self.trueFalse[value])
        return self.yesNo[value]

    def getFormattedValue(self, obj, value, layoutType='view',
                          showChanges=False, language=None):
        return obj.translate(self.getValueLabel(value), language=language)

    def getStorableValue(self, obj, value):
        if not self.isEmptyValue(obj, value):
            exec('res = %s' % value)
            return res

    def isTrue(self, obj, dbValue):
        '''When rendering this field as a checkbox, must it be checked or
           not?'''
        rq = obj.REQUEST
        # Get the value we must compare (from request or from database)
        if self.name in rq:
            return rq.get(self.name) in ('True', 1, '1')
        return dbValue
# ------------------------------------------------------------------------------
