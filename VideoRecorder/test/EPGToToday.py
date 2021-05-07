#!/usr/bin/env python
# encoding: utf-8
'''
EPGToToday -- Take the master EPG, find oldest entry and update all data, store them
This is for testing the application!
'''
import Configuration
from ChannelReader import ChannelReader
from EpgReader import EpgReader, EpgReaderPlugin
from datetime import datetime,timedelta
import os

import xml.etree.cElementTree as CT

HomeDir = os.path.dirname(__file__)
#UserPath=os.path.expanduser("~")

DataPath="data"

config = Configuration.Config()
config.setupLogging("testVCR.log")
reader = ChannelReader()
reader.readChannels(config.getChannelFilePath());
channelList=reader.getChannels()
epgReader=EpgReader(channelList)
testpath = os.path.join(HomeDir,DataPath+"/EPGListTemplate.xmltv")
targetFile =config.getCachedXMLTVFilePath()

def getEpgInfos():
    
    epgPlugin=EpgReaderPlugin(None,False)
    infoList = epgReader.readCachedXMLFile(epgPlugin,testpath)
    return infoList

def getOldestTimestamp(infoList):
    lowTime = datetime.now();
    changed = False
    for epgInfo in infoList:
        if epgInfo.getStartTime() < lowTime:
            changed=True
            lowTime = epgInfo.getStartTime()
    if changed:
        return lowTime
    return None


def moveListInTime(days, infoList):
    for epgInfo in infoList:
        epgInfo.startTime = epgInfo.startTime+days
        epgInfo.endTime = epgInfo.endTime+days
    storePlainEPGList(infoList)   

def storePlainEPGList(infoList):
    ROOT = "REC"
    rootElement = CT.Element(ROOT)
    for epgInfo in infoList:
        if epgInfo.isConsistent:
            epgInfo.storeAsXMLElement(epgReader,rootElement)

    with open(targetFile, 'wb') as aFile:
        CT.ElementTree(rootElement).write(aFile, "utf-8")
    


def updateEPGInfos():
    infolist = getEpgInfos()
    lowTime = getOldestTimestamp(infolist)
    if not lowTime:
        print("nothing to change")
        return
    td = datetime.now() - lowTime
    print("Changing time from:",lowTime," offset: ",td.days," days")
    days = timedelta(days=td.days)
    moveListInTime(days,infolist)
    print("Saved at: ",targetFile)

updateEPGInfos()
        
        