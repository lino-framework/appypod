# ~license~
# ------------------------------------------------------------------------------
from appy.pod import PodError
from appy.model.utils import Object
from appy.utils import Traceback, commercial, CommercialError
from appy.pod.elements import *

# ------------------------------------------------------------------------------
EVAL_ERROR = 'Error while evaluating expression "%s". %s'
FROM_EVAL_ERROR = 'Error while evaluating the expression "%s" defined in the ' \
                  '"from" part of a statement. %s'
WRONG_SEQ_TYPE = 'Expression "%s" is not iterable.'
TABLE_NOT_ONE_CELL = "The table you wanted to populate with '%s' " \
                     "can\'t be dumped with the '-' option because it has " \
                     "more than one cell in it."

class EvaluationError(Exception):
    def __init__(self, originalError, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)
        self.originalError = originalError

# ------------------------------------------------------------------------------
class Action:
    '''Abstract class representing a action (=statement) that must be performed
       on the content of a buffer (if, for...).'''
    def __init__(self, name, buffer, expr, elem, minus):
        # Actions may be named. Currently, the name of an action is only used
        # for giving a name to "if" actions; thanks to this name, "else" actions
        # that are far away may reference their "if".
        self.name = name
        # The buffer hosting the action
        self.buffer = buffer
        # The Python expression to evaluate (may be None in the case of a
        # Null or Else action, for example).
        self.expr = expr
        # The element within the buffer that is the action's target
        self.elem = elem
        # If "minus" is True, the main elem(s) must not be dumped
        self.minus = minus
        # If "source" is "buffer", we must dump the (evaluated) buffer content.
        # If it is 'from', we must dump what comes from the "from" part of the
        # action (='fromExpr'). See m_setFrom below.
        self.source = 'buffer'
        self.fromExpr = self.fromPlus = None
        # Several actions may co-exist for the same buffer, as a chain of Action
        # instances, defined via the following attribute.
        self.subAction = None

    def setFrom(self, plus, expr):
        '''Associate to this action a "from" clause (pod only)'''
        self.source = 'from'
        self.fromPlus = plus
        self.fromExpr = expr

    def getExceptionLine(self, e):
        '''Gets the line describing exception p_e, containing the exception
           class, message and line number.'''
        return '%s: %s' % (e.__class__.__name__, str(e))

    def manageError(self, result, context, errorMessage, originalError=None):
        '''Manage the encountered error: dump it into the buffer or raise an
           exception.'''
        if self.buffer.env.raiseOnError:
            if not self.buffer.pod:
                # Add in the error message the line nb where the errors occurs
                # within the PX.
                locator = self.buffer.env.parser.locator
                # The column number may not be given
                col = locator.getColumnNumber()
                if col == None: col = ''
                else: col = ', column %d' % col
                errorMessage += ' (line %s%s)' % (locator.getLineNumber(), col)
                # Integrate the traceback (at least, its last lines)
                errorMessage += '\n' + Traceback.get(6).decode('utf-8')
            if originalError:
                raise EvaluationError(originalError, errorMessage)
            raise Exception(errorMessage)
        # Create a temporary buffer to dump the error. If I reuse this buffer to
        # dump the error (what I did before), and we are, at some depth, in a
        # for loop, this buffer will contain the error message and not the
        # content to repeat anymore. It means that this error will also show up
        # for every subsequent iteration.
        tempBuffer = self.buffer.clone()
        PodError.dump(tempBuffer, errorMessage, withinElement=self.elem)
        tempBuffer.evaluate(result, context)

    def _evalExpr(self, expr, context):
        '''Evaluates p_expr with p_context. p_expr can contain an error expr,
           in the form "someExpr|errorExpr". If it is the case, if the "normal"
           expr raises an error, the "error" expr is evaluated instead.'''
        if '|' not in expr:
            res = eval(expr, context)
        else:
            expr, errorExpr = expr.rsplit('|', 1)
            try:
                res = eval(expr, context)
            except Exception:
                res = eval(errorExpr, context)
        return res

    def evaluateExpression(self, result, context, expr):
        '''Evaluates expression p_expr with the current p_context. Returns a
           tuple (result, errorOccurred).'''
        try:
            res = self._evalExpr(expr, context)
            error = False
        except Exception as e:
            # Hack for MessageException instances: always re-raise it as is
            if e.__class__.__name__ == 'MessageException': raise e
            res = None
            errorMessage = EVAL_ERROR % (expr, self.getExceptionLine(e))
            self.manageError(result, context, errorMessage, e)
            error = True
        return res, error

    def execute(self, result, context):
        '''Executes this action given some p_context and add the result to
           p_result.'''
        # Check that if minus is set, we have an element which can accept it
        if self.minus and isinstance(self.elem, Table) and \
           (not self.elem.tableInfo.isOneCell()):
            self.manageError(result, context, TABLE_NOT_ONE_CELL % self.expr)
        else:
            error = False
            # Evaluate self.expr in eRes
            eRes = None
            if self.expr:
                eRes,error = self.evaluateExpression(result, context, self.expr)
            if not error:
                # Trigger action-specific behaviour
                self.do(result, context, eRes)

    def evaluateBuffer(self, result, context,
                       forceSource=None, ignoreMinus=False):
        '''Evaluates the buffer tied to this action and add the result in
           p_result. The source for evaluation can be forced to p_forceSource
           but in most cases depends on self.source.'''
        # Determine the source
        source = forceSource or self.source
        # Determine "minus"
        minus = False if ignoreMinus else self.minus
        if source == 'buffer':
            self.buffer.evaluate(result, context, removeMainElems=minus)
        else:
            # Evaluate self.fromExpr in fromRes
            fromRes = None
            error = False
            try:
                fromRes = eval(self.fromExpr, context)
            except Exception as e:
                msg = FROM_EVAL_ERROR % (self.fromExpr,self.getExceptionLine(e))
                self.manageError(result, context, msg, e)
                error = True
            if not error:
                if not self.fromPlus:
                    # Write the result
                    result.write(fromRes)
                else:
                    # We must keep the root tag within self.buffer and dump the
                    # result into it.
                    content = self.buffer.content
                    result.write(content[:content.find('>') + 1])
                    result.write(fromRes)
                    result.write(content[content.rfind('<'):])

    def addSubAction(self, action):
        '''Adds p_action as a sub-action of this action'''
        if not self.subAction:
            self.subAction = action
            # Transmit "minus" to the sub-action. Indeed, the responsiblity to
            # dump content in the buffer is delegated to the sub-action,
            # "minus-ity" included.
            action.minus = self.minus
        else:
            self.subAction.addSubAction(action)

    def check(self):
        '''Returns a tuple (success, message) indicating if the action is well
           formed or not.'''
        return True, None

class If(Action):
    '''Action that determines if we must include the content of the buffer in
       the result or not.'''
    def do(self, result, context, exprRes):
        if exprRes:
            if self.subAction:
                self.subAction.execute(result, context)
            else:
                self.evaluateBuffer(result, context)
        else:
            if self.buffer.isMainElement(Cell.OD):
                # Don't leave the current row with a wrong number of cells
                result.dumpElement(Cell.OD.elem)

class Else(If):
    '''Action that is linked to a previous "if" action. In fact, an "else"
       action works exactly like an "if" action, excepted that instead of
       defining a conditional expression, it is based on the negation of the
       conditional expression of the last defined "if" action.'''

    def __init__(self, name, buff, expr, elem, minus, ifAction):
        If.__init__(self, name, buff, None, elem, minus)
        self.ifAction = ifAction

    def do(self, result, context, exprRes):
        # This action is executed if the tied "if" action is not executed
        ifAction = self.ifAction
        iRes, error = ifAction.evaluateExpression(result,context,ifAction.expr)
        If.do(self, result, context, not iRes)

class For(Action):
    '''Actions that will include the content of the buffer as many times as
       specified by the action parameters.'''

    def __init__(self, name, buff, expr, elem, minus, iters):
        Action.__init__(self, name, buff, expr, elem, minus)
        # Name of the iterator variable(s) used in each loop
        self.iters = iters

    def initialiseLoop(self, context, elems):
        '''Initialises information about the loop, before entering into it. It
           is possible that this loop overrides an outer loop whose iterator
           has the same name. This method returns a tuple
           (loop, outerOverriddenLoop).'''
        # The "loop" object, made available in the POD context, contains info
        # about all currently walked loops. For every walked loop, a specific
        # object, le'ts name it curLoop, accessible at
        # getattr(loop, self.iters[0]), stores info about its status:
        #   * curLoop.length  gives the total number of walked elements within
        #                     the loop
        #   * curLoop.nb      gives the index (starting at 0) if the currently
        #                     walked element.
        #   * curLoop.first   is True if the currently walked element is the
        #                     first one.
        #   * curLoop.last    is True if the currently walked element is the
        #                     last one.
        #   * curLoop.odd     is True if the currently walked element is odd
        #   * curLoop.even    is True if the currently walked element is even
        # For example, if you have a "for" statement like this:
        #        for elem in myListOfElements
        # Within the part of the ODT document impacted by this statement, you
        # may access to:
        #   * loop.elem.length to know the total length of myListOfElements
        #   * loop.elem.nb     to know the index of the current elem within
        #                      myListOfElements.
        if 'loop' not in context:
            context['loop'] = Object()
        try:
            total = len(elems)
        except Exception:
            total = 0
        curLoop = Object(length=total)
        # Does this loop override an outer loop with homonym iterator ?
        outerLoop = None
        iter = self.iters[0]
        if hasattr(context['loop'], iter):
            outerLoop = getattr(context['loop'], iter)
        # Put this loop in the global object "loop"
        setattr(context['loop'], iter, curLoop)
        return curLoop, outerLoop

    def updateContext(self, context, item, forcedValue=None):
        '''We are in the loop, and p_item is the currently walked item. We must
           update the context by adding or updating values for iterator
           variable(s).'''
        # In most cases, there is a single iterator variable: for x in list
        names = self.iters
        if len(names) == 1:
            if forcedValue == None:
                value = item
            else:
                value = forcedValue
            context[names[0]] = value
        # This is the case: for a, b, c in list
        else:
            i = 0
            while i < len(names):
                if forcedValue == None:
                    value = item[i]
                else:
                    value = forcedValue
                context[names[i]] = value
                i += 1

    def do(self, result, context, elems):
        '''Performs the "for" action. p_elems is the list of elements to
           walk, evaluated from self.expr.'''
        # Check p_exprRes type
        try:
            # All "iterable" objects are OK
            iter(elems)
        except TypeError as te:
            self.manageError(result, context, WRONG_SEQ_TYPE % self.expr, te)
            return
        # Remember variables hidden by iterators if any
        hiddenVars = {}
        for name in self.iters:
            if name in context:
                hiddenVars[name] = context[name]
        # In the case of cells, initialize some values
        isCell = False
        if isinstance(self.elem, Cell):
            isCell = True
            if 'columnsRepeated' in context:
                # This feature is only available in the open source version
                if commercial: raise CommercialError()
                nbOfColumns = sum(context['columnsRepeated'])
                customColumnsRepeated = True
            else:
                nbOfColumns = self.elem.tableInfo.nbOfColumns
                customColumnsRepeated = False
            initialColIndex = self.elem.colIndex
            currentColIndex = initialColIndex
            rowAttributes = self.elem.tableInfo.curRowAttrs
            # If p_elems is empty, dump an empty cell to avoid having the wrong
            # number of cells for the current row.
            if not elems:
                result.dumpElement(Cell.OD.elem)
        # Enter the "for" loop
        loop, outerLoop = self.initialiseLoop(context, elems)
        i = -1
        for item in elems:
            i += 1
            loop.nb = i
            loop.first = i == 0
            loop.last = i == (loop.length-1)
            loop.even = (i%2)==0
            loop.odd = not loop.even
            self.updateContext(context, item)
            # Cell: add a new row if we are at the end of a row
            if isCell and (currentColIndex == nbOfColumns):
                result.dumpEndElement(Row.OD.elem)
                result.dumpStartElement(Row.OD.elem, rowAttributes)
                currentColIndex = 0
            # If a sub-action is defined, execute it
            if self.subAction:
                self.subAction.execute(result, context)
            else:
                # Evaluate the buffer directly
                self.evaluateBuffer(result, context)
            # Cell: increment the current column index
            if isCell:
                currentColIndex += 1
        # Cell: leave the last row with the correct number of cells, excepted
        # if the user has specified himself "columnsRepeated": it is his
        # responsibility to produce the correct number of cells.
        if isCell and elems and not customColumnsRepeated:
            wrongNbOfCells = (currentColIndex-1) - initialColIndex
            if wrongNbOfCells < 0: # Too few cells for last row
                for i in range(abs(wrongNbOfCells)):
                    self.updateContext(context, None, forcedValue='')
                    self.buffer.evaluate(result, context, subElements=False)
                    # This way, the cell is dumped with the correct styles
            elif wrongNbOfCells > 0: # Too many cells for last row
                # Finish current row
                nbOfMissingCells = 0
                if currentColIndex < nbOfColumns:
                    nbOfMissingCells = nbOfColumns - currentColIndex
                    self.updateContext(context, None, forcedValue='')
                    for i in range(nbOfMissingCells):
                        self.buffer.evaluate(result, context, subElements=False)
                result.dumpEndElement(Row.OD.elem)
                # Create additional row with remaining cells
                result.dumpStartElement(Row.OD.elem, rowAttributes)
                nbOfRemainingCells = wrongNbOfCells + nbOfMissingCells
                nbOfMissingCellsLastLine = nbOfColumns - nbOfRemainingCells
                self.updateContext(context, None, forcedValue='')
                for i in range(nbOfMissingCellsLastLine):
                    self.buffer.evaluate(result, context, subElements=False)
        # Delete the current loop object and restore the overridden one if any
        name = self.iters[0]
        try:
            delattr(context['loop'], name)
        except AttributeError:
            pass
        if outerLoop:
            setattr(context['loop'], name, outerLoop)
        # Restore hidden variables and remove iterator variables from the
        # context.
        context.update(hiddenVars)
        if elems:
            for name in self.iters:
                if (name not in hiddenVars) and (name in context):
                    # On error, name may not be in the context
                    del context[name]

class Null(Action):
    '''Action that does nothing. Used in conjunction with a "from" clause, it
       allows to insert in a buffer arbitrary odt content.'''
    noFromError = 'There was a problem with this action. Possible causes: ' \
      '(1) you specified no action (ie "do text") while not specifying any ' \
      'from clause; (2) you specified the from clause on the same line as ' \
      'the action, which is not allowed (ie "do text from ...").'

    def __init__(self, buff, elem):
        Action.__init__(self, '', buff, None, elem, None)

    def do(self, result, context, exprRes):
        self.evaluateBuffer(result, context)

    def check(self):
        '''This action must have a tied from clause'''
        if self.source != 'from':
            return False, self.noFromError
        return True, None

class MetaIf(Action):
    '''Action allowing a note not to be evaluated and re-dumped as-is in the
       result, depending on some (meta-) condition.'''

    class StringBuffer:
        '''Class adopting a behaviour similar to a memory buffer, but
           simplified, used to reify the note coresponding to the buffer action
           when it must not be evaluated.'''
        def __init__(self):
            self.content = u''
            self.action = None
        def write(self, s): self.content += s
        dumpContent = write

    def __init__(self, buff, subExpr, elem, minus, statements):
        Action.__init__(self, '', buff, subExpr, elem, minus)
        # The list of statements containing in the original note
        self.statements = statements

    def reifyNote(self):
        '''Recreate the note as close to the original as possible'''
        # Use some fake buffer and dump the note in it. Reuse the code for
        # dumping an error, also dumped as a note.
        r = self.StringBuffer()
        PodError.dump(r, '</text:p>\n<text:p>'.join(self.statements),
                      dumpTb=False)
        return r

    def do(self, result, context, exprRes):
        if exprRes:
            # The "meta-if" condition is True. It means that content must really
            # be dumped.
            if self.subAction:
                self.subAction.execute(result, context)
            else:
                self.evaluateBuffer(result, context)
        else:
            # The note must be dumped unevaluated in the result; the potential
            # "from" expression must not be evaluated as well.
            note = self.reifyNote()
            # Inject the note in the buffer, after the first 'text:p' tag: else,
            # it might not be rendered. self.minus must not be interpreted.
            self.buffer.insertSubBuffer(note, after='text:p')
            self.evaluateBuffer(result, context,
                                forceSource='buffer', ignoreMinus=True)

class Variables(Action):
    '''Action that allows to define a set of variables somewhere in the
       template.'''
    def __init__(self, name, buff, elem, minus, variables):
        # We do not use the default Buffer.expr attribute for storing the Python
        # expression, because here we will have several expressions, one for
        # every defined variable.
        Action.__init__(self,name, buff, None, elem, minus)
        # Definitions of variables: ~[(s_name, s_expr)]~
        self.variables = variables

    def do(self, result, context, exprRes):
        '''Evaluate the variables' expressions: because there are several
           expressions, we do not use the standard, single-expression-minded
           Action code for evaluating our expressions.

           We remember the names and values of the variables that we will hide
           in the context: after execution of this buffer we will restore those
           values.
        '''
        hidden = None
        for name, expr in self.variables:
            # Evaluate variable expression in vRes
            vRes, error = self.evaluateExpression(result, context, expr)
            if error: return
            # Replace the value of global variables
            if name.startswith('@'):
                context[name[1:]] = vRes
                continue
            # Remember the variable previous value if already in the context
            if name in context:
                if not hidden:
                    hidden = {name: context[name]}
                else:
                    hidden[name] = context[name]
            # Store the result into the context
            context[name] = vRes
        # If a sub-action is defined, execute it
        if self.subAction:
            self.subAction.execute(result, context)
        else:
            # Evaluate the buffer directly
            self.evaluateBuffer(result, context)
        # Restore hidden variables if any
        if hidden: context.update(hidden)
        # Delete not-hidden variables
        for name, expr in self.variables:
            if name.startswith('@'): continue
            if hidden and (name in hidden): continue
            del context[name]
# ------------------------------------------------------------------------------
