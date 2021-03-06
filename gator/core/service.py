""" The service initializer

This file is responsible for intializing the appropriate service by determining
if the system is in test or production mode
"""

import os
import json
import logging
import requests

import stripe
from twilio.rest import TwilioRestClient
import boto.dynamodb2
from boto.dynamodb2.layer1 import DynamoDBConnection
import boto.sns

import gator.config as config

# Global services. Initalized at bottom
sms = None
shorturl = None
dynamodb = None
sns = None

#######################
# Service Definitions #
#######################

class SmsService(object):
    def is_connected(self):
        return True

    def send_msg(self, to, body, _from="+15123593557"):
        logging.info("TEST: Sent SMS to {} from {} with body: {}".format(to, _from, body))

class TwilioService(SmsService):
    def __init__(self, account_sid, auth_token):
        self.twilio = TwilioRestClient(account_sid, auth_token)

    def is_connected(self):
        return len(self.twilio.accounts.list()) > 0

    def send_msg(self, to, body, from_="+15123593557"):
        sms_chunks = [body[i : i + config.MAX_TWILIO_MSG_SIZE]
                for i in range(0, len(body), config.MAX_TWILIO_MSG_SIZE)];

        for msg in sms_chunks:
            self.twilio.messages.create(body=msg, to=to, from_=from_)

class ShortUrlService(object):
    def shorten_url(self, long_url):
        logging.info("TEST: shortened url {}".format(long_url))
        return long_url

class GoogleUrlService(object):
    def __init__(self, key):
        self.api_url = 'https://www.googleapis.com/urlshortener/v1/url?key={}'.format(key)

    def shorten_url(self, long_url):
        data = json.dumps({'longUrl': long_url})
        headers = {'Content-Type': 'application/json'}

        try:
            resp = requests.post(self.api_url, data=data, headers=headers, timeout=2.0)
        except requests.exceptions.RequestException as e:
            logging.exception(e)
        else:
            if resp.status_code == 200:
                return resp.json()["id"]
            else:
                logging.warning("Received bad status code from google api: %s\n\n%s",
                        resp.status_code, resp.text)
        return long_url

class SNSService(object):
    def create_platform_endpoint(self, platform_application_arn, token):
        logging.info("TEST: created platform endpoint (%s)" % token)
        return {'CreatePlatformEndpointResponse':
                    {'CreatePlatformEndpointResult':
                    {'EndpointArn': 'LOCAL_ENDPOINT_ARN'}}}

    def delete_endpoint(self, endpoint_arn):
        logging.info("TEST: deleted platform endpoint (%s)" % endpoint_arn)

    def publish(self, **kwargs):
        logging.info("TEST: send publish message")

##########################
# Service Initialization #
##########################

def _create_sms():
    cnfg = config.store["twilio"]
    if cnfg["account_sid"] is not None and cnfg["auth_token"] is not None:
        return TwilioService(cnfg["account_sid"], cnfg["auth_token"])
    else:
        return SmsService()

def _create_dynamodb():
    cnfg = config.store["dynamodb"]
    if cnfg["endpoint"] is not None:
        logging.info("Connecting to local dynamodb instance")
        return DynamoDBConnection(
            aws_access_key_id='foo',
            aws_secret_access_key='bar',
            host=cnfg["endpoint"]["hostname"],
            port=cnfg["endpoint"]["port"],
            is_secure=False)
    else:
        logging.info("Connecting to aws dynamodb instance")
        return boto.dynamodb2.connect_to_region(
                         cnfg["region"],
                         aws_access_key_id=cnfg["access_key"],
                         aws_secret_access_key=cnfg["secret_key"])


def _create_urlshortener():
    key = config.store["google"]["api_key"]
    if key is None:
        return ShortUrlService()
    else:
        return GoogleUrlService(key)

def _setup_stripe():
        stripe.api_key = config.store["stripe"]["secret_key"]
        stripe.api_version = config.store["stripe"]["version"]

def _create_sns():
    cnfg = config.store["sns"]
    if not cnfg["use_local"]:
        return boto.sns.connect_to_region(
            cnfg["region"],
            aws_access_key_id=cnfg["access_key"],
            aws_secret_access_key=cnfg["secret_key"],
        )
    else:
        return SNSService()

sms = _create_sms()
dynamodb = _create_dynamodb()
shorturl = _create_urlshortener()
sns = _create_sns()
_setup_stripe()
