var isFilterOn=false;

var channelList= null;
var programmList= null;
var currentRecListSelection=null;
//constant definition
var TYPE_HEAD=0;
var TYPE_PROG=1;
var TYPE_INFO=2;
var CHANNEL_KEY = document.domain+"channelStore";
var CHANNEL_SELECTION_KEY = document.domain+"channelSelection";

var MODE_DATA = 0xA0;
var MODE_REC = 0xA1;
var MODE_BLOCK = 0xA3;
var touchDragItem;
var TOUCH_MODE=false;

/*
 * Note:
 * var functionX = function() == is defined at runtime, calls muss lie below it.
 * function functionX() == defined at parse time, so refrences can be anywhere
 */
window.onload=initialize;

function initialize(){
    //BROWSER_TYPE=checkBrowserType();
	hookActionEvents();
	var rootElement = document.documentElement;

    //no context menu
    window.addEventListener("contextmenu", function(e) { e.preventDefault(); })
    if ("ontouchstart" in rootElement) {
        //prevents hover effects?
        rootElement.className += " no-touch";
        setDynamicCSS("touchdefault.css");
        //--touch only
    	touchDragItem = document.createElement("div");
	    touchDragItem.id="draggable";
	    rootElement.appendChild(touchDragItem);
        resetTouchDragItem();  
        TOUCH_MODE=true;      
    }
    else {
        setDynamicCSS("clickdefault.css");
    }
    connectToServer();
};

function setDynamicCSS(cssName){
    var head  = document.getElementsByTagName('head')[0];
    var link  = document.createElement('link');
    link.id   = 0xAE;
    link.rel  = 'stylesheet';
    link.type = 'text/css';
    link.href = './css/'+cssName;
    link.media = 'all';
    head.appendChild(link);
};

function refreshProgrammList(){
	var selected = channelList.getSelected();
	if (selected != null){
		this.executeServerCommand(new ServerCommand("REQ_Programs",selected.getTitle()));
    }        
        
};


//var txt = function is a class, not a function?
function connectToServer(){
	this.showStatus("..connecting");
	this.executeServerCommand(new ServerCommand("REQ_Channels",""));
};


function executeServerCommand(aServerCommand){
	this.showStatus("..reading");
	var url="cmd";
	var jCommand = JSON.stringify(aServerCommand,aServerCommand.stringify);
	var request = new XMLHttpRequest();
	request.open("POST",url,true);
	request.onload = function() {
		if (request.status==200){
			handleServerResponse(aServerCommand,request.responseText);
		}
	};
	try {
		request.send(jCommand);
	}
	catch(err){
		showStatus(err.message);
	}
	
};

function handleServerResponse(aServerCommand,jsonResult){
	var command = aServerCommand.cmd;

	if (command=="REQ_Channels"){
		updateChannels(jsonResult);
		refreshProgrammList();
		return;
	} 
	if (command=="REQ_Programs"){
		updateProgrammList(jsonResult);
		isFilterOn=false;
		return;
	}

	if (command=="MARK_Programm"){
		aServerCommand.data.updateProgrammInfo(jsonResult);
		return;
	}
	
	if (command=="FILTER"){
		updateProgrammList(jsonResult);
		isFilterOn=true;
		return;
	}

	if (command=="SEARCH_ALL"){
		createSearchList(jsonResult);
		return;
	}


	if (command=="LIST_REC"){
		updateRecordList(jsonResult);
        //setChannelToViewPort();
		return;
	}
	if (command=="LIST_AUTO"){
		updateAutoselectList(jsonResult);
		return;
	}
    
	if (command=="AUTO_SELECT"){ //DnD add to autoselect
		showStatus("Idle");
		return;
	}
	
	if (command=="RM_AUTOSELECT"){ 
		refreshAutoSelectList(aServerCommand.data);
        //setChannelToViewPort();
		return;
	}
	if (command=="AUTO_WEEKMODE"){ 
	   console.log("WEEK Mode set"); 
	   return;
	}
    
    if (command=="REC_MARGINS"){
        showStatus("Margins saved");
    }

};

/* ---- serverfunctions ----*/
function updateChannels(jsonResult){
	channelList = new ProgrammCollection();
	var channels = JSON.parse(jsonResult);
	if (channels.error != null){
		showStatus("Error retrieving data:"+channels.args);
		return;
	}
	var count = channels.length;
	var channelDOM=document.getElementById("channel_contents");
	var sortedChannels = getSortedChannels(channels);
	for (i=0; i< count; i++){ 
		var li= document.createElement("div");
		/*textContent replaces innerText and is W3C compliant*/
		li.className="ChannelItem";
		li.textContent=sortedChannels[i];
		li.id="channel_"+(i+1);
		channelDOM.appendChild(li);
		var listEntry = new ChannelListEntry(i,li);
		listEntry.registerEvents();
		channelList.add(listEntry);
	}
	var lastSel = localStorage[CHANNEL_SELECTION_KEY];
	if (lastSel == null)
		lastSel=0;
	channelList.selectedIndex=lastSel;
    setChannelToViewPort();
	showStatus("Channels loaded");
};

function getSortedChannels(channels){
	var items = localStorage[CHANNEL_KEY];
	if (items == null || items.length < 10){
		items = JSON.stringify(channels);
		localStorage[CHANNEL_KEY] = items;
	}
	var result = JSON.parse(items);
	if (result.length != channels.length){
		localStorage[CHANNEL_KEY]=null;
		return getSortedChannels(channels);
	}
	return result;
};

function updateProgrammList(jsonResult){
	var currentDayPos = nearestDayRow();
	var builder = new ProgramListBuilder(jsonResult);
	var ok= builder.updateProgrammList()
	channelList.getSelected().setSelection();
	localStorage[CHANNEL_SELECTION_KEY] = channelList.selectedIndex;
	//this is a webkit bug: Scrolling will lead to empty screen. Evil?
	var programmDOM=document.getElementById("programmbody");
	programmDOM.style.display='none';
	programmDOM.offsetHeight;
	programmDOM.style.display='block';
	if (currentDayPos != null) {
		var nextHook=getDayRowByName(currentDayPos.innerHTML);
		if (nextHook != null){
			nextHook.scrollIntoView(true);
		}

	}
	if (ok)
		showStatus("Infos loaded");
	
};



//---------------- Action events from buttons, DnD and List ----------
function hookActionEvents(){
	//var nodes = document.getElementsByClassName("icoAction");
	//Connect the buttons to events
	
	var button = document.getElementById("logBtn");
	button.addEventListener("click",handleShowLogClicked,false);

	button = document.getElementById("reclistBtn");
	button.addEventListener("click",handleRecListClicked,false);
	button.addEventListener("dragover",handleDragenter,false);
	button.addEventListener("dragleave",handleDragleave,false);
	button.addEventListener("drop",handleDropOnRec,false);	
	
	button = document.getElementById("filterBtn");
	button.addEventListener("click",handleFilterClicked,false);

	button = document.getElementById("searchBtn");
	button.addEventListener("click",handleSearchClicked,false);

    button = document.getElementById("channelBtn");
	button.addEventListener("click",handleChannelAction,false);
    
	button = document.getElementById("nextPageBtn");
	button.addEventListener("click",handleNextDayClicked,false);
	
	button = document.getElementById("prevPageBtn");
	button.addEventListener("click",handlePreviousDayClicked,false);
	
	
	var dropzone = document.getElementById("dropzone");
	dropzone.addEventListener("dragover",this.handleDragenter,false);
	dropzone.addEventListener("dragleave",this.handleDragleave,false);
	dropzone.addEventListener("drop",this.handleDrop,false);
	dropzone.addEventListener("click",handleAutoListClicked,false);
	
	var input = button = document.getElementById("search");
	input.addEventListener("keyup",this.handleKeypress,false);
	
	//- the rec time buttons --
	var recButtons = document.getElementsByClassName("recBtn")
	for (i=0; i< recButtons.length; i++){ 
		recButtons[i].addEventListener("click",handleRecButtonChangeTime,false);
	}
	//- rec overlay close btn
	document.getElementById("recOK").addEventListener("click",onRecordingDialogClose,false);
    document.getElementById("autoOK").addEventListener("click",onAutoSelectDialogClose,false);
    document.getElementById("startRecOverlay").addEventListener("click",onOverlayOpen,false);
    document.getElementById("startAutoOverlay").addEventListener("click",onOverlayOpen,false);
    document.addEventListener("click", onClickedAnywhere, false);
    
};

//--- DnD action handler -----
var handleDragenter= function(event){
	var node = getActionDropNode(event);
	node.style.webkitTransform="scale(1.5)";
	node.style.transform="scale(1.5)";
	addClassName(node,"dropped");
};

var handleDragleave= function(event){
	var node = getActionDropNode(event);
	node.style.webkitTransform="scale(1.0)";
	node.style.transform="scale(1.0)";
	removeClassName(node,"dropped");
};

var handleDrop= function(event){
    var jString=prepareToDrop(event);
    if (jString == null){
		return null;
    }
	executeServerCommand(new ServerCommand("AUTO_SELECT",jString));
};

function prepareToDrop(event){
	var node = getActionDropNode(event);
	node.style.webkitTransform="scale(1.0)";
	node.style.transform="scale(1.0)";
	var id=event.dataTransfer.getData("text");
    removeClassName(node,"dropped");	
	if (id==""){
		return null;
    }		
	var selnode = document.getElementById(id);
	return JSON.stringify(selnode.model.jsonData);
}

function handleDropOnRec(event){
	var jString=prepareToDrop(event);
	var id=event.dataTransfer.getData("text");
    if (id==""){
		return null;
    }
	var node = document.getElementById(id);
	node.model.updateProgrammInfo(jString);
	executeServerCommand(new ServerCommand("MARK_Programm",jString,node.model));
};

function getActionDropNode(event){
	event.preventDefault();
	var node = event.target;
	if (event.target.id.length != 0){
		node = node.childNodes[1]; 
	}
	return node;
};

//--Autoselect click handler
var handleAutoListClicked= function(event) {
	executeServerCommand(new ServerCommand("LIST_AUTO",""));
};

var handleChannelAction= function(event) {
	//executeServerCommand(new ServerCommand("LIST_AUTO",""));
    //toggle the left panel...
    panel=document.getElementById("leftPanel");
    proc=document.getElementById("rightPanel");
    if (panel.className == "ChannelHidden"){
        panel.className = "ChannelPanel";
        proc.className = "ProgPanel";
    }
    else {
        panel.className = "ChannelHidden";
        proc.className = "ProgHidden";
    }
    
};
//-Log button button
var handleShowLogClicked=function(event) {
	window.open("/Log.html",'_blank');
};
//--Rec list handler
var handleRecListClicked= function(event) {
	executeServerCommand(new ServerCommand("LIST_REC",""));
};

//--Filter list handler
var handleFilterClicked= function(event) {
	if (channelList.getSelected() == null){
		showStatus("No channel selected");
		return;
	}		

	var currentChannelName = channelList.getSelected().getTitle();
	if (isFilterOn){
		executeServerCommand(new ServerCommand("REQ_Programs",currentChannelName));
	}
	else { 
		if (programmList.getSelected() == null){
			showStatus("No program selected");
			return;
		}		
		var objectData = programmList.getSelected().jsonData;
		var searchData = [currentChannelName,objectData.title];		
		executeServerCommand(new ServerCommand("FILTER",searchData));
	}
};

//-- Search Button handler
var handleSearchClicked= function(event) {
	var result = window.prompt("Search a programm","?");
	if (result != null)
	   executeServerCommand(new ServerCommand("SEARCH_ALL",result));
}

//--Next day handler
var handleNextDayClicked= function(event) {
	var item = nearestDayRow();
	var next = item.dayIndex+1;
	var nextItem= document.getElementById("dayID"+next);
	if (nextItem!=null){
		item= nextItem;
	}
	item.scrollIntoView(true);
};

//--Previous day handler
var handlePreviousDayClicked= function(event) {
	var item = nearestDayRow();
	var next = item.dayIndex-1;
	if (next >=0){
		item= document.getElementById("dayID"+next);
	}
	if (item==null){
		return;
	}
	item.scrollIntoView(true);
};

//- search inpunt field handler
var handleKeypress=function(evt) {
	var inputField = (evt.target) ? evt.target : evt.srcElement;
	var searchString = inputField.value;
	var keytype = evt.keyIdentifier;
	if (keytype == null)
		keytype = evt.key;
	var programEntry;
	if (keytype=="Down"){
		programEntry = programmList.findNext(searchString);
	} else if (keytype=="Up"){
		programEntry=programmList.findPrevious(searchString);
	} else {
		programEntry=programmList.find(searchString);
	}
	if (programEntry != null){
		programEntry.domObject.scrollIntoView(true);
	}
};


