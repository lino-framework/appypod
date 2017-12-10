# ~license~
# ------------------------------------------------------------------------------
from appy import utils
from appy.px import Px
from appy.model.fields.group import Group
from appy.db.indexer import Keywords, defaultIndexes

# Error messages ---------------------------------------------------------------
WRONG_FIELD = 'Field "%s" does not exist on %s'

# ------------------------------------------------------------------------------
class ColSet:
    '''Represents a named set of columns to show when displaying Search results
       (or also Refs).'''
    def __init__(self, identifier, label, columns, specs=False):
        # A short identifier for the set
        self.identifier = identifier
        # The i18n label to use for giving a human-readable name to the set
        self.label = label
        # The list/tuple of columns, expressed as strings. Every string must
        # contain a field name, but can be completed (after a char *) by column
        # width and alignment, as in "state*100px|". The "width" part, just
        # after the *, can hold anything that can be set in a "width" HTML
        # attribute. The last char represents the alignment:
        #   ";"   left-aligned (the default);
        #   "|"   centered;
        #   "!"   right-aligned.
        if not specs:
            self.columns = columns
        else:
            # "specs" is the internal representation of "columns". Do not
            # specify "specs=True". It will contain a list of Object instances
            # instead of strings. Every such instance has splitted string info
            # into fields "field", "width" and "align".
            self.specs = columns

# ------------------------------------------------------------------------------
class Search:
    '''Used for specifying a search for a given class'''
    ColSet = ColSet # Make this class available as "Search.ColSet"
    initiator = None # Is it not possible to create an object from a search

    def __init__(self, name=None, group=None, sortBy='', sortOrder='asc',
                 maxPerPage=30, default=False, colspan=1, translated=None,
                 show=True, showActions=True, translatedDescr=None,
                 checkboxes=False, checkboxesDefault=True, klass=None,
                 **fields):
        # "name" is mandatory, excepted in some special cases (ie, when used as
        # "select" param for a Ref field).
        self.name = name
        # Searches may be visually grouped in the portlet
        self.group = Group.get(group)
        self.sortBy = sortBy
        self.sortOrder = sortOrder
        self.maxPerPage = maxPerPage
        # If this search is the default one, it will be triggered by clicking
        # on main link.
        self.default = default
        self.colspan = colspan
        # If a translated name or description is already given here, we will
        # use it instead of trying to translate from labels.
        self.translated = translated
        self.translatedDescr = translatedDescr
        # Condition for showing or not this search
        self.show = show
        # Condition for showing or not actions on every result of this search.
        # Can be: True, False or "inline". If True, actions will appear in a
        # "div" tag, below the object title; if "inline", they will appear
        # besides it, producing a more compact list of results.
        self.showActions = showActions
        # In the dict below, keys are indexed field names or names of standard
        # indexes, and values are search values.
        self.fields = fields
        # Do we need to display checkboxes for every object of the query result?
        self.checkboxes = checkboxes
        # Default value for checkboxes
        self.checkboxesDefault = checkboxesDefault
        # Most of the time, we know what is the class whose instances must be
        # searched. When it is not the case, the p_klass can be explicitly
        # specified.
        self.klass = klass

    @staticmethod
    def getIndexName(name, klass, usage='search'):
        '''Gets the name of the Zope index that corresponds to p_name. Indexes
           can be used for searching (p_usage="search"), for filtering
           ("filter") or for sorting ("sort"). The method returns None if the
           field named p_name can't be used for p_usage.'''
        # Manage indexes that do not have a corresponding field
        if name == 'created': return 'Created'
        elif name == 'modified': return 'Modified'
        elif name in defaultIndexes: return name
        else:
            # Manage indexes corresponding to fields
            field = getattr(klass, name, None) 
            if field: return field.getIndexName(usage)
            raise Exception(WRONG_FIELD % (name, klass.__bases__[-1].__name__))

    @staticmethod
    def getSearchValue(fieldName, fieldValue, klass):
        '''Returns a transformed p_fieldValue for producing a valid search
           value as required for searching in the index corresponding to
           p_fieldName.'''
        # Get the field corresponding to p_fieldName
        field = getattr(klass, fieldName, None)
        if field and callable(field): field = None
        if (field and (field.getIndexType() == 'TextIndex')) or \
           (fieldName == 'SearchableText'):
            # For TextIndex indexes. We must split p_fieldValue into keywords.
            res = Keywords(fieldValue).get()
        elif isinstance(fieldValue, basestring) and fieldValue.endswith('*'):
            v = fieldValue[:-1]
            # Warning: 'z' is higher than 'Z'!
            res = {'query':(v,v+'z'), 'range':'min:max'}
        elif type(fieldValue) in sutils.sequenceTypes:
            if fieldValue and isinstance(fieldValue[0], basestring):
                # We have a list of string values (ie: we need to
                # search v1 or v2 or...)
                res = fieldValue
            else:
                # We have a range of (int, float, DateTime...) values
                minv, maxv = fieldValue
                rangev = 'minmax'
                queryv = fieldValue
                if minv == None:
                    rangev = 'max'
                    queryv = maxv
                elif maxv == None:
                    rangev = 'min'
                    queryv = minv
                res = {'query':queryv, 'range':rangev}
        else:
            res = fieldValue
        return res

    def updateSearchCriteria(self, criteria, klass, advanced=False):
        '''This method updates dict p_criteria with all the search criteria
           corresponding to this Search instance. If p_advanced is True,
           p_criteria correspond to an advanced search, to be stored in the
           session: in this case we need to keep the Appy names for parameters
           sortBy and sortOrder (and not "resolve" them to Zope's sort_on and
           sort_order).'''
        # Put search criteria in p_criteria
        criteria['showActions'] = self.showActions
        for name, value in self.fields.items():
            # Management of searches restricted to objects linked through a
            # Ref field: not implemented yet.
            if name == '_ref': continue
            # Make the correspondence between the name of the field and the
            # name of the corresponding index, excepted if advanced is True: in
            # that case, the correspondence will be done later.
            if not advanced:
                indexName = Search.getIndexName(name, klass)
                # Express the field value in the way needed by the index
                criteria[indexName] = Search.getSearchValue(name, value, klass)
            else:
                criteria[name] = value
        # Add a sort order if specified
        if self.sortBy:
            c = criteria
            if not advanced:
                c['sort_on']=Search.getIndexName(self.sortBy,klass,usage='sort')
                c['sort_order']= (self.sortOrder=='desc') and 'reverse' or None
            else:
                c['sortBy'] = self.sortBy
                c['sortOrder'] = self.sortOrder

    def isShowable(self, klass, tool):
        '''Is this Search instance (defined in p_klass) showable ?'''
        if self.show.__class__.__name__ == 'staticmethod':
            return utils.callMethod(tool, self.show, klass=klass)
        return self.show

    def getSessionKey(self, className, full=True):
        '''Returns the name of the key, in the session, where results for this
           search are stored when relevant. If p_full is False, only the suffix
           of the session key is returned (ie, without the leading
           "search_").'''
        res = (self.name == 'allSearch') and className or self.name
        if not full: return res
        return 'search_%s' % res

    mergeFields = ('sortBy', 'sortOrder', 'showActions')
    def merge(self, other):
        '''Merge parameters from another search in p_other'''
        self.fields.update(other.fields)
        for name in self.mergeFields: setattr(self, name, getattr(other, name))

    def run(self, tool):
        '''Executes this query. Works only when self.klass exists.'''
        if not self.klass:
            raise Exception('Running this query requires self.klass')
        return tool.search(self.klass, sortBy=self.sortBy,
                           sortOrder=self.sortOrder, **self.fields)

# Initiators for searches whose results are shown in popups --------------------
class Initiator:
    '''When a query is rendered in a popup, the "initiator", in the main page,
       can be:
       * (a) some object, in view or edit mode, displaying a given Ref field
             for which the popup is used to select one or more objects to link;
       * (b) some class for which we must create an instance from a template;
             the popup is used to select such a template object.

       This class is the abstract class for 2 concrete initiator classes:
       RefInitiator (for case a) and TemplateInitiator (for case b).
    '''

class RefInitiator(Initiator):
    def __init__(self, obj, field, fieldName, mode):
        # The initiator object
        self.obj = obj
        # The initiator field
        self.field = field
        # As usual, the field name can be different from field.name if it is a
        # sub-field within a List field
        self.fieldName = fieldName
        # The mode can be:
        # - "repl" if the objects selected in the popup will replace already
        #          tied objects;
        # - "add"  if those objects will be added to the already tied ones.
        self.mode = mode
        # "hook" is the ID of the initiator field's XHTML tag
        self.hook = '%s_%s' % (obj.id, fieldName)
        # The root Ajax hook ID in the popup
        self.popupHook = '%s_popup' % self.hook

    def showCheckboxes(self):
        '''We must show object checkboxes if self.field is multivalued: indeed,
           in this case, several objects can be selected in the popup.'''
        return self.field.isMultiValued()

    def jsSelectOne(self, q, cbId):
        '''Generates the Javascript code to execute when a single object is
           selected in the popup.'''
        return 'onSelectObject(%s,%s,%s)' % \
               (q(cbId), q(self.hook), q(self.obj.url))

    def jsSelectMany(self, q, sortKey, sortOrder, filters):
        '''Generates the Javascript code to execute when several objects are
           selected in the popup.'''
        return 'onSelectObjects(%s,%s,%s,%s,%s,%s,%s)' % \
          (q(self.popupHook), q(self.hook), q(self.obj.url), q(self.mode), \
           q(sortKey), q(sortOrder), q(filters))

    def getAjaxParams(self):
        '''Get initiator-specific parameters for retriggering the Ajax
           request for refreshing objects in the popup.'''
        return

class TemplateInitiator(Initiator):
    MANY_ERROR = 'Cannot select several objects from a template initiator.'

    def __init__(self, className, formName, insert, sourceField):
        # The class from which we must create an instance based on a template
        # that we will choose in the popup. Indeed, the instance to create may
        # be from a different class that the instances shown in the popup.
        self.className = className
        # The name of the form that will be submitted for creating the object
        # once a template will have been selected in the popup.
        self.formName = formName
        # The root Ajax hook ID in the popup
        self.popupHook = '%s_popup' % className
        # If the object to create must be inserted at a given place in a Ref
        # field, this can be specified in p_insert.
        self.insert = insert or ''
        # The source field
        self.sourceField = sourceField

    def showCheckboxes(self):
        '''We must hide object checkboxes: only one template object can be
           selected.'''
        return

    def jsSelectOne(self, q, cbId):
        '''Generates the Javascript code to execute when a single object is
           selected in the popup.'''
        return 'onSelectTemplateObject(%s,%s,%s)' % \
               (q(cbId), q(self.formName), q(self.insert))

    def jsSelectMany(self, q, sortKey, sortOrder, filters):
        raise Exception(self.MANY_ERROR)

    def getAjaxParams(self):
        res = {'fromClass': self.className, 'formName': self.formName}
        if self.insert:
            res['insert'] = self.insert
        if self.sourceField:
            res['sourceField'] = self.sourceField
        return res

# UI search --------------------------------------------------------------------
class UiSearch:
    '''Instances of this class are generated on-the-fly for manipulating a
       Search from the User Interface.'''
    # Tied sub-classes
    RefInitiator = RefInitiator
    TemplateInitiator = TemplateInitiator
    pxByMode = {'list': 'pxResultList', 'grid': 'pxResultGrid'}

    # Rendering a search
    pxView = Px('''
     <div class="portletSearch">
      <a href=":'%s?className=%s&amp;search=%s' % \
                 (queryUrl, className, search.name)"
         class=":(search.name == currentSearch) and 'current' or ''"
         onclick="clickOn(this)"
         title=":search.translatedDescr">:search.translated</a>
     </div>''')

    # Search results, as a list (used by pxResult below)
    pxResultList = Px('''
     <table class=":ztool.getResultCss(className, layoutType)" width="100%">
      <!-- Headers, with filters and sort arrows -->
      <tr if="showHeaders">
       <th if="checkboxes" class="cbCell" style=":'display:%s' % cbDisplay">
        <img src=":url('checkall')" class="clickable"
             title=":_('check_uncheck')"
             onclick=":'toggleAllCbs(%s)' % q(checkboxesId)"/>
       </th>
       <th for="column in columns"
           var2="field=column.field;
                 sortable=field.isSortable(usage='search')"
           width=":column.width" align=":column.align">
        <x>::ztool.truncateText(_(field.labelId))</x>
        <!-- Sort icons -->
        <x if="sortable and (totalNumber &gt; 1)">
         <img if="(sortKey != field.name) or (sortOrder == 'desc')"
              onclick=":'askBunchSorted(%s, %s, %s)' % \
                        (q(ajaxHookId), q(field.name), q('asc'))"
              src=":url('sortDown')" class="clickable"/>
         <img if="(sortKey != field.name) or (sortOrder == 'asc')"
              onclick=":'askBunchSorted(%s, %s, %s)' % \
                        (q(ajaxHookId), q(field.name), q('desc'))"
              src=":url('sortUp')" class="clickable"/>
        </x>
        <!-- Filter widget -->
        <x if="field.filterPx and ((totalNumber &gt; 1) or \
               filters)">:getattr(field, field.filterPx)</x>
        <x>:tool.pxShowDetails</x>
       </th>
      </tr>

      <!-- Results -->
      <tr if="not zobjects">
       <td colspan=":len(columns)+1">:_('query_no_result')</td>
      </tr>
      <x for="zobj in zobjects"
         var2="rowCss=loop.zobj.odd and 'even' or 'odd';
              @currentNumber=currentNumber + 1">:zobj.appy().pxViewAsResult</x>
     </table>
     <!-- The button for selecting objects and closing the popup -->
     <div if="inPopup and cbShown" align=":dleft">
      <input type="button"
             var="label=_('object_link_many'); css=ztool.getButtonCss(label)"
             value=":label" class=":css" style=":url('linkMany', bg=True)"
             onclick=":uiSearch.initiator.jsSelectMany(\
                   q, sortKey, sortOrder, uiSearch.getFiltersString(filters))"/>
     </div>
     <!-- Init checkboxes if present -->
     <script if="checkboxes">:'initCbs(%s)' % q(checkboxesId)</script>
     <script>:'initFocus(%s)' % q(ajaxHookId)</script>''')

    # Search results, as a grid (used by pxResult below)
    pxResultGrid = Px('''
     <table width="100%"
            var="modeElems=resultMode.split('_');
                 cols=(len(modeElems)==2) and int(modeElems[1]) or 4;
                 rows=ztool.splitList(zobjects, cols)">
      <tr for="row in rows" valign="middle">
       <td for="zobj in row" width=":'%d%%' % (100/cols)" align="center"
           style="padding-top: 25px"
           var2="obj=zobj.appy(); mayView=zobj.mayView()">
        <x var="@currentNumber=currentNumber + 1"
           for="column in columns"
           var2="field=column.field">:field.pxRenderAsResult</x>
       </td>
      </tr>
     </table>''')

    # Render search results
    pxResult = Px('''
     <div var="ajaxHookId='queryResult';
               layoutType='view';
               className=className|req['className'];
               klass=ztool.getAppyClass(className);
               searchName=req.get('search', '') or field.name | '';
               uiSearch=field|ztool.getSearch(className, searchName, ui=True);
               resultMode=uiSearch.getResultMode(klass, req);
               customPx=resultMode not in uiSearch.pxByMode;
               maxResults=customPx and 'NO_LIMIT' or None;
               rootHookId=uiSearch.getRootHookId();
               refInfo=ztool.getRefInfo();
               refObject=refInfo[0];
               refField=refInfo[1];
               refUrlPart=refObject and ('&amp;ref=%s:%s' % (refObject.id, \
                                                             refField)) or '';
               startNumber=req.get('startNumber', '0');
               startNumber=int(startNumber);
               sortKey=req.get('sortKey', '');
               sortOrder=req.get('sortOrder', 'asc');
               filters=uiSearch.getFiltersDict(req.get('filters'));
               queryResult=ztool.executeQuery(className, \
                 search=uiSearch.search, startNumber=startNumber, \
                 maxResults=maxResults, remember=True, sortBy=sortKey, \
                 sortOrder=sortOrder, filters=filters, refObject=refObject, \
                 refField=refField);
               zobjects=queryResult.objects;
               objects=maxResults and [z.appy() for z in zobjects];
               totalNumber=queryResult.totalNumber;
               batchSize=queryResult.batchSize;
               batchNumber=len(zobjects);
               showNewSearch=showNewSearch|True;
               newSearchUrl='%s/search?className=%s%s' % \
                   (ztool.absolute_url(), className, refUrlPart);
               showSubTitles=req.get('showSubTitles', 'true') == 'true';
               target=ztool.getLinksTargetInfo(klass);
               showHeaders=showHeaders|True;
               checkboxes=uiSearch.checkboxes;
               checkboxesId=rootHookId + '_objs';
               cbShown=uiSearch.showCheckboxes();
               cbDisplay=cbShown and 'table-cell' or 'none'"
          id=":ajaxHookId">
      <script>:uiSearch.getAjaxData(ajaxHookId, ztool, popup=inPopup and '1', \
        checkboxes=checkboxes, checkboxesId=checkboxesId, cbDisplay=cbDisplay, \
        search=searchName, searchName=searchName, startNumber=startNumber, \
        filters=filters, sortKey=sortKey, sortOrder=sortOrder, \
        totalNumber=totalNumber)</script>

      <x if="zobjects or filters"> <!-- Pod templates -->
       <table var="fields=ztool.getResultPodFields(className)"
              if="not inPopup and zobjects and fields" align=":dright">
        <tr>
         <td var="zobj=zobjects[0]; obj=zobj.appy()"
             for="field in fields" var2="fieldName=field.name"
             class=":not loop.field.last and 'pod' or ''">:field.pxRender</td>
        </tr>
       </table>

       <!-- The title of the search -->
       <p if="not inPopup">
       <x>::uiSearch.translated</x> (<span class="discreet">:totalNumber</span>)
        <x if="showNewSearch and (searchName == 'customSearch')">&nbsp;&mdash;
         &nbsp;<i><a href=":newSearchUrl">:_('search_new')</a></i>
        </x>
       </p>
       <table width="100%">
        <tr valign="top">
         <!-- Search description -->
         <td if="uiSearch.translatedDescr.strip()">
          <span class="discreet">:uiSearch.translatedDescr</span><br/>
         </td>
         <!-- (Top) navigation -->
         <td if="not customPx"
             align=":dright" width="200px">:tool.pxNavigate</td>
        </tr>
       </table>

       <!-- Results -->
       <x var="columnLayouts=ztool.getResultColumnsLayouts(className, refInfo,
                                                           searchName);
               columns=ztool.getColumnsSpecifiers(className,columnLayouts,dir);
               currentNumber=0">:uiSearch.getPx(resultMode, klass)</x>

       <!-- (Bottom) navigation -->
       <x if="not customPx">:tool.pxNavigate</x>
      </x>

      <x if="not zobjects and not filters">
       <x>:_('query_no_result')</x>
       <x if="showNewSearch and (searchName == 'customSearch')"><br/>
        <i class="discreet"><a href=":newSearchUrl">:_('search_new')</a></i></x>
      </x>
    </div>''')

    def __init__(self, search, className, tool, initiator=None):
        self.search = search
        self.name = search.name
        self.type = 'search'
        self.colspan = search.colspan
        self.className = className
        # Property "display" of the div tag containing actions for every search
        # result.
        self.showActions = search.showActions
        if search.showActions == True: self.showActions = 'block'
        if search.translated:
            self.translated = search.translated
            self.translatedDescr = search.translatedDescr or ''
        else:
            # The label may be specific in some special cases
            labelDescr = ''
            if search.name == 'allSearch': label = '%s_plural' % className
            elif search.name == 'customSearch': label = 'search_results'
            elif (not search.name or search.klass): label = None
            else:
                label = '%s_search_%s' % (className, search.name)
                labelDescr = label + '_descr'
            _ = tool.translate
            self.translated = label and _(label) or ''
            self.translatedDescr = labelDescr and _(labelDescr) or ''
        # Strip the description (a single space may be present)
        self.translatedDescr = self.translatedDescr.strip()
        # An initiator instance if the query is in a popup
        self.initiator = initiator
        # When query results are shown in a popup, checkboxes must be present
        # even when not shown. Indeed, we want them in the DOM because object
        # ids are stored on it.
        if initiator:
            self.checkboxes = True
            self.checkboxesDefault = False
        else:
            self.checkboxes = search.checkboxes
            self.checkboxesDefault = search.checkboxesDefault

    def getRootHookId(self):
        '''If there is an initiator, return the hook as defined by it. Else,
           return the name of the search.'''
        if not self.initiator:
            return self.name or 'search'
        else:
            return self.initiator.popupHook

    def getAllResultModes(self, klass):
        '''How must we show the result? As a list, grid, or a custom px ?'''
        return getattr(klass, 'resultModes', ('list',))

    def getResultMode(self, klass, req):
        '''Get the current result mode'''
        res = req.get('resultMode')
        if not res: res = self.getAllResultModes(klass)[0]
        return res

    def getPx(self, mode, klass):
        '''What is the PX to show, according to the current result p_mode?'''
        if mode in UiSearch.pxByMode:
            return getattr(UiSearch, UiSearch.pxByMode[mode])
        # It must be a custom PX on p_klass
        return getattr(klass, mode)

    def showCheckboxes(self):
        '''When must checkboxes be shown ?'''
        if not self.initiator: return self.checkboxes
        return self.initiator.showCheckboxes()

    def getCbJsInit(self, hookId):
        '''Returns the code that creates JS data structures for storing the
           status of checkboxes for every result of this search.'''
        default = self.checkboxesDefault and 'unchecked' or 'checked'
        return '''var node=findNode(this, '%s');
                  node['_appy_objs_cbs'] = {};
                  node['_appy_objs_sem'] = '%s';''' % (hookId, default)

    def getFiltersDict(self, filterData):
        '''Converts p_filterData as encoded in the request to a dict'''
        return sutils.getDictFrom(filterData)

    def getFiltersString(self, filters):
        '''Converts dict p_filters into its string representation'''
        if not filters: return ''
        res = []
        for k, v in filters.items():
            res.append('%s:%s' % (k, v))
        return ','.join(res)

    def getAjaxData(self, hook, ztool, **params):
        '''Initializes an AjaxData object on the DOM node corresponding to
           p_hook = the whole search result.'''
        # Complete params with default ones. For performing a complete Ajax
        # request, "className" is not needed because included in the PX name.
        # But it is requested by sub-Ajax queries at the row level.
        params['className'] = self.className
        # Add initiator-specific params
        if self.initiator:
            initatorParams = self.initiator.getAjaxParams()
            if initatorParams: params.update(initatorParams)
        # Convert params into a JS dict
        name = params['searchName']
        params = sutils.getStringFrom(params)
        px = '%s:%s:pxResult' % (self.className, name)
        return "new AjaxData('%s', '%s', %s, null, '%s')" % \
               (hook, px, params, ztool.absolute_url())

    def getAjaxDataRow(self, zobj, parentHook, **params):
        '''Initializes an AjaxData object on the DOM node corresponding to
           p_hook = a row within the list of results.'''
        hook = zobj.id
        return "new AjaxData('%s', 'pxViewAsResultFromAjax', %s, '%s', '%s')"% \
               (hook, sutils.getStringFrom(params), parentHook,
                zobj.absolute_url())

    def getModeText(self, mode, _):
        '''Gets the i18n text corresponding to p_mode'''
        if mode in UiSearch.pxByMode: return _('result_mode_%s' % mode)
        return _('custom_%s' % mode)
# ------------------------------------------------------------------------------
