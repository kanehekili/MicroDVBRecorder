# -*- coding: utf-8 -*-
'''
Created on Oct 4, 2012
List that handles the epg info that should be recorded.
Communicates with Frontend by reclist. The reclist might be altered by the frontend, therefore each access
needs to get the actual data.
@author: matze
'''
from datetime import datetime, timedelta
from Configuration import MessageListener
from EpgReader import EpgReader,EpgReaderPlugin, EpgProgramInfo
import OSTools
import itertools
from itertools import tee


class RecordQueue():
    MAINT_DAY = 60*60*24+120
    def __init__(self,channelList,config):
        self._config = config
        self._channelList=channelList
        RecordingInfo.REC_MARGIN = self._config.RecordTimeMargin
    
    def addRecording(self,epgProgramInfo):
        if epgProgramInfo.isBlockedForRecord():
            return False
        recList = self.getRecList()
        if self.isInRecordingList(epgProgramInfo, recList):
            print("Oops -that should not happen (added recording twice)")
            self._config.logError("QUEUE: tried to add recording twice:"+epgProgramInfo.getString())
            self._dispatchMessage("Error: Rec entry already present")
            return False
        jobID = self._generateJobID(recList) #all items in that group should have the same id..
        epgProgramInfo.setJobID(jobID)
        recList.append(RecordingInfo(epgProgramInfo,self._config.GlueRecordings))
        self._config.logInfo("Added Recording "+str(jobID)+">"+epgProgramInfo.getString())
        self._storeRecordQueue(recList)
        return True
    
    def cancelRecording(self,epgProgramInfo,force=False):
        recList = self.getRecList()
        recInfo = self._mapToItemInRecordingList(epgProgramInfo, recList)
        if recInfo is None:
            self._config.logError("QUEUE: cancel nonexistent record?")
            print("That info can not be cancelled")
            epgProgramInfo.setJobID('')
            return False
        
        if not force:
            if epgProgramInfo.getStartTime()< datetime.today():
                msg = "No Canx: recording already running"
                self._config.logError(msg)
                self._dispatchMessage(msg)
                return False

        epgProgramInfo.setJobID("")
        recList.remove(recInfo)
        self._config.logInfo("Cancelled Recording " +epgProgramInfo.getString())
        self._storeRecordQueue(recList)
        return True

    def _mapToItemInRecordingList(self,epgInfo, recList):
        for recInfo in recList:
            if epgInfo.isAlike(recInfo.getEPGInfo()):
                return recInfo
        return None
        
    def isInRecordingList(self,epgInfo, recList):
        for recInfo in recList:
            if epgInfo.isAlike(recInfo.getEPGInfo()):
                return True
        return False

    def _calculateExecutionTime(self,recInfo):
        now = datetime.today()
        isHead = recInfo.isHead()
        isTail = recInfo.isTail()
        epgInfo = recInfo.getEPGInfo()
         
        startTime = epgInfo.getStartTime()
        endTime = epgInfo.getEndTime()
        marginStart = recInfo.marginStart
        marginEnd = recInfo.marginEnd 
         
        if isHead:
            startTime = startTime - marginStart
            if startTime < now:
                startTime = now            
        else:
            predecessorEnd = recInfo.getPredecessor().getEPGInfo().getEndTime()
            delta = startTime - predecessorEnd
            startTime = startTime - (delta/2) #in the middle of it
         
        if isTail:
            endTime = endTime+marginEnd
        else:
            succStart= recInfo.getSuccessor().getEPGInfo().getStartTime()
            delta = succStart-endTime
            endTime = endTime + (delta/2)
        
        recInfo.setExecutionTime(startTime)
         
        durance = endTime-startTime
 
        seconds = durance.days * 3600 * 24 + durance.seconds
        if seconds > (60*60*3):
            self._config.logError("Large recording > 3 hours!")   
        if seconds < 0:
            self._config.logError("Recording in the past...")
        else:
            recInfo.setDurance(seconds)


    def _generateJobID(self,recList):
        jobId =1
        for recInfo in recList:
            idString = recInfo.getEPGInfo().getJobID()
            if len(idString) > 0:
                number= int(idString)
                if number>=jobId:
                    jobId=number+1;
        if jobId >= 1000:
            jobId=1;
        
        return str(jobId)
     

    #---- block: mark those items busy, that are in the same recording slot (one device given..)
    #They may not record, since that slot is already taken
    #@param: daytoDay list of epgInfo  
    def markRecordingSlots(self,dayToDayList):
        recList=self.getRecList()
        for dailyItems in dayToDayList:
            for epgInfo in dailyItems:
                self._setRecordingMarkersToEPG(epgInfo, recList)
    
    #marks /syncs the recording data of the reclist with the epgInfo
    def _setRecordingMarkersToEPG(self,epgInfo,recList):
        for recordInfo in recList:
            recEPGInfo=recordInfo.getEPGInfo()
            if epgInfo.isAlike(recEPGInfo):
                epgInfo.setJobID(recEPGInfo.getJobID()) 
                return
            if epgInfo.overlapsWith(recEPGInfo):
                epgInfo.markBlocked(True)
                epgInfo.setJobID('')
                return
        epgInfo.setJobID('')
        epgInfo.markBlocked(False)
        
    '''
    makes sure that possibly changed epg data is in sync with the rec q.
    e.g Make sure that a moved recording gets the right time 
    '''
    def synchronizeEntries(self,infoArray):
        recList=self.getRecList()
        syncedRecList=[]
        for dayToDayList in infoArray:
            for dayList in dayToDayList:
                for epgInfo in dayList:
                    found = self.__checkForTimeShiftEntries(epgInfo, recList)
                    if found:
                        syncedRecList.append(found)

        if len(recList) != len(syncedRecList):
            self._config.logError("Recordings lost on sync!")
                                            
        self._storeRecordQueue(syncedRecList)
    
    def __checkForTimeShiftEntries(self,epgInfo,recList):
        for recordInfo in recList:
            recEPGInfo=recordInfo.getEPGInfo()
            if recEPGInfo.hasSameContent(epgInfo):
                if epgInfo.startTime ==  recEPGInfo.getStartTime():
                    return recordInfo 
                if epgInfo.isTimeShiftedWith(recEPGInfo):
                    self._config.logInfo("RecQ-timeshift:"+epgInfo.getString()+" was:"+recEPGInfo.getString())
                    epgInfo.setJobID(recEPGInfo.getJobID())
                    recordInfo._epgInfo=epgInfo
                    return recordInfo
        return None       
                                            
             
    '''
    Stores the rec queue in its own list. Should be seen by the recorder daemon,reflecting the changes
    '''
    def _storeRecordQueue(self,recList):
        wrapper=[]
        wrapper.append(recList)
        reader = EpgReader(None)
        reader.dumpEPGData(wrapper, self._config.getRecQueuePath())
    
    #interface for the recorder daemon...reads the rec queue altered by the web service
    def _readRecordQueue(self):
        reader = EpgReader(self._channelList)
        epgReaderPlug = RecReaderPlugin(self._config.GlueRecordings)
        return reader.readCachedXMLFile(epgReaderPlug,self._config.getRecQueuePath())

    def __pairwise(self,iterable):
        a, b = tee(iterable)
        next(b, None)
        return list(zip(a, b))


    def getNextRecordingEntry(self):
        top=0;
        recList = self.getRecList()
        if len(recList)<= top:
            self._config.logInfo("Empty rec list-creating maint entry")
            return self.createMaintenanceRecord()
 
        head = recList[top]
        #if exec time > 24 hrs return a maintenance entry
        if self.isMaintenanceNeeded(head):
            self._config.logInfo("RecQ: Next rec @ %s -creating maint entry" %(head.getEPGInfo().getStartTime()))
            return self.createMaintenanceRecord()
        
        if len(recList)<2:
            self._calculateExecutionTime(head)
        else:
            for pred,successor in self.__pairwise(recList):
                success= self._connect(pred, successor)
                self._calculateExecutionTime(pred)
                self._calculateExecutionTime(successor)#partly redundant, but you need the last
                if not success:
                    break               
                
        
        return head
            
    def isMaintenanceNeeded(self,recInfo):
        maintenanceDurance = 15*60;
        nextStart = OSTools.getDateTimeWithOffset(self.MAINT_DAY)
        maintEnd = OSTools.addToDateTime(nextStart, maintenanceDurance)
        scheduledStartTime = recInfo.getEPGInfo().getStartTime()
        return maintEnd <= scheduledStartTime
    
    def createMaintenanceRecord(self):
        maintenanceDurance = 15*60;
        nextStart = OSTools.getDateTimeWithOffset(self.MAINT_DAY)

        maintMsg = "creating maintenance entry for %s" %(OSTools.dateTimeAsString(nextStart))
        self._config.logInfo(maintMsg)
        print(maintMsg)
   
        maint = RecordingInfo(None);
        maint.setExecutionTime(nextStart)
        maint.setDurance(maintenanceDurance)
        return maint

    '''
    getting the embedded EPGInfo out of the rec list
    '''    
    def getEpgList(self):
        recList = self._readRecordQueue()
        #remove old entries
        now = datetime.today();#speed up
        recList[:]=[recInfo.getEPGInfo() for recInfo in recList if recInfo.getEPGInfo().isActual(now)]
        return sorted(recList, key=lambda epgInfo: epgInfo.getStartTime())
    
    #this is REC list with recording infos!
    def getRecList(self):
        recList = self._readRecordQueue()
        now = datetime.today();#speed up
        recList[:]=[recInfo for recInfo in recList if recInfo.getEPGInfo().isActual(now)]
        return sorted(recList, key=lambda recInfo: recInfo.getEPGInfo().getStartTime())
        
        

    def _dispatchMessage(self,aString):
        ml = MessageListener()
        ml.signalMessage(ml.MSG_STATUS,aString)
        

    #----------- adjacent recordings -------------
    def _connect(self,headRecInfo, newRecInfo):
        
        if headRecInfo.isPredecessorOf(newRecInfo):
            newRecInfo.setPredecessor(headRecInfo)
            headRecInfo.setSuccessor(newRecInfo)
            return True
        return False

class RecReaderPlugin(EpgReaderPlugin):
    def __init__(self,glueRecordings):
        EpgReaderPlugin.__init__(self,None,False)
        self.glueRec=glueRecordings
    
    def createEpgObject(self):
        return RecordingInfo(None,self.glueRec)     


class RecordingInfo():
    '''
        Record item takes one to n adjacent epgInfos. Used solely if films
        should be recorded immediately after the other.
        Reason:
        Since there is an overlapping of time (due to the record time margin)
        a second item has to be recorded directly after the first.
        Clip the margins where necessary and make sure the films will be recorded
        IMMEDIATElY after each other.
    '''

    REC_MARGIN=None    
    ADJACENT_BEFORE=2
    ADJACENT_AFTER=1
    
    def __init__(self,epgInfo,glueTogether=False):
        self._predecessor = None
        self._successor = None
        self._epgInfo = epgInfo
        self._duranceInSeconds=0;
        self.marginStart=self.REC_MARGIN;
        self.marginEnd=self.REC_MARGIN;
        self.glueRecs = glueTogether
    '''
    Time to start the recording (usually with a margin)
    Created when called by the daemon
    '''
    def getExecutionTime(self):
        return self._execTime
    
    def setExecutionTime(self,aTime):
        self._execTime = aTime
        
    '''
    durance of recording in seconds (usually with a margin)
    '''    
    def getDurance(self):
        return self._duranceInSeconds
    
    def getEndTime(self):
        return OSTools.addToDateTime(self._execTime, self._duranceInSeconds)
    
    def setDurance(self,seconds):
        self._duranceInSeconds = seconds
        
    def setPredecessor(self,adjInfo):
        self._predecessor = adjInfo

    def setSuccessor(self,adjInfo):
        self._successor = adjInfo
    
    def isPredecessorOf(self,otherRecInfo):
        if otherRecInfo is self:
            return False
        
        otherEPG = otherRecInfo.getEPGInfo()
        oStart = otherEPG.getStartTime()
        if self._epgInfo.getStartTime()>oStart:
            return False
        
        myEnd = self._epgInfo.getEndTime()
        delta = abs(oStart-myEnd)
        shouldBeAdjacent = delta <= (self.marginStart+self.marginEnd)
        return shouldBeAdjacent

    def isSuccessorOf(self,otherRecInfo):
        if otherRecInfo is self:
            return False
        otherEPG = otherRecInfo.getEPGInfo()
        myStart = self._epgInfo.getStartTime()
        if myStart<otherEPG.getStartTime():
            return False
        
        oEnd = otherEPG.getEndTime()
        delta = abs(oEnd-myStart)
        shouldBeAdjacent = delta <= (self.marginStart+self.marginEnd)
        return shouldBeAdjacent
    
    #removes this from the tree
    def detach(self):
        pre = self._predecessor
        if pre:
            pre.setSuccessor(None)
            self._predecessor = None
        
        post = self._successor 
        if post:
            post.setPredecessor(None)
            self._successor = None
            
        return (pre,post)

    
    def hasNeighbours(self):
        return self._successor or self._predecessor    

    def getGluedDurance(self):
        if not self.glueRecs or not self.isHead():
            return self.getDurance()
        #this makes only sense if this the head...
        items=self.getGlueList()
        dur=len(items)-1# some seconds plus 
        for rec in items:
            dur=dur+rec.getDurance()
        return dur    
    
    def getGlueList(self):
        res=[]
        recInfo = self
        while recInfo:
            res.append(recInfo)
            succ = recInfo.getSuccessor()
            if recInfo.isGluedTo(succ):
                recInfo=succ
            else:
                recInfo=None
        return res
    
   
    def isGluedTo(self,successor):
        if successor is None or not self.glueRecs:
            return False
        myChan=self.getEPGInfo().getChannel().getName()
        otherChan =successor.getEPGInfo().getChannel().getName()
        return myChan==otherChan
            
        
    def getList(self):
        treeList = []
        recInfo = self.getHead()
        while recInfo:
            treeList.append(recInfo.getEPGInfo())
            recInfo = recInfo.getSuccessor()
        
        return treeList
    
    def getHead(self):
        if self._predecessor is None:
            return self
        return self._predecessor.getHead() 
    
    def isHead(self):
        return self._predecessor is None
    
    def isTail(self):
        return self._successor is None
    
    def getTail(self):
        if self._successor is None:
            return self
        return self._successor.getTail()
    
    def getSuccessor(self):
        return  self._successor

    def getPredecessor(self):
        return self._predecessor
            
    def getEPGInfo(self):
        return self._epgInfo   
    
    def replaceInfo(self,epgInfo):
        self._epgInfo = epgInfo;
       
    def getString(self):
        if self._epgInfo:
            return self._epgInfo.getString()
        return "Maintenance @"+str(self._execTime)    

    #XML persistency 
    def storeAsXMLElement(self,builder,rootElement):
        ctSubElement = self.getEPGInfo().storeAsXMLElement(builder,rootElement)
        ctSubElement.attrib["marginStart"]=self.getMarginAsString(self.marginStart)
        ctSubElement.attrib["marginEnd"]= self.getMarginAsString(self.marginEnd)
        return ctSubElement;

    def createFromXMLElement(self,builder,program,isUTC):
        anEPG = EpgProgramInfo()
        self._epgInfo = anEPG.createFromXMLElement(builder,program,isUTC)
        mStart= program.get('marginStart')
        mStop= program.get('marginEnd')
        if mStart:
            self.marginStart=timedelta(seconds=int(mStart))
        if mStop:            
            self.marginEnd=timedelta(seconds=int(mStop))
        
        return self;
    
    def getMarginInSeconds(self,margin):
        return int(margin.total_seconds())
    
    def getMarginAsString(self,margin):
        return str(self.getMarginInSeconds(margin))

    def setMarginStart(self,seconds):
        self.marginStart=timedelta(seconds=int(seconds))

    def setMarginStop(self,seconds):
        self.marginEnd=timedelta(seconds=int(seconds))
        

    def isConsistent(self):
        return True
    