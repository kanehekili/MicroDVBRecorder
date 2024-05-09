#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Created on Mar 27, 2021
Walks through erverything... 
Usage:
comma sep pathes, Mime type, output file name
Test: python3 TreeWalker.py /media/nas video hugo.html
Truth: python3 ~/JWSP/python/Diverse/src/TreeWalker.py /media/nas/films/,/media/nas/nexus/CloneWars/,/media/nas/nexus/Nexus  video Films.html
@author: matze
'''
import sys,os
from pathlib import Path
import mimetypes
class TreeWalker():
    space =  '    ' # &#32&#32&#32&#32
    branch = '│   ' # &#9474&#32&#32&#32 
    tee =    '├── ' # &#9500&#9472&#9472&#32
    last =   '└── ' # &#9492&#9472&#9472&#32
        
    def __init__(self,mimeFilter=None):
        self.files=0
        self.directories=0
        self.filterMime=None
        self._initMimeFilter(mimeFilter)
        self._tempPath=[]
        self._fileInDir=0
    
    #we want the types like "video" "text" etc
    def _initMimeFilter(self,mimeFilter):
        if mimeFilter:
            self.filterMime=mimeFilter
        else:
            return

        if not mimetypes.inited:
            mimetypes.init()  # try to read system mime.types
        mimetypes.add_type("video/MP2T", "m2t")
            
        
    def tree(self,url,level=-1,onlyDirs=False):
        startPath=Path(url)
        self.onlyDirs=onlyDirs
        yield PathEntry(startPath,'','')#This is the "root"
        yield from self._walk(startPath, level=level)

    
    def getSummary(self):
        return f'\n{self.directories} directories' + (f', {self.files} files' if self.files else '')
             
    def _walk(self,path,prefix='', level=-1):
        if not level: 
            return # 0, stop iterating
        
        if self.onlyDirs:
            #contents = [d for d in path.iterdir() if d.is_dir()]
            contents = self._retrieveSave(path,lambda d:d.is_dir())
        else: 
            #contents = [f for f in path.iterdir() if self._filter(f)]
            contents = self._retrieveSave(path,self._filter)

        contents = sorted(contents, 
                            key=lambda posixP: posixP.name.lower() and posixP.is_dir())

        pointers = [self.tee] * (len(contents) - 1) + [self.last]
        for pointer, cpath in zip(pointers, contents):
            if cpath.is_dir():
                if self.onlyDirs:
                    yield PathEntry(cpath,prefix,pointer)
                self._tempPath.append(PathEntry(cpath,prefix,pointer))
                self.directories += 1
                self._fileInDir = 0
                extension = self.branch if pointer == self.tee else self.space 
                yield from self._walk(cpath, prefix=prefix+extension, level=level-1)
            elif not self.onlyDirs:
                if len(self._tempPath)>0:
                    #call with yield, otherwise won't exec pending pathes
                    yield from self._pushPendingPathes(path)
                yield PathEntry(cpath,prefix,pointer)
                self.files += 1
                self._fileInDir += 1

    def _pushPendingPathes(self,hitPath):
        test=str(hitPath)
        if len(self._tempPath)>0:
            for tPath in self._tempPath:
                slider = tPath.path.name
                if slider in test:
                    yield tPath

            self._tempPath=[]        

    def _retrieveSave(self,path,contraint):
        content=[]
        try:
            for item in sorted(path.iterdir()):
                #if self._filter(item):
                if contraint(item):
                    content.append(item)
        except PermissionError:
            pass
        return content

    def _filter(self,pPath):
        if not self.filterMime or pPath.is_dir():
            return True
        
        res= mimetypes.guess_type(pPath.name)
        if not res[0]:
            return False
        
        for mType in self.filterMime:
            if mType in res[0]:
                return True
        return False

    def printTree(self,urlList,onlyDirs=False):
        for url in urlList:
            res= self.tree(url,onlyDirs=onlyDirs)
            for pathentry in res:
                print(pathentry.display())
        print(self.getSummary())


#TODO: we need more than one root, set mime, +folders unwanted...
    def saveHTML(self,urlList,destFile):
        style ='<style>body { float:left;} div {white-space: pre;padding:0px;margin:0px;font-family: Helvetica, Arial, sans-serif;font-size:1.0em;} .evenrow {background-color: #F8E0D7;} .oddrow {background-color: #F8EEEE;}</style>'  
        htmlStart = '<!DOCTYPE html><html><head><meta content="text/html; charset=UTF-8">'+style+'<title>Micro Recorder Log</title><body>'
        htmlend = '--- End ---</body></html>'
        #possible hook back in micro recorder
        #htmlBack = '<div class= back><a href="./Log.html">Back to Log</a></div>'
        isEven=False

        with open(destFile, 'w+') as htmlFile:
            htmlFile.write(htmlStart)
            #htmlFile.write("<b> The film list</b>")
            #htmlFile.write(htmlBack)
            #mfilter=",".join(self.filterMime)
            #htmlFile.write("<div><b> File List generated by Treewalker >>github.com@kanehekili/MicroDVBRecorder<< , filter:%s </b></div>"%(mfilter))
            for url in urlList:
                htmlFile.write("<b>Root:%s</b>"%(url)) 
                res= self.tree(url)
                for pathentry in res:
                    if pathentry.pathName().startswith('.'):#Must include subfolders!
                        continue
                    if isEven:
                        divid="evenrow"
                    else:
                        divid="oddrow"
                    if pathentry.isDir():
                        line="<b>"+pathentry.prefix+pathentry.pointer+pathentry.pathName()+"</b>"
                    else:
                        line=pathentry.prefix+pathentry.pointer+pathentry.pathName()
                    #print(pathentry.display())
                    line=self.encodeHtml(line)
                    htmlFile.write('<div class="'+divid+'">'+line+"</div>")
                    isEven=not isEven
            htmlFile.write(htmlend)
    
    def encodeHtml(self,line):
        tmp = line.encode('ascii', 'xmlcharrefreplace')
        return tmp.decode('ascii')
        

class PathEntry():
    def __init__(self,path,prefix,pointer):
        self.path=path
        self.prefix=prefix
        self.pointer=pointer
        
    def isDir(self):
        return self.path.is_dir()
    
    def pathName(self):
        return self.path.name
    
    def display(self,tweak=None): #tweak is a lambda
        if tweak:
            return tweak(self.path,self.prefix,self.pointer)
        
        if self.isDir():
            return self.prefix + self.pointer + "["+self.pathName()+"]"
        else:
            return self.prefix + self.pointer + self.pathName()


if __name__ == '__main__':
    fallback=os.path.dirname(__file__)
    fn = sys.argv[1:]
    if len(fn)<1:
        src=fallback
    else:
        srcList=fn[0].split(',')
        test=Path(srcList[0])
        if not Path(test).is_dir():
            print("Usage: TreeWalker /path/to/folder,pathToFolder2 ['mimeType,...'] [../web/Films.html]")
            exit()
    if len(fn)>1:
        mimes=fn[1].split(',')
    else:
        mimes=None
    w=TreeWalker(mimes)
    if len(fn)<3:
        w.printTree(srcList)
    else:
        w.saveHTML(srcList,fn[2])
