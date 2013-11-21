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
from xml.sax.saxutils import unescape,escape

class EpgDatabase:
    def __init__(self,config):
        self._channelDictionary={}
        self._config = config
        self._futureItemsOnly=config.FUTURE_ITEMS_ONLY
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
        #TODO: clean empty or old entries!
        return self._channelDictionary.setdefault(aChannelString,[])
    
    def showFutureItemsOnly(self,aFlag):
        self._futureItemsOnly=aFlag
    '''
    Answers an array  containing an array of daily entries - per channel
    '''
    def getData(self):
        return self._channelDictionary.values()
    
    
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
            currentList = self._getCurrentDayList(channelName,searchDate)
            if currentList is None:
                #adds the dayList into the day to day array
                self._insertToDayToDayList(channelName,dayList)
            else:
                self._mergeDailyEntries(currentList,dayList)

        
            
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
        
    '''
    merge two daily lists. The new data rules on the same time slot
    Scope: day list
    '''
    def _mergeDailyEntries(self,currentList, newDayList):
        for epgInfo in newDayList:
            found = self._findTimeslot(currentList, epgInfo)
            if not found: #Add new entry
                currentList.append(epgInfo)
            else:
                self._updateEpgEntry(found,epgInfo)
        
        currentList.sort(key=lambda epgInfo: epgInfo.getStartTime())   
        self._checkforOverlappingEntries(currentList)

    '''
    update the current slot data
    '''    
    def _updateEpgEntry(self,currentEpgInfo, newEpgInfo):
        if currentEpgInfo.getEndTime()!=newEpgInfo.getEndTime():
            #self._config.logInfo("!LEN chg:"+newEpgInfo.getString())
            currentEpgInfo.setEndTime(newEpgInfo.getEndTime())
        
        currentEpgInfo.setTitle(newEpgInfo.getTitleUnescaped())
        currentEpgInfo.setDescription(newEpgInfo.getDescriptionUnescaped())
            

    def _findTimeslot(self,aList, epgInfo):
        for epg in aList:
            if epg.getStartTime()==epgInfo.getStartTime():
                return epg
        return None
            

    def _checkforOverlappingEntries(self,mergedList):
        previousEpgInfo=None
        invalidEntries=[]
        for epgInfo in mergedList:
            overlaps = self._isEntryOverlapping(epgInfo, previousEpgInfo)
            if overlaps:
                invalidEntries.append(epgInfo)
            else:
                previousEpgInfo=epgInfo
        
        for wrongItem in invalidEntries:
            mergedList.remove(wrongItem)
            #self._config.logInfo("Removing EPG Info "+wrongItem.getString())
            
    
    #gets the first entry of the EPGInfo array and answers the search date
    def _getDateFromDayList(self,dayList):
        #check if that can be zero length
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
        
        if self._futureItemsOnly:
            epgList[:]=[epgInfo for epgInfo in epgList if epgInfo.isActual()]
        
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
            if not self._isEntryOverlapping(epgInfo, previousEntry):   
                currentList.append(epgInfo)

            previousEntry = epgInfo   
                            

        return dayToDayList

    def _isEntryOverlapping(self,epgInfo, previousEpgInfo):
        if previousEpgInfo is None:
            return False
        
        isOverlapping = epgInfo.overlapsWith(previousEpgInfo)
        #if isOverlapping:
            #self._config.logInfo("!Overlaps: "+previousEpgInfo.getString()+">>"+epgInfo.getString())
        
        return isOverlapping            
    
        

#Access to autoselect list. Reads and writes to file    
class AutoSelectAccessor:
    
    def __init__(self,config):
        self.autoSelectList=[]
        self._config=config
        self.readAutoSelectData()
            
    def addAutoSelectPreference(self,epgInfo):
        ase = AutoSelectEntry(epgInfo.getTitle(),epgInfo.getStartTime().hour)
        self.autoSelectList.append(ase)
    
    def removeFromAutoSelectPreference(self,hourString,titleString):
        self.autoSelectList[:] = [ase for ase in self.autoSelectList if not ase.isSelection(titleString,hourString) ]

    def getAutoSelectionList(self):
        return self.autoSelectList
    
    def contains(self,epgInfo):
        for autoSelect in self.autoSelectList:
            if autoSelect.matchesEPGInfo(epgInfo):
                return True
        
        return False
    
    
    def saveAutoSelectData(self):
        rootElement = CT.Element('AutoSelectList')
        for autoSelect in self.autoSelectList:
            entry = CT.SubElement(rootElement,"Entry")
            entry.attrib["hour"]=str(autoSelect.getHour())
            entry.text= unescape(autoSelect.getTitle()) #The unescaped text
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
            title=escape(info.text)
            autoSelect=AutoSelectEntry(title,int(hourString))
            self.autoSelectList.append(autoSelect)
     
     
    '''
    goes thru a channel list and checks if one of the epginfos should be recorded .... which calls the record queue
    '''
    def getEPGListForAutoSelect(self,dayToDayList):
        autoEPGList=[]
        for dayList in dayToDayList:
            for epgInfo in dayList:
                if self.contains(epgInfo):
                    autoEPGList.append(epgInfo)
        return autoEPGList

#encapsulates the auto select data
class AutoSelectEntry:
    def __init__(self,title,prefHour):
        self._title=title
        self._prefHour = prefHour #in case stuff comes twice a day. no entry = any
        
    def isSelection(self,aTitle, hourString):
        if self._title == aTitle:
            return hourString == self.getHourListString()
        return False

    def matchesEPGInfo(self,epgInfo):
        if self._title == epgInfo.getTitle():
            startDate=epgInfo.getStartTime()
            return startDate.hour == self._prefHour
        return False
    
    def getTitle(self):
        return self._title
    
    def getHour(self):
        return self._prefHour
    
    def getHourListString(self):
        return str(self._prefHour)+".xx"
