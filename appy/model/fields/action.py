# ~license~
# ------------------------------------------------------------------------------
import os.path
from appy.px import Px
from appy import utils
from appy.ui.layout import Layouts
from appy.model.fields import Field, Initiator

# Constants --------------------------------------------------------------------
CONFIRM_ERROR = 'When using options, a popup will already be shown, with the ' \
  'possibility to cancel the action, so it has no sense to ask a ' \
  'confirmation via attribute "confirm".'
RESULT_ERROR = 'Currently, when specifying options, you cannot set a result ' \
  'which is different from "computation".'

# ------------------------------------------------------------------------------
class ActionInitiator(Initiator):
    '''Initiator used when an action triggers the creation of an object via
       field "options" (see below).'''

    def manage(self, options):
        '''Executes the action with p_options. Once this has been done,
           p_options becomes useless and is deleted.'''
        # Call the action(s) with p_options as argument (simulate a UI request)
        method = self.field.onUiRequest
        success, msg = method(self.obj, self.req, options=options, minimal=True)
        # Remove the "options" transient object
        options.delete()

# ------------------------------------------------------------------------------
class Action(Field):
    '''An action is a Python method that can be triggered by the user on a
       given Appy class. An action is rendered as a button.'''
    # Action-specific initiator class
    initiator = ActionInitiator

    # PX for viewing the Action button
    pxView = pxCell = Px('''
     <form var="formId='%s_%s_form' % (zobj.id, name);
                label=_(field.labelId);
                inputTitle=field.getInputTitle(zobj, label);
                inputLabel=field.getInputLabel(label, layoutType);
                smallButtons=smallButtons|False;
                css=ztool.getButtonCss(label, smallButtons, field.render)"
           id=":formId" action=":field.getFormAction(zobj, ztool)"
           target=":field.options and 'appyIFrame' or '_self'"
           style="display:inline">

      <!-- Form fields for direct action execution -->
      <x if="not field.options">
       <input type="hidden" name="fieldName" value=":name"/>
       <input type="hidden" name="popupComment" value=""/>
      </x>

      <!-- Form fields for creating an options instance -->
      <x if="field.options">
       <input type="hidden" name="action" value="Create"/>
       <input type="hidden" name="className"
              value=":ztool.getPortalType(field.options)"/>
       <input type="hidden" name="popup" value="1"/>
       <input type="hidden" name="nav"
              value=":'action.%s.%s'% (zobj.id, name)"/>
      </x>

      <!-- The button for executing the action -->
      <input type="button" class=":css" title=":inputTitle"
             value=":inputLabel" style=":url(field.icon, bg=True)"
             onclick=":field.getOnClick(zobj, name, layoutType, q)"/>
     </form>''')

    # It is not possible to edit an action, not to search it
    pxEdit = pxSearch = ''

    def __init__(self, validator=None, multiplicity=(1,1), default=None,
                 show=('view', 'result'), page='main', group=None, layouts=None,
                 move=0, specificReadPermission=False,
                 specificWritePermission=False, width=None, height=None,
                 maxChars=None, colspan=1, action=None, result='computation',
                 downloadDisposition='attachment', confirm=False, master=None,
                 masterValue=None, focus=False, historized=False, mapping=None,
                 label=None, icon=None, view=None, cell=None, xml=None,
                 render='button', options=None):
        # "action" must be a method or a list/tuple of methods. In most cases,
        # every method will be called without arg, but there are exceptions (see
        # parameters "options" and "confirm").
        self.action = action
        # For the 'result' param:
        #  * value 'computation' means that the action will simply compute
        #    things and redirect the user to the same page, with some status
        #    message about execution of the action;
        #  * 'file' means that the result is the binary content of a file that
        #    the user will download (it must be an opened Python file handler;
        #    after the action has been executed, Appy will close the handler);
        #  * 'redirect' means that the action will lead to the user being
        #    redirected to some other page.
        self.result = result
        # If self.result is "file", the "disposition" for downloading the file
        # is defined in self.downloadDisposition and can be "attachment" or
        # "inline".
        self.downloadDisposition = downloadDisposition
        # If "confirm" is True, a popup will ask the user if he is really sure
        # about triggering this action. If "confirm" is "comment", the same
        # effect wil be achieved, but the popup will contain a field allowing to
        # enter a comment; this comment will be available to self.action's
        # method(s), via a parameter named "comment".
        self.confirm = confirm
        # If no p_icon is specified, "action.png" will be used
        self.icon = icon or 'action'
        Field.__init__(self, None, (0,1), default, show, page, group, layouts,
                       move, False, True, None, False, specificReadPermission,
                       specificWritePermission, width, height, None, colspan,
                       master, masterValue, focus, historized, mapping, label,
                       None, None, None, None, False, False, view, cell, xml)
        self.validable = False
        # There are various ways to render the action in the ui:
        # "button"   (the default) as a button;
        # "icon"     as an icon on layouts where compacity is a priority
        #            (ie, within lists of objects) but still as a button on the
        #            "view" layout.
        self.render = render
        # An action may receive options: once the user clicks on the action's
        # icon or button, a form is shown, allowing to choose options. In order
        # to achieve this, specify an Appy class in field "options". self.action
        # will then be called with an instance of this class in a parameter
        # named "option". After the action has been executed, this instance will
        # be deleted.
        self.options = options
        self.checkParameters()

    def checkParameters(self):
        '''Ensures this Action is correctly defined'''
        # Currently, "result" cannot be "file" or "redirect" if options exist.
        # Indeed, when options are in use, the process of executing and
        # finalizig the action, and redirecting the user, is managed by the
        # object creation mechanism, that has limitations.
        if self.options:
            if self.result != 'computation': raise Exception(RESULT_ERROR)
            if self.confirm: raise Exception(CONFIRM_ERROR)

    def getDefaultLayouts(self): return Layouts.Action.b

    def renderLabel(self, layoutType):
        return # Label is rendered directly within the button

    def getFormAction(self, zobj, ztool):
        '''Get the value of the "action" parameter to the "form" tag
           representing the action.'''
        if self.options:
            # Submitting the form will lead to creating an object, in order to
            # retrieve action's options.
            return '%s/do' % ztool.absolute_url()
        else:
            # Submitting the form will really trigger the action
            return '%s/onExecuteAction' % zobj.absolute_url()
    
    def getOnClick(self, zobj, name, layoutType, q):
        '''Gets the JS code to execute when the action button is clicked'''
        # Determine the ID of the form to submit
        formId = '%s_%s_form' % (zobj.id, name)
        back = (layoutType == 'cell') and zobj.id or None
        if not self.options:
            # Determine the parameters for executing the action
            showComment = (self.confirm == 'comment') and 'true' or 'false'
            confirmText = self.getConfirmText(zobj)
            back = not back and 'null' or q(back)
            js = 'submitForm(%s,%s,%s,%s)' % (q(formId), q(confirmText),
                                              showComment, back)
        else:
            # Determine the parameters for creating an options instance
            target = gutils.LinkTarget(klass=self.options,
                                       forcePopup=True, back=back)
            js = '%s; submitForm(%s)' % (target.onClick, q(formId))
        return js

    def __call__(self, obj, options=None):
        '''Calls the action on p_obj. Returns a tuple (b_success, s_message)'''
        # Get args to give to method(s) in self.action
        args = {}
        if options: args['options'] = options
        if self.confirm == 'comment':
            args['comment'] = obj.request.get('popupComment')
        # Call method(s) in self.action
        if type(self.action) in sutils.sequenceTypes:
            # There are multiple methods
            res = [True, '']
            for act in self.action:
                actRes = act(obj, **args)
                if type(actRes) in sutils.sequenceTypes:
                    res[0] = res[0] and actRes[0]
                    if self.result.startswith('file'):
                        res[1] = res[1] + actRes[1]
                    else:
                        res[1] = res[1] + '\n' + actRes[1]
                else:
                    res[0] = res[0] and actRes
        else:
            # There is only one method
            actRes = self.action(obj, **args)
            if type(actRes) in sutils.sequenceTypes:
                res = list(actRes)
            else:
                res = [actRes, '']
        # If res is None (ie the user-defined action did not return anything),
        # we consider the action as successfull.
        if res[0] == None: res[0] = True
        return res

    def isShowable(self, obj, layoutType):
        if layoutType == 'edit': return
        return Field.isShowable(self, obj, layoutType)

    def getInputTitle(self, obj, label):
        '''Returns the content of attribute "title" for the "input" field
           corresponding to the action in the ui.'''
        if not self.hasDescr: return label
        return '%s: %s' % (label, obj.translate(self.descrId))

    def getInputLabel(self, label, layoutType):
        '''Returns the label to display on the button corresponding to this
           action = the content of attribute "value" for the "input" field.'''
        # An icon is a button rendered without "value", excepted on the "view"
        # layout, where we still display it.
        if (self.render == 'icon') and (layoutType != 'view'): return ''
        return label

    def getConfirmText(self, zobj):
        '''Get the text to display in the confirm popup'''
        if not self.confirm: return ''
        _ = zobj.translate
        return _(self.labelId + '_confirm', blankOnError=True) or \
               _('action_confirm')

    # Action fields can a priori be shown on every layout, "buttons" included
    def isRenderable(self, layoutType): return True

    def onUiRequest(self, obj, rq, options=None, minimal=False):
        '''This method is called when a user triggers the execution of this
           action from the user interface.'''
        # Execute the action (method __call__)
        actionRes = self(obj.appy(), options=options)
        # Unwrap action results
        success, msg = actionRes
        if not msg:
            # Use the default i18n messages
            suffix = success and 'done' or 'ko'
            msg = obj.translate('action_%s' % suffix)
        # Stop here if p_minimal is True
        if minimal: return success, msg
        if (self.result == 'computation') or not success:
            # If we are called from an Ajax request, simply return msg
            if hasattr(rq, 'pxContext') and rq.pxContext['ajax']: return msg
            obj.say(msg)
            return obj.goto(obj.getUrl(obj.getReferer()))
        elif self.result == 'file':
            # msg does not contain a message, but a Python file handler
            response = rq.RESPONSE
            response.setHeader('Content-Type', utils.getMimeType(msg.name))
            response.setHeader('Content-Disposition', '%s;filename="%s"' % \
                         (self.downloadDisposition, os.path.basename(msg.name)))
            response.write(msg.read())
            msg.close()
        elif self.result == 'redirect':
            # msg does not contain a message, but the URL where to redirect
            # the user. Redirecting is different if we are in an Ajax request.
            if hasattr(rq, 'pxContext') and rq.pxContext['ajax']:
                rq.RESPONSE.setHeader('Appy-Redirect', msg)
                obj.setMessageCookie()
            else:
                return obj.goto(msg)
# ------------------------------------------------------------------------------
