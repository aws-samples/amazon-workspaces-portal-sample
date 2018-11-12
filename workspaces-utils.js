/*
 * Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this
 * software and associated documentation files (the "Software"), to deal in the Software
 * without restriction, including without limitation the rights to use, copy, modify,
 * merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
 * PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
 * OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

/*
 * Change the following lines to reflect your Cognito User Pool, API Gateway,
 * S3 bucket and region configuration.
 */
CognitoDomainName = "xxxxxxxxxxxx";
CognitoClientId   = "xxxxxxxxxxxxxxxxxxxxxxxxxx";
APIGatewayId      = "xxxxxxxxxx";
RegionName        = "ap-southeast-2";
S3BucketName      = "xxxxxxxxxxxx";

USER_API_URL  = "https://"+APIGatewayId+".execute-api."+RegionName+".amazonaws.com/Prod/user/"
ADMIN_API_URL = "https://"+APIGatewayId+".execute-api."+RegionName+".amazonaws.com/Prod/admin/"
authRedirect  = "https://"+CognitoDomainName+".auth."+RegionName+".amazoncognito.com/login?response_type=token&client_id="+CognitoClientId+"&redirect_uri=https%3A%2F%2Fs3-"+RegionName+".amazonaws.com%2F"+S3BucketName+"%2Findex.html";

function parseJWT(token) {
 var base64Url = token.split('.')[1];
 var base64 = base64Url.replace('-', '+').replace('_', '/');
 return JSON.parse(window.atob(base64));
}

function login() {
 var accessToken = localStorage.getItem('WorkspacesAccessToken');
 if (accessToken == null) {
   hash = location.hash
   if (hash.length > 0) {
    parameters = location.hash.substring(1).split("&"); // Lose the # off the front first
    for(var i = 0; i < parameters.length; i++) {
     if (parameters[i].substr(0,9) == "id_token=") {
      accessToken = parameters[i].split("=")[1];
      localStorage.setItem('WorkspacesAccessToken', accessToken);
     }
    }

    if (accessToken == null) { // Just in case we can't figure out who the user is
     console.log("Access token not found in URL hash contents");
     window.location = authRedirect;
     return;
    }
   }
   else {
    console.log("No token found");
    window.location = authRedirect;
    return;
   }
 }

 var currentEpoch = new Date()/1000;
 var JWTExpiry    = parseJWT(accessToken).exp
 if (currentEpoch > JWTExpiry) {
  localStorage.removeItem("WorkspacesAccessToken")
  console.log("Token expired");
  window.location = authRedirect;
  return;
 }

 // Otherwise we're authenticated and we can do stuff
 decoded = parseJWT(accessToken);
 if (decoded["custom:ADGroups"].includes("UserGroupMember")) {
  GetWorkspacesDetails(false);
 }
 if (decoded["custom:ADGroups"].includes("AdminGroupMember")) {
  GetWorkspacesDetails(true);
 }

 UserLen  = document.getElementById("userworkspaces").innerHTML.length
 AdminLen = document.getElementById("adminworkspaces").innerHTML.length
 if (UserLen == 0 && AdminLen == 0) {
  document.getElementById("noworkspaces").style.visibility = "visible";
 }
}

function GetWorkspacesDetails(GetAllWorkspaces) {
 var accessToken = localStorage.getItem('WorkspacesAccessToken');
 var API_URL = USER_API_URL;
 if (GetAllWorkspaces) { API_URL += "?ListAll=True" }

 var API_Client = new XMLHttpRequest();
 API_Client.onreadystatechange = function() {
  if (API_Client.readyState == XMLHttpRequest.DONE) {
   Result = API_Client.responseText;
   HTML = RenderWorkspacesTiles(Result, GetAllWorkspaces);
   document.getElementById(GetAllWorkspaces ? "adminworkspaces" : "userworkspaces").innerHTML = HTML;
   if (HTML.length > 0)  {
    document.getElementById("noworkspaces").style.visibility = "hidden";
   }
  }
 }
 API_Client.open("get", API_URL);
 API_Client.setRequestHeader("Content-Type", "application/json");
 API_Client.setRequestHeader("Authorization", accessToken);
 API_Client.timeout = 10000;
 API_Client.ontimeout = ProcessTimeout;
 API_Client.send();
}

function RenderWorkspacesTiles(ListString, AdminList) {
 var HTML = "";

 try {
  JSONResult = JSON.parse(ListString);
 }
 catch(error) {
  console.log(error);
  console.log(ListString);

  HTML += "<div class='error'>Sorry - could not parse JSON response.</div>";
  return(HTML); // Yeah, yeah - early return but it's neater
 }

 if (JSONResult.Workspaces != undefined) {
  var WorkspacesCount = 0;

  for(i = 0; i < JSONResult.Workspaces.length; i++) {
   var Div = ""
   var Instance = JSONResult.Workspaces[i];


   Div += "<table class='workspacesinfo'>";

   if (AdminList) {
    Div += "<tr><td class='title'>Username:</td><td class='info'>"+Instance.UserName+"</td></tr>";
   }

   Div += "<tr><td class='title'>Workspace id:</td><td class='info'>"+Instance.WorkspaceId+"</td></tr>";

   ComputerName =  (Instance.ComputerName != undefined) ? Instance.ComputerName : "<span class='italic'>Unknown</span>";
   Div += "<tr><td class='title'>Computer name:</td><td class='info'>"+ComputerName+"</td></tr>";

   Div += "<tr><td class='title'>Region:</td><td class='info'>"+Instance.Region+"</td></tr>";
   Div += "<tr><td class='title'>State:</td><td class='state-"+Instance.InstanceState.toLowerCase()+"'><span>"+Instance.InstanceState+"</span></td></tr>";

   if (AdminList) {
    Div += "<tr><td class='title'>Running mode:</td><td class='info'>"+Instance.RunningMode+"</td></tr>";

    IPAddress = (Instance.IPAddress != undefined) ? Instance.IPAddress : "<span class='italic'>Unknown</span>";
    Div += "<tr><td class='title'>IP address:</td><td class='info'>"+IPAddress+"</td></tr>";

    var Connected = "";
    if( Instance.LastConnected != undefined) {
     Connected = new Date(0);
     Connected.setUTCSeconds(Instance.LastConnected);
    }
    else {
     Connected = "<span class='italic'>Never</span>"
    }
    Div += "<tr><td class='title'>Last connected:</td><td class='info'>"+Connected+"</td></tr>";
   }

   Div += "<tr><td class='title'>Registration code:</td><td class='info'>"+Instance.RegCode+"</td></tr>";

   if (! AdminList) {
    Div += "<tr><td colspan='2' class='link'><a href='https://clients.amazonworkspaces.com/' target='_blank'>Download the Workspaces client</a></td></tr>";
   }

   Div += "<tr><td colspan='2' class='actions'>"

   if (Instance.RunningMode == "AUTO_STOP") {
    if (Instance.InstanceState == "STOPPED") {
     Div += "<a href='javascript:WorkspacesAction(\"Start\",\""+Instance.WorkspaceId+"\")' class='start'>Start</a>&nbsp;&nbsp;";
    }
    if (Instance.InstanceState == "AVAILABLE") {
     Div += "<a href='javascript:WorkspacesAction(\"Stop\",\""+Instance.WorkspaceId+"\")' class='stop'>Stop</a>&nbsp;&nbsp;";
    }
   }

   if (Instance.InstanceState != "STOPPED" && Instance.InstanceState != "REBOOTING") {
    Div += "<a href='javascript:WorkspacesAction(\"Reboot\",\""+Instance.WorkspaceId+"\")' class='reboot'>Reboot</a>&nbsp;&nbsp;";
   }

   Div += "<a href='javascript:WorkspacesAction(\"Rebuild\",\""+Instance.WorkspaceId+"\")' class='rebuild'>Rebuild</a>";
   if (AdminList) {
    Div += "&nbsp;&nbsp;<a href='javascript:WorkspacesAction(\"Decommission\",\""+Instance.WorkspaceId+"\")' class='decommission'>Decommission</a>";
   }
   Div += "</td></tr>";
   Div += "</table>";

   HTML += Div;
   WorkspacesCount++;
  }

  if (WorkspacesCount > 0) {
   HTML = "<h1>"+(AdminList ? "All" : "Your")+" Workspaces</h1>"+HTML;
  }
 }
 else if (JSONResult.Message != undefined) {
  HTML += "<div class='error'>"+JSONResult.Message+"</div>";
 }
 else if (JSONResult.message != undefined) {
  HTML += "<div class='error'>"+JSONResult.message+"</div>";
 }
 else if (JSONResult.Error != undefined) {
  HTML += "<div class='error'>"+JSONResult.Error+"</div>";
 }
 else if (JSONResult.Warning != undefined) {
  HTML += "<div class='warning'>"+JSONResult.Warning+"</div>";
 }
 else {
  HTML += "<div class='error'>Undefined error</div>";
  console.log(ListString)
}

 return(HTML);
}

function ProcessTimeout() {
 console.log("Query to API Gateway timed out");
}

function WorkspacesAction(Action, InstanceId) {
 var accessToken = localStorage.getItem('WorkspacesAccessToken');
 var API_URL = ADMIN_API_URL;

 API_URL += "?Action="+Action+"&InstanceId="+InstanceId;

 var API_Client = new XMLHttpRequest();
 API_Client.onreadystatechange = function() {
  if (API_Client.readyState == XMLHttpRequest.DONE) {
   var HTML = "";

   Result = API_Client.responseText;
   try {
    JSONResult = JSON.parse(Result);

    if (JSONResult.Success != undefined) {
     HTML = "<div class='success'>"+JSONResult.Success+"</div>";
    }
    if (JSONResult.Warning != undefined) {
     HTML = "<div class='warning'>"+JSONResult.Warning+"</div>";
    }
    if (JSONResult.Error != undefined) {
     HTML = "<div class='error'>"+JSONResult.Error+"</div>";
    }
   }
   catch(error) {
    console.log(error);
    console.log(Result);

    HTML += "<div class='error'>Sorry - could not parse JSON response.</div>";
   }

   document.getElementById("response").innerHTML = HTML;

   document.getElementById("userworkspaces").innerHTML = "";
   document.getElementById("adminworkspaces").innerHTML = "";
   GetWorkspacesDetails(false);
   GetWorkspacesDetails(true);
  }
 }
 API_Client.open("get", API_URL);
 API_Client.setRequestHeader("Content-Type", "application/json");
 API_Client.setRequestHeader("Authorization", accessToken);
 API_Client.timeout = 10000;
 API_Client.ontimeout = ProcessTimeout;
 API_Client.send();
}
