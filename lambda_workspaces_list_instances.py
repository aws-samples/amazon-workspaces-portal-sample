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
from boto3.dynamodb.conditions import Attr
import os
import logging
import json
import base64

logger = logging.getLogger()
logger.setLevel(logger.INFO)

DDBTableName = os.environ.get("DynamoDBTableName", "WorkspacesPortal")

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
    
    ListAll = False
    try:
        if "queryStringParameters" in event:
            if "ListAll" in event["queryStringParameters"]:
                if ADGroups.find("AdminGroupMember") >= 0:
                    ListAll = True
    except:
        pass
            
    logger.info("Username: "+Username+" ADGroups: "+ADGroups+ " ListAll: "+str(ListAll))

    Table = boto3.resource("dynamodb").Table(DDBTableName)
    Expression = Attr("UserName").eq(Username)
    
    StartKey       = {}
    WorkspacesList = []
    while True: # Loop until no more items come from the DDB Scan
        logger.info("DDB scan loop, StartKey="+str(StartKey))
        try:
            if len(StartKey) == 0:  
                if ListAll:
                    Result = Table.scan()
                else:
                    Result = Table.scan(FilterExpression=Expression)
            else:
                if ListAll:
                    Result = Table.scan(ExclusiveStartKey=StartKey)
                else:
                    Result = Table.scan(FilterExpression=Expression, ExclusiveStartKey=StartKey)
        except Exception as e:
            logger.error("DynamoDB error: "+str(e))
            Response["body"] = '{"Error":"DynamoDB scan error."}'
            return(Response)

        for Workspace in Result["Items"]:
            logger.info("Processing "+Workspace["WorkspaceId"])
            
            # Need to convert Decimal() to actual numbers before returning JSON
            if "LastConnected" in Workspace: Workspace["LastConnected"] = int(Workspace["LastConnected"])
            if "LastTouched"   in Workspace: Workspace["LastTouched"]   = int(Workspace["LastTouched"])

            WorkspacesList.append(Workspace)

        if "LastEvaluatedKey" in Result:
            StartKey = Result["LastEvaluatedKey"]
        else:
            break

    JSONObject = {"Workspaces":WorkspacesList}
    Response["body"] = json.dumps(JSONObject)

    return(Response)