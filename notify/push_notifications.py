import json
import urllib2

config_file = open("./config.json", "r")
config = json.loads(config_file.read())

BASE_URL = "http://%s:%s" % (config["api_host"]["name"], config["api_host"]["recv_port"])
SEND_PUSH_NOTIFICATION_ENDPOINT = "%s/push/send_push_notification/" % BASE_URL

# Handles dynamodb event stream request
def handler(event, context):
    # Make sure the event is an update
    root = event["Records"][0]["dynamodb"]
    if root.get("OldImage") is None or "messages" not in root["NewImage"]:
        print("Exiting: Transaction contains no messages")
        return

    new_item = root["NewImage"]
    old_item = root["OldImage"]

    # Important/Required fields
    platform_type = new_item["customer_platform_type"]["S"]
    new_last_message = new_item["messages"]["L"][-1]["M"]
    from_customer = new_last_message["from_customer"]["BOOL"]
    old_last_message = old_item["messages"]["L"][-1]["M"] if "messages" in old_item else None

    # Return if the platform isn't ios, the last message was sent by the
    # customer, or the transaction update didn't include a new message
    if platform_type != "ios" or from_customer or new_last_message == old_last_message:
        print("Exiting: not ios or no new messages")
        return

    # Request data
    customer_uuid = new_item["customer_uuid"]["S"]
    transaction_uuid = new_item["uuid"]["S"]
    message = new_last_message["content"]["S"]

    print("Sending push notification to %s with timestamp %s" %
            (transaction_uuid, new_last_message["timestamp"]["N"]))
    req = urllib2.Request(
        "%s%s/%s" % (SEND_PUSH_NOTIFICATION_ENDPOINT, customer_uuid, transaction_uuid),
        json.dumps({"message": message}),
        {"Content-Type": "application/json"})

    f = urllib2.urlopen(req)
    f.close()
