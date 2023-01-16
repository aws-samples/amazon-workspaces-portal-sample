## Amazon Workspaces Self Service Portal Sample

## Introduction
`amazon-workspaces-portal-sample` provides code for building a serverless end-user portal for manging Amazon Workspaces instances across multiple regions. It was introduced [in this blog post](https://aws.amazon.com/blogs/desktop-and-application-streaming/creating-a-self-service-portal-for-amazon-workspaces-end-users/) which has further details about the architecture and initial setup.

The intention is that end-users (particularly when there are many of them) should not have to login to the AWS console in order to manage (stop, start, reboot or rebuild) their Workspaces instnace. The portal also provides Workspaces administrators the ability to perform the same functions for multiple workspaces. End-users can only manage instances that "belong" to them.

## Architecture

There are four Lambda functions:
 - lambda_workspaces_import.py
   - Periodically scans for Workspaces instances in regions it is configured to do so. Details are stored in a DynamoDB table.
 - lambda_workspaces_reaper.py
   - Periodically scans the DynamoDB table and deletes Workspaces instances that are in the database but don't exist in the listed region any more.
 - lambda_list_instances.py
   - Called from the web front end (via API Gateway) to return a list of Workspaces instances specific to the end-user or administrator that is logged in.
 - lambda_workspaces_actions.py
   - Called from the web front end (via API Gateway) to perform actions on specific Workspaces instances.

As mentioned, there is a DynamoDB table while holds Workspaces instance details and API Gateway is used to received requests from the web front-end. Amazon S3 is used to store the static HTML for the web page (this should be customised with your corporate logo). The use of Amazon CloudFront is also recomendeded to deliver custom domain names and HTTPS support for the web front end.

Amazon Congito is used to authenticate users to the portal. It needs to be federated with Active Directory to provide a consistent username/password experience for the end-userrs. Federation also allows Active Directory to pass back group membership information that identifies end-users and administrators. The Lambda functions use the identities to ensure that users are only accessing Workspaces instances they are authorised to; and the API Gateway methods are authorised by Cognito.

## License Summary

This sample code is made available under a modified MIT license. See the LICENSE file.
