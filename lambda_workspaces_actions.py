#!/usr/bin/python

#
# Copyright 2024 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

import boto3
import logging
import base64
import json
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DDBTableName = os.environ.get("DynamoDBTableName", "WorkspacesPortal")

ValidActions = ["Start", "Stop", "Reboot", "Rebuild", "Decommission"]

def ParseJWT(Token):
    Auth = Token.split(".")[1]
    
    MissingPadding = len(Auth)%4
    if MissingPadding != 0: Auth += "="*(4-MissingPadding)
        
    try:
        AuthDict = json.loads(base64.urlsafe_b64decode(Auth))
    except Exception as e:
        logger.error("Could not parse JWT: "+str(e)+" "+Token)
        AuthDict = {}

    return(AuthDict)

def lambda_handler(event, context):
    global ValidActions
    
    Response               = {}
    Response["statusCode"] = 200
    Response["headers"]    = {"Access-Control-Allow-Origin": "*"}
    Response["body"]       = ""

    if "headers" not in event:
        logger.error("No headers supplied: "+str(event))
        Response["body"] = '{"Error":"No headers supplied."}'
        return(Response)
        
    if "Authorization" not in event["headers"]:
        logger.error("No Authorization header supplied: "+str(event))
        Response["body"] = '{"Error":"No authorization header supplied."}'
        return(Response)
        
    AuthInfo = ParseJWT(event["headers"]["Authorization"])
    if "identities" not in AuthInfo:
        logger.error("No identity information in JWT")
        Response["body"] = '{"Error":"No identity information in authorization."}'
        return(Response)
        
    Username = AuthInfo["identities"][0]["userId"].split("\\")[1] # Username is expected to be "DOMAIN\\username"
    ADGroups = AuthInfo["custom:ADGroups"]

    if "queryStringParameters" not in event:
        logger.error("Did not find queryStringParameters")
        Response["body"] = '{"Error":"No query string in request."}'
        return(Response)

    if "InstanceId" not in event["queryStringParameters"]:
        logger.error("No instance id specified")
        Response["body"] = '{"Error":"No instance id specified in request."}'
        return(Response)

    if "Action" not in event["queryStringParameters"]:
        logger.error("No action specified")
        Response["body"] = '{"Error":"No action specified in request."}'
        return(Response)
        
    InstanceId = event["queryStringParameters"]["InstanceId"]
    Action     = event["queryStringParameters"]["Action"]
    
    if Action not in ValidActions:
        logger.error("Invalid specified: "+Action)
        Response["body"] = '{"Error":"Invalid action specified in request."}'
        return(Response)

    if Action == "Decommission" and ADGroups.find("AdminGroupMember") == -1:
        logger.error("User not authorised to decommission Workspaces instance")
        Response["body"] = '{"Error":"You are not authorised to decommission instances."}'
        return(Response)

    DynamoDB = boto3.client("dynamodb")
    try:
        WorkspaceInfo = DynamoDB.get_item(TableName=DDBTableName,
                                          Key={"WorkspaceId":{"S":InstanceId}})
    except Exception as e:
        logger.error("DynamoDB error: "+str(e))
        Response["body"] = '{"Error":"Database query error."}'
        return(Response)

    if "Item" not in WorkspaceInfo:
        logger.error("Instance not found in DDB: "+InstanceId)
        Response["body"] = '{"Error":"Instance not found in database."}'
        return(Response)

    try:
        OwnedBy = WorkspaceInfo["Item"]["UserName"]["S"]
    except:
        logger.error("Username of instance owner not found in data: "+str(WorkspaceInfo))
        Response["body"] = '{"Error":"Instance owner not found."}'
        return(Response)
    
    if ADGroups.find("AdminGroupMember") == -1 and OwnedBy.lower() != Username.lower():
        logger.error("User not authorised to action other Workspaces instance")
        Response["body"] = '{"Error":"You are not authorised to modify other users instances."}'
        return(Response)

    State = WorkspaceInfo["Item"]["InstanceState"]["S"]
    Mode  = WorkspaceInfo["Item"]["RunningMode"]["S"]

    if Action == "Rebuild" and State not in {"AVAILABLE", "ERROR"}:
        logger.error("Cannot rebuild - state is not AVAILABLE or ERROR: "+State)
        Response["body"] = '{"Warning":"You cannot rebuild a Workspace unless it is in an AVAILABLE or ERROR state."}'
        return(Response)

    if Action == "Reboot" and State not in {"AVAILABLE", "IMPAIRED", "INOPERABLE"}:
        logger.error("Cannot reboot - state is not AVAILABLE, IMPAIRED or INOPERABLE: "+State)
        Response["body"] = '{"Warning":"You cannot reboot a Workspace unless it is in an AVAILABLE, IMPAIRED or INOPERABLE state."}'
        return(Response)

    if Action == "Decommission" and State == "SUSPENDED":
        logger.error("Cannot decommission - state is SUSPENDED: "+State)
        Response["body"] = '{"Warning":"You cannot decommission a Workspace when it is in a SUSPENDED state."}'
        return(Response)

    if Action == "Start" and State != "STOPPED":
        logger.error("Cannot start - state is not STOPPED: "+State)
        Response["body"] = '{"Warning":"You cannot start a Workspace that is not in a STOPPED state."}'
        return(Response)
        
    if Action == "Stop" and State not in {"AVAILABLE", "IMPAIRED", "UNHEALTHY", "ERROR"}:
        logger.error("Cannot stop - state is not AVAILABLE, IMPAIRED, UNHEALTHY or ERROR: "+State)
        Response["body"] = '{"Warning":"You cannot stop a Workspace that is not in an AVAILABLE, IMPAIRED, UNHEALTHY or ERROR state."}'
        return(Response)

    Workspaces = boto3.client("workspaces", region_name=WorkspaceInfo["Item"]["Region"]["S"])
    NextState  = ""
    
    if Action == "Start":
        try:
            ActionResponse = Workspaces.start_workspaces(StartWorkspaceRequests=[{"WorkspaceId":InstanceId}])
            NextState = "STARTING"
        except Exception as e:
            logger.error("Workspaces API error on start: "+str(e))
            Response["body"] = '{"Error":"Workspaces API query error for start."}'
            return(Response)

    if Action == "Stop":
        try:
            ActionResponse = Workspaces.stop_workspaces(StopWorkspaceRequests=[{"WorkspaceId":InstanceId}])
            NextState = "STOPPING"
        except Exception as e:
            logger.error("Workspaces API error on stop: "+str(e))
            Response["body"] = '{"Error":"Workspaces API query error for stop."}'
            return(Response)

    if Action == "Reboot":
        try:
            ActionResponse = Workspaces.reboot_workspaces(RebootWorkspaceRequests=[{"WorkspaceId":InstanceId}])
            NextState = "REBOOTING"
        except Exception as e:
            logger.error("Workspaces API error on reboot: "+str(e))
            Response["body"] = '{"Error":"Workspaces API query error for reboot."}'
            return(Response)

    if Action == "Rebuild":
        try:
            ActionResponse = Workspaces.rebuild_workspaces(RebuildWorkspaceRequests=[{"WorkspaceId":InstanceId}])
            NextState = "REBUILDING"
        except Exception as e:
            logger.error("Workspaces API error on rebuild: "+str(e))
            Response["body"] = '{"Error":"Workspaces API query error for rebuild."}'
            return(Response)

    if Action == "Decommission":
        try:
            ActionResponse = Workspaces.terminate_workspaces(TerminateWorkspaceRequests=[{"WorkspaceId":InstanceId}])
            NextState = "STOPPING"
        except Exception as e:
            logger.error("Workspaces API error on decommission: "+str(e))
            Response["body"] = '{"Error":"Workspaces API query error for decommission."}'
            return(Response)

    if len(ActionResponse["FailedRequests"]) > 0:
        logger.error("Workspaces API request failed:: "+ActionResponse["FailedRequests"][0]["ErrorMessage"])
        Response["body"] = '{"Error":"Action failed: '+ActionResponse["FailedRequests"][0]["ErrorMessage"]+'"}'
    else:
        Response["body"] = '{"Success":"Workspaces '+Action+' in progress for '+InstanceId+'."}'

        try:
            DynamoDB.update_item(TableName=DDBTableName,
                                 Key={"WorkspaceId":{"S":InstanceId}},
                                 UpdateExpression="set InstanceState = :s",
                                 ExpressionAttributeValues={":s":{"S":NextState}})
        except Exception as e:
            logger.error("Could not update DynamoDB for instance "+InstanceId+": "+str(e))

    return(Response)