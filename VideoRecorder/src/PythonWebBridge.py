#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
Created on Aug 15, 2013
Interface/data provider for the web service.
@author: matze
'''

from ChannelReader import ChannelReader
import DVBDevice
from EPGProgramProvider import EPGProgramProvider
from Configuration import Config, MessageListener
import json
import OSTools
import os
import mimetypes
import codecs
from importlib.resources import path

class WebRecorder():
    '''
    API methods are called by the RecorderPlugin in the RecorderWebService module.
    '''
    # signal modes
    # TODO change mode to STATUS und ERROR...
    MSG_STATUS = MessageListener.MSG_STATUS
    # MSG_EPG = MessageListener.MSG_EPG
    MSG_REFRESH = MessageListener.MSG_REFRESH
    
    # Modes or types of rec? 
    (MODE_DATA, MODE_REC, MODE_BLOCK) = list(range(0xA0, 0xA3))
    (TYPE_HEAD, TYPE_PROG, TYPE_INFO) = list(range(3))



    def __init__(self):
        '''
        starts the app
        '''
        self.configuration = Config()
        self.configuration.setupLogging("webdvb.log")
        
        self._lastMessage = None
        ml = MessageListener();
        ml.addListener(ml.MSG_STATUS, self.storeLastMessage)
        # ml.addListener(ml.MSG_EPG, this.storeLastMessage)
        ml.addListener(ml.MSG_REFRESH, self.storeLastMessage)
        
        channelReader = ChannelReader()
        cPath = self.configuration.getChannelFilePath()

        channelReader.readChannels(cPath)
        self.channelList = channelReader.getChannels()
        self.progProvider = EPGProgramProvider(self, self.channelList, self.configuration)
        self._lastEpgRead = 0.0
        # self._readCachedEpgData()
        self.checkEPGData()
  

  
    def _readCachedEpgData(self):
        ml = MessageListener();
        if not self.channelList:
            ml.signalMessage(self.MSG_STATUS, "Where is that channel.conf? RTF!")
            return

        ml.signalMessage(self.MSG_STATUS, "Reading programm info")
        msg = "Idle"
        try:
            self.progProvider.readEPGCache()
            ml.signalMessage(self.MSG_REFRESH, "Program info read")  # enforces a new list
        except IOError:
            msg = "No EPG data"
        except Exception as ex:
            msg = "Error reading cached EPG Data: " + str(ex.args[0])
            self.configuration.getLogger().exception(msg)
            print(msg)
        self.configuration.logInfo(msg)                        
        ml.signalMessage(self.MSG_STATUS, msg)
        
    def _getEPGDevice(self):
        return DVBDevice.getGrabber(self.channelList, self.configuration)

    def _collectEPGFromDevice(self):
        epgUpdater = self.progProvider.getEPGUpdater()
        self._updater.updateDatabase();
        if epgUpdater.hasError():
            MessageListener().signalMessage(self.MSG_STATUS, epgUpdater.getErrorMessage())
        
    '''
    API to Recorder plugin
    Basic idea: should be json objects
    '''    

    def storeLastMessage(self, message):
        self._lastMessage = message
    
    def getLastSignal(self):
        msg = self._lastMessage
        self._lastMessage = None
        return msg
    
    
    def readEPGDeviceData(self):
        self._collectEPGFromDevice()

    def getChannelList(self):
        channelNames = []
        for channel in self.channelList:
            channelNames.append(channel.getName())
        jchannels = json.dumps(channelNames)
        return jchannels  

    def getProgrammInfoForChannel(self, aChannelString):
        daytoDayList = self.progProvider.getInfosForChannel(aChannelString)
        jDayToDayArray = self._formatProgramList(daytoDayList)
        jInfos = json.dumps(jDayToDayArray)
        return jInfos
    
    def toggleRecordMode(self, jsonString):
        jsonDict = json.loads(jsonString)
        epgInfo = self._lookupEPGInfoFromJSON(jsonDict)
        forceRemove = jsonDict["type"] == self.TYPE_INFO;
        if epgInfo is not None:
            self.progProvider.toggleRecordInfo(epgInfo, forceRemove)
            result = self._formatProgramRow(epgInfo)
        else:
            jsonDict["error"] = "Entry not found"
            result = jsonDict
        if self._lastMessage is not None:
            result["error"] = self.getLastSignal()    
        return json.dumps(result)    

    def getFilterList(self, searchTuple):
        channelName = searchTuple[0]
        filterString = searchTuple[1]
        epgInfoList = self.progProvider.searchInChannel(channelName, filterString)
        jDayToDayArray = self._formatProgramList(epgInfoList)
        return json.dumps(jDayToDayArray)
        

    def getAutoSelectList(self):
        autoselectList = self.progProvider.getAutoSelector().getAutoSelectionList();
        
        jList = self._formatAutoSelectList(autoselectList)
        return json.dumps(jList)

        
    def addToAutoSelection(self, jsonString):
        jsonDict = json.loads(jsonString)
        epgInfo = self._lookupEPGInfoFromJSON(jsonDict)
        autoSelector = self.progProvider.getAutoSelector() 
        autoSelector.addAutoSelectPreference(epgInfo)
        autoSelector.saveAutoSelectData()

    def saveAutoSelectionSetting(self, jsonString):
        # weekmode has changed. single entry. update & save
        jsonDict = json.loads(jsonString)
        hourString = jsonDict["timetext"]
        # Text is unicode!!
        titleString = jsonDict["text"]
        channelName = jsonDict["chanID"]
        weekModeString = jsonDict["weekMode"]
        
        autoSelector = self.progProvider.getAutoSelector()
        autoSelector.updateWeekMode(hourString, titleString, channelName, weekModeString)
        autoSelector.saveAutoSelectData()

    def removeFromAutoSelection(self, jsonString):
        # NOTE: json makes unicode out of the string
        jsonDict = json.loads(jsonString)
        hourString = jsonDict["timetext"]
        titleString = jsonDict["text"]
        channelName = jsonDict["chanID"]
        autoSelector = self.progProvider.getAutoSelector()
        autoSelector.removeFromAutoSelectPreference(hourString, str(titleString), str(channelName))
        autoSelector.saveAutoSelectData()
        
    def getRecordingList(self):
        recInfoList = self.progProvider.getRecordQueue().getRecList();
        jList = self._formatRecordingList(recInfoList)
        return json.dumps(jList)
    
    
    #### dict: {u'marginStop': 600, u'marginStart': 300, u'jobID': u'1'}
    def updateRecorderMargins(self,jsonString):
        jsonList = json.loads(jsonString)
        recInfoList = self.progProvider.getRecordQueue().getRecList();
        for jEntry in jsonList:
            jobID= jEntry["jobID"]
            found = next((recEntry for recEntry in recInfoList if recEntry.getEPGInfo().getJobID()==jobID),None)
            if found:
                found.setMarginStart(jEntry["marginStart"])
                found.setMarginStop(jEntry["marginStop"])
        
        self.progProvider.getRecordQueue()._storeRecordQueue(recInfoList)

    '''
    search the database for a string
    "cmd":"SEARCH_ALL","arg":"test","data":""}
    '''    
    def searchAll(self,searchString): 
        epgInfoList = self.progProvider.searchAll(searchString)
        #jDayToDayArray = self._formatProgramList(epgInfoList)
        #return json.dumps(jDayToDayArray)
        #maybe sort them per channel?
        jDayList=[]
        for epgInfo in epgInfoList:
            jInfo = self._formatProgramRow(epgInfo);
            jDayList.append(jInfo)           
        
        errorMsg=None
        if len(jDayList) == 0:
            errorMsg = "Nothing found"     
        jAnswer = {"type":self.TYPE_INFO, "error":errorMsg,"list":jDayList}
        return json.dumps(jAnswer)
        
    '''
    reread epg info if a modification took place.If changes took place (like a daemon epg update)
    update the database 
    '''
    def checkEPGData(self):
        fileName = self.configuration.getCachedXMLTVFilePath()
        currentModificationtime = 0
        try:
            currentModificationtime = OSTools.getLastModificationTime(fileName)
        except OSError as osError:
            msg = "CheckEpgData:" + osError.strerror
            self.configuration.logError(msg)                        
            self.storeLastMessage(msg)
            return
            
#         if self._lastEpgRead is None:
#             self._lastEpgRead= currentModificationtime-100

        if currentModificationtime - self._lastEpgRead > 60:
            self._lastEpgRead = currentModificationtime
            self._readCachedEpgData()

    '''
    End of WebRecorder API
    --
    
    Helper/conversion methods -- aka WebViewGenerator?
    '''
    def _formatHeader(self, epgInfo):
        header = epgInfo.getStartTime().strftime("%A %d %B")
        headerText = "<b>%s</b>" % header
        return {"type":self.TYPE_HEAD, "text":headerText, "time":None};
                
    def _formatProgramRow(self, epgInfo):
        epgTime = epgInfo.getStartTimeString()
        epgDate = epgInfo.getDateString()
        title = epgInfo.getTitle()
        duration = str(epgInfo.getDuration())
        description = epgInfo.getDescription() 
        # TODO: Formating is client work- only the data!
        programText = "<b>%s</b><br>%s<small><i> Duration: %s</i></small>" % (title, description, duration)
        
        jobID = None
        if epgInfo.isMarkedForRecord():
            recmode = self.MODE_REC
            jobID = epgInfo.getJobID()
        elif epgInfo.isBlockedForRecord():
            recmode = self.MODE_BLOCK
        else:
            recmode = self.MODE_DATA
        return {"type":self.TYPE_PROG, "text":programText, "time":epgTime, "date":epgDate, "recordMode":recmode, "jobID":jobID, "title":title, "channel":epgInfo.getChannel().getName(), "epgOK":epgInfo.isConsistent, "error":None};

    def _formatProgramList(self, daytoDayList):
        jDayToDayArray = []
        for singleDayList in daytoDayList:
            jDayList = []
            # adds the header - setting the date only
            # TODO: Empty singleDayList! Should not happen
            if len(singleDayList) == 0:
                print("ERROR: Empty single day list")
                continue
                
            headerText = self._formatHeader(singleDayList[0])
            for epgInfo in singleDayList:
                jInfo = self._formatProgramRow(epgInfo);
                jDayList.append(jInfo)

            jDayObject = {"head":headerText, "list":jDayList};
            jDayToDayArray.append(jDayObject)
        if len(jDayToDayArray) == 0:
            return self.asJsonError("No data", self.getLastSignal())    
        return jDayToDayArray
        
    def asJsonError(self, errorMsg, argumentString):
        reason = argumentString
        if not reason:
            reason = errorMsg
        return {"type":self.TYPE_INFO, "error":errorMsg, "args":reason}

    def _lookupEPGInfoFromJSON(self, jsonData):
        aChannelString = jsonData["channel"]
        dayString = jsonData["date"]
        timeString = jsonData["time"]
        # Note JSON data always uses unicode - convert it to byte encoding it to uf8
        daytoDayList = self.progProvider.getInfosForChannel(aChannelString)
        # Well... get the right DAY first....
        for singleDayList in daytoDayList:
            if singleDayList[0].getDateString() in dayString:
                for epgInfo in singleDayList:
                    if epgInfo.getStartTimeString() in timeString:
                        return epgInfo 
        return None
    
    def _formatAutoSelectList(self, autoSelectList):
        
        jDayList = []
        for autoSelection in autoSelectList:
            timeString = autoSelection.getHourListString()
            title = autoSelection.getTitle()
            chanID = autoSelection.getChannelID()
            weekMode = autoSelection.getWeekMode()
            jInfo = {"type":self.TYPE_INFO, "timetext":timeString, "text":title, "title":title, "chanID":chanID, "weekMode":weekMode, "error":None}
            jDayList.append(jInfo)
        jsonASList = {"weekTypes":["Mo-Fri", "Sa-Su", "Mo-Su"], "elements":jDayList}    
        return jsonASList
            
    
    def _formatRecordingList(self, recInfoList):
        jDayList = []
        for recInfo in recInfoList:
            jInfo = self._formatRecordingRow(recInfo);
            jDayList.append(jInfo)
        return jDayList
    
    def _formatRecordingRow(self, recInfo):
        epgInfo = recInfo.getEPGInfo()
        epgTime = epgInfo.getStartTimeString()
        epgDate = epgInfo.getDateString()
        theDay = epgInfo.getStartTime().strftime("%a %d")
        start = epgInfo.getStartTime().strftime("%H:%M-")
        end = epgInfo.getEndTime().strftime("%H:%M")
        channel = epgInfo.getChannel().getName()
        formatTime = "<b>%s</b><i> %s</i><br><small>%s%s</small>" % (channel, theDay, start, end)
        
        title = epgInfo.getTitle()
        description = epgInfo.getDescription()
        jobID = epgInfo.getJobID()
        marginStart = recInfo.getMarginAsString(recInfo.marginStart)
        marginStop = recInfo.getMarginAsString(recInfo.marginEnd)
        if len(jobID) > 0:
            programText = "<b>%s</b><br>%s <i>(%s)</i>" % (title, description, jobID)
        else:
            programText = "<b>%s</b><br>%s" % (title, description)
        return {"type":self.TYPE_INFO, "timetext":formatTime, "text":programText, "time":epgTime, "date":epgDate, "jobID":jobID, "title":title, "channel":channel,"marginStart":marginStart,"marginStop":marginStop, "error":None};

        
'''
  This is the connector from the HTTP Server to the WebRecorder. Should only exist one instance
'''
class RecorderPlugin():
    Commands = ["REQ_Channels", "REQ_Programs", "MARK_Programm", "AUTO_SELECT", "LIST_REC", "LIST_AUTO", "FILTER", "RM_AUTOSELECT", "AUTO_WEEKMODE","REC_MARGINS","SEARCH_ALL","-Download"]
    LogPos=0
    
    ''' initial sequence
        Mimetypes will be registered on import, to avoid missing types
        they must be defined here before the SimpleHttpServer will be initialized  
    '''
    
    if not mimetypes.inited:
        mimetypes.init()  # try to read system mime.types
        mimetypes.add_type("image/svg+xml", ".svg", True)
        mimetypes.add_type("image/svg+xml", ".svgz", True)
    
    
    def __init__(self):
        print("RecorderPlugin activated")
        self.count = 0;
        self._webRecorder = WebRecorder()
        self._config = self._webRecorder.configuration

    def log(self, aString):
        self._config.logInfo(aString)
    
    def _getArgs(self, commandDic):
        return commandDic["arg"]
    
    def handleLogCommand(self,command):
        logStep=250;
        if "NXT" in command:
            self.LogPos+=logStep;
        else:
            self.LogPos=0
        self.prepareLogFile(self.LogPos,logStep)
    
    def handleFilmCommand(self,command):
        #Using the html file from the treewalker now. 
        #Position is in /web/Films.html - no needd to scan the videos currently
        #self.prepareFilmPage()
        pass
            
    
    def prepareLogFile(self,lineStart,lineCount):
        #read the log file, prepare it and put it into the log file text?
        self.log("Getting Log request")
        
        srcFile = self._config.getLoggingPath();
        srcFile = OSTools.ensureFile(srcFile, "dvb_suspend.log")
        destFile = self._config.getFilePath(self._config.getWebPath(), "Log.html")
        style ='<style>body { float:left;} div {white-space: nowrap;padding:2px;margin:0px;font-family: Helvetica, Arial, sans-serif;font-size:0.85em;} .evenrow {background-color: #F8E0D7;} .oddrow {background-color: #F8EEEE;}</style>'  

        htmlStart = '<!DOCTYPE html><html><head><meta content="text/html; charset=UTF-8">'+style+'<title>Micro Recorder Log</title><body>'
        htmlend = '--- End ---</body></html>'
        htmlmore = '<a href="./Log.html?NXT">Log more?</a></body></html>'
        htmlFilms = '<a href="./Films.html">Show Films</a>'

        with codecs.open(srcFile, 'r',encoding='utf-8') as logFile:
            logLines = logFile.readlines()
 
       
        startIndex = len(logLines)
        reqLines = lineStart+lineCount
        reqEnd = max(0,startIndex-reqLines)
        print(("start:",startIndex," to:",reqEnd))
        #aRange=reversed(range(reqEnd,startIndex))   
 
        isEven=False
        with open(destFile, 'w+') as htmlFile:
            htmlFile.write(htmlStart)
            htmlFile.write("<b> The Logs (newest first) </b>")
            htmlFile.write(htmlFilms)
            #for line in logLines:
            lineIndex = startIndex
            while lineIndex > reqEnd:
                lineIndex-=1;
                line=logLines[lineIndex]
                if isEven:
                    divid="evenrow"
                else:
                    divid="oddrow"
                htmlFile.write('<div class="'+divid+'">'+line+"</div>")
                isEven=not isEven
            if reqEnd==0:
                htmlFile.write(htmlend)
            else:
                htmlFile.write(htmlmore)      
    
    def prepareFilmPage(self):
        #Films.html has been produced by the "Treewalker" - so no need to use this anymore. 
        style ='<style>body { float:left;} div {white-space: nowrap;padding:2px;margin:0px;font-family: Helvetica, Arial, sans-serif;font-size:0.85em;} .evenrow {background-color: #F8E0D7;} .oddrow {background-color: #F8EEEE;} .back {float:right}</style>'
        htmlStart = '<!DOCTYPE html><html><head><meta content="text/html; charset=UTF-8">'+style+'<title>Recorded Films</title><body>'
        htmlend = '--- End ---</body></html>'
        htmlBack = '<div class= back><a href="./Log.html">Back to Log</a></div>'
        srcFile = self._config.getLoggingPath();
        srcFile = OSTools.ensureFile(srcFile, "Filmlist.txt")
        
        destFile = self._config.getFilePath(self._config.getWebPath(), "Films.html")
        with codecs.open(srcFile, 'r',encoding="utf-8") as logFile:
            logLines = logFile.readlines()
        
        isEven=False
        with open(destFile, 'w+') as htmlFile:
            htmlFile.write(htmlStart)
            htmlFile.write("<b> The film list</b>")
            htmlFile.write(htmlBack)
            for line in logLines:
                if isEven:
                    divid="evenrow"
                else:
                    divid="oddrow"
                hack=self.utf8ToHTMLUmlauts(line)
                htmlFile.write('<div class="'+divid+'">'+hack+"</div>")
                isEven=not isEven            
            htmlFile.write(htmlend)
        

    #can'be a good solution, but didn't find any better yet
    '''
    Update -this works:
        tmp = line.encode('ascii', 'xmlcharrefreplace') #binary
        return tmp.decode('ascii') #back to string, without 'b'
    ''' 
    def utf8ToHTMLUmlauts(self,text):
        return text.replace("ö", "&ouml;").replace("ü", "&uuml;").replace("ä", "&auml;").replace("Ö", "&Ouml;").replace("Ü", "&Uuml;").replace("Ä", "&Auml;").replace("ß", "&szlig;")
    
    # Note: arguments must be encoded to utf-8     
    def executePostData(self, jsonCmd):
        try:
            print(("Processing post data:" + jsonCmd))
            self.log("Processing post data:" + jsonCmd)
            commandDic = json.loads(jsonCmd)
            command = commandDic["cmd"]
            if command == self.Commands[0]:  # channel request
                return (self._webRecorder.getChannelList())
            if command == self.Commands[1]:  # prog request
                self._webRecorder.checkEPGData()
                channel = self._getArgs(commandDic)
                return self._webRecorder.getProgrammInfoForChannel(channel)
            if command == self.Commands[2]:  # Recording on/off
                jsonString = self._getArgs(commandDic)
                return self._webRecorder.toggleRecordMode(jsonString)
            if command == self.Commands[3]:  # AUTOSELECT DnD
                jsonString = self._getArgs(commandDic)
                return self._webRecorder.addToAutoSelection(jsonString)
            if command == self.Commands[4]:  # get rec list
                return self._webRecorder.getRecordingList()
            if command == self.Commands[5]:  # get auto select list
                return self._webRecorder.getAutoSelectList()
            if command == self.Commands[6]:  # Filter current list
                return self._webRecorder.getFilterList(commandDic["arg"])  # channel and The string
            if command == self.Commands[7]:  # Remove Autoselect entry
                jsonString = self._getArgs(commandDic)
                return self._webRecorder.removeFromAutoSelection(jsonString)  # channel and The string
            if command == self.Commands[8]:  # weekmode Autoselect entry
                jsonString = self._getArgs(commandDic)
                return self._webRecorder.saveAutoSelectionSetting(jsonString)
            if command == self.Commands[9]: #Set the margins
                jsonString = self._getArgs(commandDic)
                return self._webRecorder.updateRecorderMargins(jsonString)
            if command == self.Commands[10]: #search all channels
                jsonString = self._getArgs(commandDic)
                return self._webRecorder.searchAll(jsonString)
            
            # more:settings, download file....
            
            
        except Exception as ex:
            msg = "Error running POST data: " + str(ex.args[0])
            print(msg)
            self._config.getLogger().exception(msg)
            jsonError = self._webRecorder.asJsonError("Server Error", msg)
            return json.dumps(jsonError)
        
            
if __name__ =="__main__":
    pass
        