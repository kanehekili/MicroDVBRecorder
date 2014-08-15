# -*- coding: utf-8 -*-
'''
Created on Sep 29, 2012

@author: matze
'''

import gtk
import gobject

class RecorderView:
    
    def __init__(self,epgProgramProvider):
    #create Window
        gtk.gdk.threads_init() ##otherwise gtk will block the threads!    @UndefinedVariable
        self.programProvider = epgProgramProvider 
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("Tiny Video Recorder")
        self.window.connect("delete_event",self._cb_Exit)
        self.window.set_border_width(5)
        # minimun size, no resize below that size
        self.window.set_size_request(680,450)
        self.window.set_resizable(True)
        mainbox = gtk.VBox(homogeneous=False, spacing=0)
        self._toolbar = RecorderToolbar(self,mainbox,epgProgramProvider)
        self._buildWidgets(mainbox)
        appIcon = epgProgramProvider.getAppIconPath()
        self.window.set_icon_from_file(appIcon)
        self.window.show_all()

    def _buildWidgets(self,mainbox):
        dataBox = gtk.HBox(homogeneous=False, spacing=0)
        mainbox.pack_start(dataBox,expand=True, fill=True, padding=0)
        channelwidget= self._createChannelWidget()
        progwidget = self._createProgramList()

        #put both lists into the data box
        dataBox.pack_start(channelwidget,expand=False, fill=False, padding=0)
        dataBox.pack_end(progwidget,expand=True, fill=True, padding=0)

        bottomPart = gtk.HBox(homogeneous=True, spacing=0)
        mainbox.pack_end(bottomPart,expand=False, fill=True, padding=10)
        widget = self._createStatusLine()
        bottomPart.pack_start(widget,expand=True, fill=True, padding=0)
        self.window.add(mainbox)
    
    
    #List on the right side    
    def _createChannelWidget(self):
        self.channelStore = gtk.ListStore(str)
        self.updateChannels(self.programProvider.getChannels())
        self.channelTreeView = gtk.TreeView(self.channelStore)
        rendererText = gtk.CellRendererText()
        column = gtk.TreeViewColumn("Station",rendererText,text=0)
        column.set_sort_column_id(0)
        self.channelTreeView.set_reorderable(True)
        self.channelTreeView.append_column(column)

        channelSelection=self.channelTreeView.get_selection();
        channelSelection.select_path(0)        
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        sw.add(self.channelTreeView)
        sw.set_size_request(200, 40)
        self.channelTreeView.get_selection().connect("changed",self._on_channel_selected)
        return sw
    
    def _on_channel_selected(self,selection):
        model, aiter = selection.get_selected()
        if not aiter:
            return False
  
        channelName = model.get_value(aiter, 0)
        programs = self.programProvider.getInfosForChannel(channelName)
        self._toolbar.resetFilterList()
        self.programTreeView.setProgrammInfo(programs)
        self.programTreeView.grab_focus()
        
    #List on the left with program info
    def _createProgramList(self):
        self.programTreeView = EpgListWidget()
        sw = gtk.ScrolledWindow()
        self.programTreeView.connect("focus-out-event", self._cb_Focusout)
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add(self.programTreeView)
        self.programTreeView.connect("row-activated",self._on_ProgramListDoubleClick)
        #contextMenu support
        self.programTreeView.connect("button-press-event",self._on_menu_context)
        self._createContextMenu()
        return sw

    def _on_ProgramListDoubleClick(self,treeview,aiter,userData):
        epgInfo = self.programTreeView.getObjectAt(aiter)
        if self.programProvider.toggleRecordInfo(epgInfo):
            self.programTreeView.toggleRecordMode(aiter)
        

    #context menu
    def _on_menu_context(self,overviewWidget ,gdkEvent):
        if gdkEvent.button==3:
            self.contextMenu.popup(None, None, None, gdkEvent.button, gdkEvent.time)
    
    def _createContextMenu(self):
        self.contextMenu=gtk.Menu()
        menuItem = gtk.MenuItem("Auto select")
        menuItem.connect("activate", self._onContextMenuAutoSelect)
        self.contextMenu.append(menuItem)
        menuItem.show()         
        menuItem = gtk.MenuItem("Recording On/Off")
        menuItem.connect("activate", self._onContextMenuToggleRecording)
        menuItem.show()
        self.contextMenu.append(menuItem)


    def _onContextMenuToggleRecording(self,widget):
        selection = self.programTreeView.get_selection()
        modelPath=selection.get_selected()
        epgInfo = self.programTreeView.getSelectedObject();
        if epgInfo and self.programProvider.toggleRecordInfo(epgInfo):
                self.programTreeView.toggleRecordMode(modelPath[1])
    
        
    def _onContextMenuAutoSelect(self,widget):
        epgInfo = self.programTreeView.getSelectedObject();
        if epgInfo:
            self.programProvider.getAutoSelector().addAutoSelectPreference(epgInfo)

    #context menu fin


    #The status line    
    def _createStatusLine(self):
        sw = gtk.ScrolledWindow();
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        statusLabelView = gtk.TextView()
        statusLabelView.set_wrap_mode(False)
        statusLabelView.set_cursor_visible(False)
        sw.set_size_request(width = 100, height = 55)
        self.statusLabel = statusLabelView.get_buffer()
        self.statusLabel.set_text("Idle")
        sw.add(statusLabelView)
        return sw

    def notifyEPGStatus(self,isRunning):
        self._toolbar.updateEPGStatus(isRunning)

    def setStatusLine(self,aString):
        self.statusLabel.set_text(aString)

    def appendToStatusLine(self,textline):
        enditer = self.statusLabel.get_end_iter()
        self.statusLabel.insert(enditer,"\n"+textline)
    

    # This callback quits the program
    def _cb_Exit(self, widget, event, data=None):
        gtk.main_quit()
        return False    
    
    #forces the list widget to get the focus
    def _cb_Focusout(self,widget,event,data=None):
        widget.grab_focus()
    
    def _select_nextDay(self):
        self.programTreeView.selectNextDay()

    def _select_previousDay(self):
        self.programTreeView.selectPreviousDay()
    
    #Public API
    def openView(self):
        gtk.main()
        #control returns if quit is called
        return 0;
 
    def updateChannels(self,channelEntries):
        self.channelStore.clear()
        for channel in channelEntries:
            self.channelStore.append([channel.getName()])
            
    '''
    Hint from the model, that the programm data has been updated
    '''
    def refreshProgrammInfos(self):
        gtk.gdk.threads_enter()#since called from a NON gtk thread! @UndefinedVariable
        self._refreshTreeView()
        gtk.gdk.threads_leave()  # @UndefinedVariable
        

    def _refreshTreeView(self):
        self._on_channel_selected(self.channelTreeView.get_selection())
        
        
    def showSelectionFiltered(self,useFilter):
        if useFilter:
            epgInfo = self.programTreeView.getSelectedObject();
            if not epgInfo:
                return;
            filterString=epgInfo.getTitleEscaped()
            
            channelmodel, channeliter = self.channelTreeView.get_selection().get_selected()
            channelName = channelmodel.get_value(channeliter, 0)
            programs = self.programProvider.searchInChannel(channelName,filterString)
            self.programTreeView.setProgrammInfo(programs)
            self.programTreeView.grab_focus()
        else:
            self._refreshTreeView()
            

        
'''
a subclass of tree view. Handles the list store and the formatting
'''            
class EpgListWidget(gtk.TreeView):
    #Column numbers of the list store
    (COL_MODE,COL_OBJECT,COL_TIME,COL_TEXT)=range(4)
    #Modes in the COL_MODE 
    (MODE_DATA,MODE_DAY_HEADER,MODE_REC,MODE_BLOCK)=range(4)
    _DAY_FG = "#FFF700"
    _DAY_BG = "#055A00"
    _ENTRY_BG ="#FFFFFF"
    _ENTRY_FG ="#000000"
    _REC_BG ="#FF0000"
    
    def __init__(self):
        gtk.TreeView.__init__(self)
        self._listStore = gtk.ListStore(int,gobject.TYPE_PYOBJECT,str,str)
        self.set_model(self._listStore)
                
        self.set_property("headers-visible", True)
        self._dayIndex=0;
        
        col_time = gtk.TreeViewColumn("Time")
        col_time.set_expand(False)
        col_time.set_spacing(0)
        render_icon = gtk.CellRendererPixbuf()
        render_time = gtk.CellRendererText()
        col_time.pack_start(render_icon, False)
        col_time.pack_end(render_time, True)
        col_time.set_cell_data_func(render_time, self._get_time_data, None)
        col_time.set_cell_data_func(render_icon, self._get_rec_icon, None)
        self.append_column(col_time)
        
        render_description = gtk.CellRendererText()        
        col_description = gtk.TreeViewColumn("Program",render_description)
        col_description.set_cell_data_func(render_description, self._get_description_data, None)
        self.append_column(col_description)
        #actions
        self.get_selection().set_select_function(self._on_aboutToSelect,self._listStore)
        self.set_enable_search(True)
        self.set_search_equal_func(self._onSearchItems)
        self.set_flags(gtk.CAN_FOCUS | gtk.CAN_DEFAULT)
        
    
    def _onSearchItems(self,model,columnNumber,searchString,aiter):
        epgInfo = model[aiter][self.COL_OBJECT]
        title= epgInfo.getTitleEscaped()
        #True= get the next entry -False: thats the entry
        #at this point the selection has been removed. No selection available
        #works - but does not make sense...        
        found = searchString in title
        return not found

   
    def _get_rec_icon(self, column, cell, model, aiter, user_data=None):
        mode = model[aiter][self.COL_MODE]
        cell.set_property("width",15)
        if mode == self.MODE_REC:
            cell.set_property("stock-id", gtk.STOCK_MEDIA_RECORD)
        elif mode == self.MODE_BLOCK:
                cell.set_property("stock-id", "record")#TODO: maybe another icon??
        else:
            cell.set_property("stock-id", None)
        
    def _get_time_data(self, column, cell, model, aiter, user_data=None):
        mode = model[aiter][self.COL_MODE]
        if mode == self.MODE_DAY_HEADER:
            cell.set_property("text", "")
            cell.set_property("background",self._DAY_BG)
        else:
            time = model[aiter][self.COL_TIME]
            cell.set_property("text", time)
            if mode == self.MODE_REC:
                cell.set_property("background",self._REC_BG)
            else:
                cell.set_property("background",self._ENTRY_BG)
        
    ##wird häufig aufgerufen, bei jedem Mouse move... formatting ggf doch vorher.
    def _get_description_data(self, column, cell, model, aiter, user_data=None):
        mode = model[aiter][self.COL_MODE]
        if mode == self.MODE_DAY_HEADER:
            formatted = model[aiter][self.COL_TIME] 
            cell.set_property("markup", formatted)
            cell.set_property("foreground",self._DAY_FG)
            cell.set_property("background",self._DAY_BG)
        else:
            formatted = model[aiter][self.COL_TEXT]
            cell.set_property("foreground",self._ENTRY_FG)
            cell.set_property("background",self._ENTRY_BG)
            cell.set_property("markup", formatted)

    def setProgrammInfo(self,epgList):
        
        self._searchIndex=0
        
        self._dayPaths=[]
        store = self._listStore
        store.clear();
        
        if len(epgList)==0:
            return

        cnt=-1
        for singleDayList in epgList:
            cnt=cnt+1
            self._dayPaths.append(cnt)
            data = self._formatHeader(singleDayList[0])
            store.append(data)
            for epgInfo in singleDayList:
                cnt=cnt+1
                recmode = self.MODE_DATA
                if epgInfo.isMarkedForRecord():
                    recmode = self.MODE_REC
                elif epgInfo.isBlockedForRecord():
                    recmode =self.MODE_BLOCK
                data = self._formatProgramRow(epgInfo, recmode)
                store.append(data)

        
        self._dayIndex = min(self._dayIndex,len(self._dayPaths)-1)        
        if self.window is not None:
            self._scrollToDayPath()

    def _formatHeader(self,epgInfo):
        header = epgInfo.getStartTime().strftime("%A %d %B")
        headerText = "<b>%s</b>" % header
        return [self.MODE_DAY_HEADER,epgInfo,headerText,""]
        
    def _formatProgramRow(self,epgInfo,aMode):
        time = epgInfo.getStartTime().strftime("%H:%M")
        title = epgInfo.getTitleEscaped()
        duration = str(epgInfo.getDuration())
        description = epgInfo.getDescriptionEscaped() 
        text = "<b>%s</b>\n%s<small><i> Duration: %s</i></small>" % (title, description, duration)
        return [aMode,epgInfo,time,text] 
                
 
    def getObjectAt(self,aiter):
        progModel = self._listStore
        return progModel[aiter][self.COL_OBJECT]
    
    def getSelectedObject(self):
        selection = self.get_selection()
        model,aiter=selection.get_selected()
        if not aiter:
            return None
        return model[aiter][self.COL_OBJECT] 
        
    
    def getSelectedIndex(self):
        selection = self.get_selection()
        model,aiter=selection.get_selected()
        if not aiter:
            return 0;
        return model.get_path(aiter)[0]
 
       
    ##actions
    def _on_aboutToSelect(self, aiter,model):
        mode = model[aiter][self.COL_MODE]
        if mode == self.MODE_DAY_HEADER: 
            return False
        return True

    def toggleRecordMode(self, aiter):
        model = self.get_model()
        mode = model[aiter][self.COL_MODE]
        if mode == self.MODE_DATA:
            model[aiter][self.COL_MODE]=self.MODE_REC
        else:
            model[aiter][self.COL_MODE]=self.MODE_DATA

    def selectNextDay(self):
        self._dayIndex = min(self._dayIndex+1,len(self._dayPaths)-1)
        self._scrollToDayPath()


    def selectPreviousDay(self):
        self._dayIndex = max(self._dayIndex-1,0)
        self._scrollToDayPath()    
        
    
    def _scrollToDayPath(self):
        if self._dayIndex < 0:
            return
        path = self._dayPaths[self._dayIndex]
        selection = self.get_selection()
        selection.select_path(path+1)
        self.scroll_to_cell(path,column=None, use_align=True, row_align=0.0, col_align=0.0)



class EPGOverviewWidget(gtk.TreeView):
    (COL_TIME,COL_TEXT,COL_OBJECT)=range(3)

    _ENTRY_BG ="#FFFFFF"
    _ENTRY_FG ="#000000"
    
    def __init__(self):
        gtk.TreeView.__init__(self)
        listStore = gtk.ListStore(str,str,gobject.TYPE_PYOBJECT)
        self.set_model(listStore)
#        self.prev_selection = None
        self.set_property("headers-visible", True)
        self._dayIndex=0;
        
        col_time = gtk.TreeViewColumn("Time")
        col_time.set_expand(False)
        col_time.set_spacing(0)
        render_icon = gtk.CellRendererPixbuf()
        render_time = gtk.CellRendererText()
        col_time.pack_start(render_icon, False)
        col_time.pack_end(render_time, True)
        col_time.set_cell_data_func(render_time, self._get_time_data, None)
        col_time.set_cell_data_func(render_icon, self._get_rec_icon, None)
        self.append_column(col_time)
    
        render_description = gtk.CellRendererText()        
        col_description = gtk.TreeViewColumn("Program",render_description)
        col_description.set_cell_data_func(render_description, self._get_description_data, None)
        self.append_column(col_description)
        

    def _get_rec_icon(self, column, cell, model, aiter, user_data=None):
        cell.set_property("width",15)
        cell.set_property("stock-id", "record") #courtesy RecorderToolbar
        
    def _get_time_data(self, column, cell, model, aiter, user_data=None):
        time = model[aiter][self.COL_TIME]
        cell.set_property("markup", time)
        
    def _get_description_data(self, column, cell, model, aiter, user_data=None):
        formatted = model[aiter][self.COL_TEXT]
        cell.set_property("foreground",self._ENTRY_FG)
        cell.set_property("background",self._ENTRY_BG)
        cell.set_property("markup", formatted)
        

    def setProgrammInfo(self,epgList):
        store = self.get_model()
        store.clear();
        if len(epgList)>0:
            for epgInfo in epgList:
                data = self._formatProgramRow(epgInfo)
                store.append(data)

    def _formatProgramRow(self,epgInfo):
        theDay= epgInfo.getStartTime().strftime("%a %d")
        start = epgInfo.getStartTime().strftime("%H:%M-")
        end = epgInfo.getEndTime().strftime("%H:%M")
        channel = epgInfo.getChannel().getName()
        formatTime = "<b>%s</b><i> %s</i>\n%s%s" % (channel,theDay,start,end)
        
        title = epgInfo.getTitleEscaped()
        description = epgInfo.getDescriptionEscaped()
        jobid = epgInfo.getJobID()
        if len(jobid)>0:
            text = "<b>%s</b>\n%s <i>(%s)</i>" % (title, description,jobid)
        else:
            text = "<b>%s</b>\n%s" % (title, description)
        return [formatTime,text,epgInfo] 
    
    def getSelectedObject(self):
        selection = self.get_selection()
        model,aiter=selection.get_selected()
        return model[aiter][self.COL_OBJECT]          

'''
Defines and handles the toolbar stuff
'''
class RecorderToolbar:
    ui = '''<ui>
    <toolbar name="Toolbar">
      <toolitem action="Quit"/>
      <toolitem action="SaveHTML"/>
      <separator/>
      <toolitem action='RecordList'/>
      <toolitem action='AutoSelectList'/>
    </toolbar>
    <toolbar name="ToolbarRight">  
      <toolitem action='Series'/>
      <separator/>
      <toolitem action='PrevDay'/>
      <toolitem action='NextDay'/>
      <separator/>
      <toolitem action='RefreshEPG'/>      
    </toolbar>
    </ui>'''

    def __init__(self,recView,mainBox,progProvider):
        self.recorderView = recView
        self._progProvider = progProvider
        self.setFactoryIcons(progProvider)
        self._defineYourself(recView.window,mainBox)
    
    def setFactoryIcons(self,progProvider):
    
        goDownPath = progProvider.getIconPath('go-down.svg')
        goUpPath = progProvider.getIconPath('go-up.svg')
        refreshPath = progProvider.getIconPath('view-refresh.svg')
        recordPath = progProvider.getIconPath('multimedia.svg')
        savePath = progProvider.getIconPath('save.svg')
        exitPath = progProvider.getIconPath('exit.svg')
        seriesPath = progProvider.getIconPath('filter_list.png')
        asList= progProvider.getIconPath('open_folder.png')
        icoPaths = [goDownPath,goUpPath,refreshPath,recordPath,savePath,exitPath,seriesPath,asList]
        icoKeys = ["goDown","goUp","refresh","record","save","exit","filtericon","autoSelectList"]

        for key in icoKeys:
            items = [(key, '_GTK!', 0, 0, '')]
            gtk.stock_add(items)
                 
        # Register our stock items
        
        # Add our custom icon factory to the list of defaults
        factory = gtk.IconFactory()
        factory.add_default()
        
        try:
            for index,path in enumerate(icoPaths):
                pixbuf = gtk.gdk.pixbuf_new_from_file(path)  # @UndefinedVariable
                #pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(path,64,64)
                # Register icon to accompany stock item
                icon_set = gtk.IconSet(pixbuf)
                key = icoKeys[index]
                factory.add(key, icon_set)

        except gobject.GError, error:
            print 'failed to load GTK logo for toolbar',error


        
    def _defineYourself(self,window,mainBox):
        uiManager = gtk.UIManager()
        accelgroup = uiManager.get_accel_group()
        window.add_accel_group(accelgroup)
        
        # Create an ActionGroup
        actiongroup = gtk.ActionGroup('Recorder')
        self.actiongroup = actiongroup

        actionDefinitions =[
            # key      icon           Menutxt      key    The tooltip!      callback
            ('Quit', "exit", '_Quit me!', None,'Quit the Program', self.cb_quit),
            ('SaveHTML',"save",'Save HTML',None,'Save EPG Data as HTML',self.cb_saveHTML),
            ('RecordList',"record",'RecList','<Control>r','The Recording List',self.cb_showRecordList),
            ('AutoSelectList',"autoSelectList",'Auto Select List',None,'The auto select List',self.cb_showAutoSelectList),
            ('RefreshEPG',"refresh",'Refresh',None,'Update program guide',self.cb_refreshEPGInfo),
            ('PrevDay',"goUp",'Prev',None,'Previous day',self.cb_previousDay),
            ('NextDay',"goDown",'Next',None,'Next Day',self.cb_nextDay)            
        ]
        toggleDefinitions = [
            ('Series','filtericon','Filter',None,'Filter for selected item',self.cb_selectSeries)
        ]
        actiongroup.add_actions(actionDefinitions)
        actiongroup.add_toggle_actions(toggleDefinitions)
        # Add the actiongroup to the uimanager
        uiManager.insert_action_group(actiongroup, 0)
        # Add a UI description
        uiManager.add_ui_from_string(self.ui)
        toolbar = uiManager.get_widget('/Toolbar')
        toolbar2 = uiManager.get_widget('/ToolbarRight')
        table = gtk.Table(rows=1, columns=3, homogeneous=True)
        table.attach(child= toolbar,left_attach =0,right_attach=2,
                     top_attach=0,bottom_attach=1,xoptions=gtk.EXPAND | gtk.FILL,yoptions=0,
                     xpadding=0, ypadding=0)

        table.attach(child= toolbar2,left_attach =2,right_attach=3,
                     top_attach=0,bottom_attach=1,xoptions=gtk.SHRINK | gtk.FILL,yoptions=0,
                     xpadding=0, ypadding=0)
        mainBox.pack_start(table, False)   
        
        self.uimgr=uiManager
          
    def cb_quit(self,action):
        print "Quit"
        self.recorderView._cb_Exit(self.recorderView.window,None)

    def cb_saveHTML(self,action):
        print "Save html"
        #self.recorderView.channelTreeView.get_selection()
        #channel = self.recorderView.getChannelSelected()
        #self._progProvider.saveHTML(self)

    def cb_showRecordList(self,action):
        dlg= RecorderDialog(self._progProvider.getRecordQueue())
        dlg.showData()
        if dlg.hasChangedList():
            self.recorderView._refreshTreeView()

    def cb_showAutoSelectList(self,action):
        asList= self._progProvider.getAutoSelector().getAutoSelectionList()
        dlg=AutoSelectDialog(asList,self._progProvider)
        dlg.showData()
    
    
    def cb_refreshEPGInfo(self,action):
        self._progProvider.readEPGDeviceData()
       

    def cb_selectSeries(self,action):
        active = action.get_active()
        self.recorderView.showSelectionFiltered(active)
        

    def cb_previousDay(self,action):
        self.recorderView._select_previousDay()

    def cb_nextDay(self,action):
        self.recorderView._select_nextDay()

    def updateEPGStatus(self,isRunning):
        btn = self.uimgr.get_widget('/ToolbarRight/RefreshEPG')
        btn.set_sensitive(not isRunning)
    
    #called by the view if another channel has been selected
    def resetFilterList(self):
        btn = self.uimgr.get_widget('/ToolbarRight/Series')
        btn.set_active(False)
    
        

'''
Shows a preview of all recorded items
Removes any recorded entry, even if it is running on dbleclick
'''
class RecorderDialog:
    _DAY_FG = "#FFF700"
    _DAY_BG = "#055A00"
    def __init__(self,recordQueue):
        self.dialog = gtk.Dialog("Recording list",
                   None,
                   gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                   (gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        self._changedRecordList=False
        lbl = gtk.Label("Double click item to cancel recording")
        bx=gtk.EventBox()
        bx.add(lbl)
        bx.modify_bg(gtk.STATE_NORMAL,bx.get_colormap().alloc_color(self._DAY_BG))
        lbl.modify_fg(gtk.STATE_NORMAL,bx.get_colormap().alloc_color(self._DAY_FG))
        scrolled_window= self.createList(recordQueue)
        self.dialog.vbox.pack_start(bx,expand=False,fill=True,padding=1)
        self.dialog.vbox.pack_start(scrolled_window)
        self.dialog.set_size_request(width = 400, height = 400)
        self.dialog.show_all()
        
        
    def createList(self,recordQueue):
        listWindow = EPGOverviewWidget()
        listWindow.connect("row-activated",self._on_ProgramListDoubleClick,recordQueue)
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add(listWindow)
        listWindow.setProgrammInfo(recordQueue.getEpgList())
        return sw 


    def _on_ProgramListDoubleClick(self,treeView,storePath,userData,recordQueue):
        progModel =treeView.get_model() 
        aTreeIter = progModel.get_iter(storePath)
        epgInfo = progModel[storePath][EPGOverviewWidget.COL_OBJECT]

        if epgInfo.isMarkedForRecord():
            recordQueue.cancelRecording(epgInfo,force=True)
            progModel.remove(aTreeIter)
            self._changedRecordList=True


    def hasChangedList(self):
        return self._changedRecordList

         
    def showData(self):
        result = self.dialog.run()
        self.dialog.destroy()
        return result
  
#shows the "autoselect" entries - a CList example  
class AutoSelectDialog:    
    _DAY_FG = "#FFF700"
    _DAY_BG = "#055A00"
    def __init__(self,asList,programProvider):
        self.dialog = gtk.Dialog("Auto select list",
                   None,
                   gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                   (gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        self._changedList=False
        self._progProvider=programProvider
        lbl = gtk.Label("Double click item to remove item")
        bx=gtk.EventBox()
        bx.add(lbl)
        bx.modify_bg(gtk.STATE_NORMAL,bx.get_colormap().alloc_color(self._DAY_BG))
        lbl.modify_fg(gtk.STATE_NORMAL,bx.get_colormap().alloc_color(self._DAY_FG))
        scrolled_window= self.createList(asList)
        self.dialog.vbox.pack_start(bx,expand=False,fill=True,padding=1)
        self.dialog.vbox.pack_start(scrolled_window)
        self.dialog.set_size_request(width = 400, height = 400)
        self.dialog.show_all()

    def createList(self,asList):
        titles=["Hour","Channel","Name"]
        listWindow = gtk.CList(3,titles)
        listWindow.set_shadow_type(gtk.SHADOW_OUT)
        listWindow.set_column_width(0,60)
        for autoSelection in asList:
            listWindow.append([autoSelection.getHourListString(),autoSelection.getChannelID(),autoSelection.getTitle()]);#TODO: escape

        listWindow.connect("select_row",self._on_Selection,asList)
        listWindow.set_selection_mode( 'browse' )#Selected if present
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add(listWindow)
        return sw 
       
    def _on_Selection(self,clist,row,column,event,aList):
        #a selection has been made - only double click is relevant
        data = clist.get_text(row,0)
        title = clist.get_text(row,2)
        chan = clist.get_text(row,1)
        if event and event.type == gtk.gdk._2BUTTON_PRESS:  # @UndefinedVariable
            self._progProvider.getAutoSelector().removeFromAutoSelectPreference(data,title,chan)
            clist.remove(row);
            

    def showData(self):
        result = self.dialog.run()
        self.dialog.destroy()
        return result        
        