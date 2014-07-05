# -*- coding: utf-8 -*-
'''
Created on Oct 4, 2012
List that handles the epg info that should be recorded.
Communicates with Frontend by reclist. The reclist might be altered by the frontend, therefore each access
needs to get the actual data.
@author: matze
'''
from datetime import datetime
from Configuration import MessageListener
from EpgReader import EpgReader
import OSTools

class RecordQueue():
    def __init__(self,channelList,config):
        self._config = config
        self._channelList=channelList
        RecordingInfo.REC_MARGIN = self._config.RecordTimeMargin
    
    def addRecording(self,epgProgramInfo):
        if epgProgramInfo.isBlockedForRecord():
            return False
        recList = self.getEpgList()
        if self.isInRecordingList(epgProgramInfo, recList):
            print "Oops -that should not happen (added recording twice)"
            self._config.logError("QUEUE: added recording twice")
            self._dispatchMessage("Error: Rec entry already present")
            return False
        #TODO: Adding adjacent while running will truncate leading 5 mins
        jobID = self._generateJobID(recList) #all items in that group should have the same id..
        epgProgramInfo.setJobID(jobID)
        recList.append(epgProgramInfo)
        self._config.logInfo("Added Recording "+str(jobID)+">"+epgProgramInfo.getString())
        self._storeRecordQueue(recList)
        return True
    
    def cancelRecording(self,epgProgramInfo,force=False):
        recList = self.getEpgList()
        recInfo = self._mapToItemInRecordingList(epgProgramInfo, recList)
        if recInfo is None:
            self._config.logError("QUEUE: cancel nonexistent record?")
            print "That info can not be cancelled"
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
            if epgInfo.isAlike(recInfo):
                return recInfo
        return None
        
    def isInRecordingList(self,epgInfo, recList):
        for recInfo in recList:
            if epgInfo.isAlike(recInfo):
                return True
        return False

    def _calculateExecutionTime(self,recInfo):
        now = datetime.today()
        isHead = recInfo.isHead()
        isTail = recInfo.isTail()
        epgInfo = recInfo.getEPGInfo()
         
        startTime = epgInfo.getStartTime()
        endTime = epgInfo.getEndTime()
        marginStart = self._config.RecordTimeMargin
        marginEnd = self._config.RecordTimeMargin 
         
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
            seconds = 60*60*3 
            self._config.logError("More than 3 hours will jam the disc!")   
        if seconds < 0:
            self._config.logError("Recording in the past...")
        else:
            recInfo.setDurance(seconds)


    def _generateJobID(self,recList):
        jobId =1
        for epgInfo in recList:
            idString = epgInfo.getJobID()
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
        recList=self.getEpgList()
        for dailyItems in dayToDayList:
            for epgInfo in dailyItems:
                self._updateRecordingInfos(epgInfo, recList)
    
    #syncs the recoding data of the reclist with the epgInfo
    def _updateRecordingInfos(self,epgInfo,recList):
        for recordInfo in recList:
            if epgInfo.isAlike(recordInfo):
                epgInfo.setJobID(recordInfo.getJobID()) 
                return
            if epgInfo.overlapsWith(recordInfo):
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
        recList=self.getEpgList()
        syncedRecList=[]
        for dayToDayList in infoArray:
            for dayList in dayToDayList:
                for epgInfo in dayList:
                    if self.__makeConsistent(epgInfo, recList):
                        syncedRecList.append(epgInfo)

        if len(recList) != len(syncedRecList):
            self._config.logError("Recordings lost on sync!")
                                            
        self._storeRecordQueue(syncedRecList)
    
            
  
    def __makeConsistent(self,epgInfo,recList):
        for recordInfo in recList:
            if epgInfo.isAlike(recordInfo):
                epgInfo.setJobID(recordInfo.getJobID()) 
                return True #handled
            
            if epgInfo.isTimeShiftedWith(recordInfo):
                #rec info changed...replace it
                self._config.logInfo("Rec entry changed to:"+epgInfo.getString())
                epgInfo.setJobID(recordInfo.getJobID())
                return True #handled
        return False   
                

             
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
        return reader.readCachedXMLFile(self._config.getRecQueuePath())

    #TODO:? generate a "FAKE" entry if the next is more than 24 h away.
    def getNextRecordingEntry(self,index=0):
        recList = self.getEpgList()
        if len(recList)<= index:
            return None;
 
        head = RecordingInfo(recList[index])
        #if exec time > 24 hrs return a maintenance entry
        if self.isMaintenanceNeeded(head):
            return self.createMaintenanceRecord()
        
        if len(recList)>index+1:
            successor = RecordingInfo(recList[index+1])
            self._connect(head, successor)
        
        self._calculateExecutionTime(head)
        return head
            
    def isMaintenanceNeeded(self,recInfo):
        startTime = recInfo.getEPGInfo().getStartTime()
        deltaToNextSchedule = OSTools.getDifferenceInSeconds(startTime, datetime.now())
        aDay = 60*60*24;
        return deltaToNextSchedule > aDay
    
    def createMaintenanceRecord(self):
        self._config.logInfo("creating a maintenance rec entry")
        aDay = 60*60*24;
        nextStart = OSTools.getDateTimeWithOffset(aDay)
        maint = RecordingInfo(None);
        maint.setExecutionTime(nextStart)
        maint.setDurance(60*5)
        return maint

    
    def getEpgList(self):
        recList = self._readRecordQueue()
        #remove old entries
        recList[:]=[epgInfo for epgInfo in recList if epgInfo.isActual()]
        return sorted(recList, key=lambda epgInfo: epgInfo.getStartTime())
    

    def _dispatchMessage(self,aString):
        ml = MessageListener()
        ml.signalMessage(ml.MSG_STATUS,aString)
        

    #----------- adjacent recordings -------------
    def _connect(self,headRecInfo, newRecInfo):
        
        if headRecInfo.isPredecessorOf(newRecInfo):
            newRecInfo.setPredecessor(headRecInfo)
            headRecInfo.setSuccessor(newRecInfo)

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
    
    def __init__(self,epgInfo):
        self._predecessor = None
        self._successor = None
        self._epgInfo = epgInfo
        self._duranceInSeconds=0;
    '''
    Time to start the recording (usually with a margin)
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
        shouldBeAdjacent = delta <= 2*self.REC_MARGIN
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
        shouldBeAdjacent = delta <= 2*self.REC_MARGIN
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
        return self._epgInfo.getString()    

