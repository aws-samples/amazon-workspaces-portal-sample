#!/usr/bin/python

#
# Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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
import os
import logging
from botocore.exceptions import ClientError

Logger       = None
DDBTableName = "WorkspacesPortal"

def Deserialise(DDBItem):
    for Key in DDBItem:
        return(DDBItem[Key])

def lambda_handler(event, context):
    global Logger,DDBTableName

    logging.basicConfig()
    Logger = logging.getLogger()
    Logger.setLevel(logging.INFO)
 
    if os.environ.get("DynamoDBTableName") is not None: DDBTableName = os.environ.get("DynamoDBTableName")

    #
    # First scan for Workspaces instances that don't exist any more
    #
    DynamoDBClient = boto3.client("dynamodb")

    StartKey       = {}
    WorkspacesList = []
    while True: # Loop until no more items from the DDB scan
        Logger.info("DDB scan loop, StartKey="+str(StartKey))
        
        try:
            if len(StartKey) == 0:
                Result = DynamoDBClient.scan(TableName=DDBTableName,
                                             Select="SPECIFIC_ATTRIBUTES",
                                             AttributesToGet=["WorkspaceId","Region","ComputerName","UserName"])
            else:
                Result = DynamoDBClient.scan(TableName=DDBTableName,
                                             Select="SPECIFIC_ATTRIBUTES",
                                             AttributesToGet=["WorkspaceId","Region","ComputerName","UserName"],
                                             ExclusiveStartKey=StartKey)
        except ClientError as e:
            Logger.error("DynamoDB error: "+e.response['Error']['Message'])
            return

        for Workspace in Result["Items"]:
            WorkspacesList.append(Workspace)

        if "LastEvaluatedKey" in Result:
            StartKey = Result["LastEvaluatedKey"]
        else:
            break

    for Item in WorkspacesList:
        WorkspaceId = Deserialise(Item["WorkspaceId"])
        Region      = Deserialise(Item["Region"])

        logging.info("Looking for "+WorkspaceId+" in "+Region)
        WorkspacesClient = boto3.client("workspaces", region_name=Region)
        InstanceInfo = WorkspacesClient.describe_workspaces(WorkspaceIds=[WorkspaceId])
        if len(InstanceInfo["Workspaces"]) > 0:
            logging.info("  Instance alive - continuing")
            continue

        #
        # This instance doesn't exist any more so let's remove it from the table and from AD
        #
        if "ComputerName" in Item:
            ComputerName = Deserialise(Item["ComputerName"])
            logging.info("  Removing "+ComputerName+" from AD")

            #
            # Here we should connect to AD and remove the Computer object
            # so that stale Workspaces instances aren't left lying around
            # in the target AD.
            #
        else:
            logging.info("  No computer name found - cannot remove from AD")

        try:
            Response = DynamoDBClient.delete_item(TableName=DDBTableName, Key={"WorkspaceId":Item["WorkspaceId"]})
            logging.info("  Instance removed")
        except ClientError as e:
            Logger.error("DynamoDB error: "+e.response['Error']['Message'])
            return
            
