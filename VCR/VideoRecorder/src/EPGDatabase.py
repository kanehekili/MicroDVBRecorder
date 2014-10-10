# -*- coding: utf-8 -*-
'''
Created on Jan 2, 2013
Models the collected EPG data

Design: Using lists makes less garbage than values from dictionaries.
The database has a dictionary of channel names
Each value is an array that contains arrays of daily EPG Infos - i.e. the leaf array contains
the data of one day 

@author: matze
'''
import xml.etree.cElementTree as CT
from datetime import datetime
from EpgReader import EpgProgramInfo
import re as REGEX

class EpgDatabase:
    def __init__(self,config):
        self._channelDictionary={}
        self._config = config
        self.autoSelectAccessor = AutoSelectAccessor(config)
    
    
    '''
    A list of EpgProgrammInfos retrieved from a well formed xml file
    '''
    def setUpChannelList(self,epgInfoList):
        if len(epgInfoList)==0:
            return
        self._config.logInfo("Setup channel infos")
        channelDict = self.__createChannelDict(epgInfoList)
        for channelName,epgInfos in channelDict.items():
            dayToDayList = self._sortEpgData(epgInfos) #[][]
            #removes all empty arrays
            dayToDayList[:] = [daily for daily in dayToDayList if daily ]
            for daylist in dayToDayList:
                self._verifyListConsistency(daylist)
            self._channelDictionary[channelName]=dayToDayList
    
    '''
    A dictionary with the channel name as key and a list of EpgProgrammInfos
    but that info comes from an EPG grabber. It is not consistent and complete,so
    add missing entries
    updateEPGList -simple list of epginfos. This is the place to build everything 
    '''
    
    def updateChannelList(self,epgInfoList):
        if len(epgInfoList)==0:
            return
        self._config.logInfo("Updating channel infos")
 
        channelDict = self.__createChannelDict(epgInfoList) 
            
        for channelName,epgInfos in channelDict.items():
            dayToDayList = self._sortEpgData(epgInfos) #[][]
            #removes all empty arrays
            dayToDayList[:] = [daily for daily in dayToDayList if daily ]
            self._insertEPGData(channelName,dayToDayList)
    
    def __createChannelDict(self,epgInfoList):
        channelDict = {} 
        for epgInfo in epgInfoList:
            aChannelString = epgInfo.getChannel().getName()
            channelDict.setdefault(aChannelString,[]).append(epgInfo)

        return channelDict
        
    '''
    Answers an array of arrays of daily epg infos
    '''
    def getInfosForChannel(self,aChannelString):
        return self._channelDictionary.setdefault(aChannelString,[])
 
    '''
    Answers an array  containing an array of daily entries - per channel
    [channel [dayList [epgPerDay] ] ]
    '''
    def getData(self):
        return self._channelDictionary.values()
    
    
    def findAllInfos(self,searchString):
        someArray = self.getData();
        
        result = []
        for channelEntries in someArray:
            for dayList in channelEntries:
                for epgInfo in dayList:
                    if REGEX.search(searchString,epgInfo.getTitle(),REGEX.IGNORECASE):
                        result.append(epgInfo)
    
        return result;
    
    '''
    Answer the plain list with all values
    '''
    def getPersistenceData(self):
        plainList=[]
        for dayToDayList in self._channelDictionary.values():
            for daily in dayToDayList:
                plainList.append(daily)
        
        return plainList

    def getAutoSelector(self):
        return self.autoSelectAccessor;
    
    # non public API
    '''
    Time consuming-find a slot for each entry
    Scope: Channel-day-to-day
    '''
    def _insertEPGData(self,channelName, dayToDayList):
        for dayList in dayToDayList:
            searchDate = self._getDateFromDayList(dayList)
            dbDayList = self._getCurrentDayList(channelName,searchDate)
            if dbDayList is None:
                #adds the dayList into the day to day array
                dbDayList = self._insertToDayToDayList(channelName,dayList)
            else:
                dbDayList = self._mergeDailyEntries(dbDayList,dayList)
            self._verifyListConsistency(dbDayList)
        
            
    '''
    Scope: Channel-day-to-day
    inserts a new daily list into the array
    '''
    def _insertToDayToDayList(self,channelName,newDayList):
        startTime = newDayList[0].getStartTime()
        dayToDayList = self.getInfosForChannel(channelName)
        cnt=0
        for dayList in dayToDayList:
            checkTime=dayList[0].getStartTime()
            if checkTime > startTime:
                dayToDayList.insert(cnt,newDayList)
                cnt=-1
                break;
            cnt+=1
            
        if cnt!=-1:
            dayToDayList.append(newDayList)
        return newDayList
            
        
    '''
    merge two daily lists. The new data rules on the same time slot
    Scope: day list
    Assumption: the new daylist rules. IF there's a gap, look for it in the 
    currentList. The dbDayList will be persisted.
    '''
    def _mergeDailyEntries(self,dbDayList, newDayList):
        prevInfo = None
        mergedList=[]
        for epgInfo in newDayList:
            if self._hasTimeGap(prevInfo,epgInfo):
                self._config.logInfo("*Merge: slot missing:"+prevInfo.getString()+" -> "+epgInfo.getString())
                slots = self._getMissingSlots(dbDayList, prevInfo.getEndTime(), epgInfo.getStartTime())
                mergedList.extend(slots)
            mergedList.append(epgInfo)
            prevInfo = epgInfo
        #NO remaining slots for epg that ends the next day
        if not epgInfo.isOverMidnight():
            slots = self._getRemainingSlots(dbDayList,epgInfo.getEndTime())
            mergedList.extend(slots)
        dbDayList[:] = mergedList
        return dbDayList
    
    def __traceDayList(self,dayList):
        self._config.logInfo("--DayList --")
        for info in dayList:
            self._config.logInfo(" ++"+info.getString())
        self._config.logInfo("--END DayList --")
        
        
    #reduce info to the necessary: channel, given time
    def __getEPGLogTimeString(self,epgInfo,aTimeString ):
        aChannelString = epgInfo.getChannel().getName()
        return "["+aChannelString+"] "+aTimeString
    
    '''
    add entries that might be later
    '''
    def _getRemainingSlots(self,currentList,startTime):
        missingSlots=[]
        
        for entry in currentList:
            if not entry.isConsistent:
                continue
            if entry.getStartTime()>= startTime:
                missingSlots.append(entry)
        if len(missingSlots)>0:
                self._config.logInfo("*Merged +tail ("+str(len(missingSlots))+") starting at: "+missingSlots[0].getString())
        return missingSlots
    
    '''
    add those entries, that are missing
    '''         
    def _getMissingSlots(self,currentList, startTime, endTime ):
        missingSlots=[]
        for entry in currentList:
            if not entry.isConsistent:
                continue
            if entry.getStartTime() >= endTime:
                return missingSlots
            if entry.getStartTime() >= startTime and entry.getEndTime() <= endTime:
                self._config.logInfo("*Merge +old: "+entry.getString())
                missingSlots.append(entry)
                
        return missingSlots
                    
    def _hasTimeGap(self,prevInfo, nextInfo):
        if prevInfo is None or nextInfo is None:
            return False
        t1 = prevInfo.getEndTime()
        t2 = nextInfo.getStartTime()
        return t1 != t2
        
    #TODO:obsolete    
    def _findTimeslot(self,aList, epgInfo):
        for epg in aList:
            if epg.getStartTime()==epgInfo.getStartTime():
                return epg
        return None
            
    def _verifyListConsistency(self,mergedList):
        if len(mergedList)==0:
            return
        #TODO: Gaps from the day before and the first entry are not recognized       
        filledGapList=[]
        
        previousEpgInfo=mergedList[0]
        filledGapList.append(previousEpgInfo)
        
        for epgInfo in mergedList[1:]:
            if previousEpgInfo.getEndTime() != epgInfo.getStartTime():
                self._config.logInfo("*-Gap: "+previousEpgInfo.getString()+"->" +epgInfo.getString())
                #creates a gap info
                gapInfo = EpgProgramInfo()
                gapInfo.isConsistent=False
                gapInfo.setTitle("*- GAP -*")
                gapInfo.setDescription("No info available")
                gapInfo.setChannel(epgInfo.getChannel())
                gapInfo.setStartTime(previousEpgInfo.getEndTime())
                gapInfo.setEndTime(epgInfo.getStartTime())
                filledGapList.append(gapInfo)
            previousEpgInfo = epgInfo
            filledGapList.append(epgInfo)

        mergedList[:]=filledGapList
        
    
    #gets the first entry of the EPGInfo array and answers the search date
    def _getDateFromDayList(self,dayList):
        if len(dayList)==0:
            return None
        return dayList[0].getDateString()
    
    def _getCurrentDayList(self,channelName, aSearchString):
        dayToDayList = self.getInfosForChannel(channelName)
        for dayList in dayToDayList:
            dateString = self._getDateFromDayList(dayList)
            if dateString == aSearchString:
                return dayList
        
        return None 
        
    
    #sort each list in the dictionary after the date and the time 
    def _sortEpgData(self,epgList):
        now = datetime.today();#speed up
        epgList[:]=[epgInfo for epgInfo in epgList if epgInfo.isActual(now)]
        sortedResult = sorted(epgList, key=lambda epgInfo: epgInfo.getStartTime())
        #convert the sorted entries in an array with progInfos per day
        dayToDayList = []
        currentList = None
        previousEntry = None
        for epgInfo in sortedResult:
            if previousEntry is None or not epgInfo.isSameDay(previousEntry):
                currentList=[]
                dayToDayList.append(currentList)
            ## removes double and old entries!
            if not epgInfo.isAlike(previousEntry):
                currentList.append(epgInfo)
#                 if not self._isEntryOverlapping(epgInfo, previousEntry):   
#                     currentList.append(epgInfo)
#                 elif self._mergeOverlappingItem(previousEntry, epgInfo):
#                     self._config.logInfo("Altered: "+epgInfo.getString())
#                     currentList.append(epgInfo) 

            previousEntry = epgInfo   
        
        return dayToDayList

    #rule of thumb: adapt the second item to the first. 
    #TODO: obsolete
    def _mergeOverlappingItem(self,firstItem,secondItem):
        secondItem.setStartTime(firstItem.getEndTime())
        return secondItem.getDurationInSeconds() > 5*60
            
    #TODO: obsolete        
    def _isEntryOverlapping(self,epgInfo, previousEpgInfo):
        if previousEpgInfo is None:
            return False
        
        isOverlapping = epgInfo.overlapsWith(previousEpgInfo)
        if isOverlapping:
            self._config.logInfo("!Overlaps: "+previousEpgInfo.getString()+">>"+epgInfo.getString())
        
        return isOverlapping            
    
        

#Access to autoselect list. Reads and writes to file    
class AutoSelectAccessor:
    
    def __init__(self,config):
        self.autoSelectList=[]
        self._config=config
        self.readAutoSelectData()
            
    def addAutoSelectPreference(self,epgInfo):
        #TODO:- introduce week day!
        if self._isEPGRegistered(epgInfo):
            self._config.logInfo("Double AutoSelect entry - ignored ")
        else:
            ase = AutoSelectEntry(epgInfo.getTitle(),epgInfo.getStartTime().hour,epgInfo.getChannel().getName())
            self.autoSelectList.append(ase)
    
    def removeFromAutoSelectPreference(self,hourString,titleString,channelName):
        self.autoSelectList[:] = [ase for ase in self.autoSelectList if not ase.isSelection(titleString,hourString,channelName) ]

    def updateWeekMode(self,hourString,titleString,channelName,weekModeString):
        found = next((ase for ase in self.autoSelectList if ase.isSelection(titleString,hourString,channelName)),None)
        if found is not None:
            found._weekMode=int(weekModeString)

    def getAutoSelectionList(self):
        return self.autoSelectList
    
    #check if the epgdata is already registered
    def _isEPGRegistered(self,epgInfo):
        found = next((ase for ase in self.autoSelectList if ase.matchesEPGInfo(epgInfo)),None)
        return found is not None 
    
    #must be the excact definition for recording 
    def _isMarkedForRecording(self,epgInfo):
        for autoSelect in self.autoSelectList:
            if autoSelect.isMarkedForRecording(epgInfo):
                return True
        return False
    
    
    def saveAutoSelectData(self):
        rootElement = CT.Element('AutoSelectList')
        for autoSelect in self.autoSelectList:
            entry = CT.SubElement(rootElement,"Entry")
            entry.attrib["hour"]=str(autoSelect.getHour())
            entry.attrib["chanID"]=autoSelect.getChannelID().decode('utf-8')
            entry.attrib["week"]=str(autoSelect.getWeekMode()); 
            entry.text= autoSelect.getTitle().decode('utf-8')
        path=self._config.getAutoSelectPath()
        with open(path, 'w') as aFile:
            CT.ElementTree(rootElement).write(aFile, "utf-8")

        
    def readAutoSelectData(self):
        path=self._config.getAutoSelectPath()
        try:
            with open(path, 'r') as xmlFile:
                xmlData = xmlFile.read()
        except IOError:
            self._config.logInfo("No AutoSelect file ")
            return
        
        root = CT.fromstring(xmlData)
        for info in root:
            hourString= info.get('hour')
            channelName = info.get('chanID').encode('utf-8')
            title=info.text.encode('utf-8')
            week = info.get("week")
            if week is None or channelName is None:
                self._config.logInfo("Invalid autoselection list - ignoring")
            else:
                autoSelect=AutoSelectEntry(title,int(hourString),channelName,int(week))
                self.autoSelectList.append(autoSelect)
     
     
    '''
    goes thru a channel list and checks if one of the epginfos should be recorded .... which calls the record queue
    '''
    def getEPGListForAutoSelect(self,dayToDayList):
        autoEPGList=[]
        for dayList in dayToDayList:
            for epgInfo in dayList:
                if self._isMarkedForRecording(epgInfo):
                    autoEPGList.append(epgInfo)
        return autoEPGList

#encapsulates the auto select data
class AutoSelectEntry:
    MODE_WEEK=0 #Mo-Fri
    MODE_WEEKEND=1 #Sa-Su
    MODE_ALL=2 #Mo-Su
    def __init__(self,title,prefHour,channelName,weekMode=MODE_ALL):
        self._title=title
        self._prefHour = prefHour #in case stuff comes twice a day. no entry = any
        self._weekMode=weekMode
        self._channelID = channelName
        
    def isSelection(self,aTitle, hourString,channelName):
        if self._title == aTitle:
            return hourString == self.getHourListString() and self.getChannelID()==channelName
        return False

    def matchesEPGInfo(self,epgInfo):
        if self._title != epgInfo.getTitle():
            return False
        if self._channelID != epgInfo.getChannel().getName():
            return False
        return epgInfo.getStartTime().hour == self._prefHour

    def isMarkedForRecording(self,epgInfo):
        if not self.matchesEPGInfo(epgInfo):
            return False;    
        return self._isRightWeekMode(epgInfo.getStartTime().weekday())
        

    def _isRightWeekMode(self,weekday):
        #Monday=0, Sunday = 6
        if self._weekMode == self.MODE_ALL:
            return True;
        if self._weekMode == self.MODE_WEEK:
            return weekday < 5;
        else:
            return weekday >4;

        
    
    def getTitle(self):
        return self._title
    
    def getHour(self):
        return self._prefHour
    
    def getChannelID(self):
        return str(self._channelID)
    
    def getHourListString(self):
        return str(self._prefHour)+".xx"
    
    def getWeekMode(self):
        return self._weekMode;
    
    def getWeekModeText(self):
        if self._weekMode==self.MODE_ALL:
            return "Mo-Su"
        if self._weekMode==self.MODE_WEEK:
            return "Mo-Fr"
        if self._weekMode==self.MODE_WEEKEND:
            return "Sa-Su"
        
