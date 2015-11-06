import json
import jsonpickle
import requests
from flask import request

import gator.config
from gator.flask import app
from gator import common
from gator import models

def add_handler(ip_address, expires):
    data = {
        "ip_address": ip_address,
        "expires": expires
    }
    models.handlers.put_item(data=data, overwrite=True)
    return data

def get_handlers():
    query = models.handlers.scan()
    return [h._data for h in query]

def purge_handlers():
    query = models.handlers.scan()
    time = common.get_current_timestamp()
    for handler in query:
        if handler["expires"] < time:
            handler.delete()

def notify_handlers(transaction_uuid):
    transaction = models.transactions.get_item(uuid=transaction_uuid, consistent=True)._data
    payload = jsonpickle.encode({"result": 0, "transaction": transaction})
    handlers = models.handlers.scan()
    headers = {"Content-Type": "application/json"}
    port = gator.config.store["notifier_host"]["recv_port"]

    for handler in handlers:
        url = "http://%s:%s/transaction_change" % (handler["ip_address"], port)
        try:
            requests.post(url, data=payload, headers=headers, timeout=0.5)
        except requests.exceptions.RequestException:
            pass #Ignore the exception. The handler is stale

@app.route("/notify/handler", methods=["POST"])
def flask_add_handler():
    expires = (common.get_current_timestamp() / 10**6) + 60 * 60 * 12 #time + 12 hours
    ip_address = request.remote_addr
    if "x-forwarded-for" in request.headers:
        ip_address = request.headers.get("x-forwarded-for").split(",")[0]
    handler = add_handler(ip_address, expires)
    return jsonpickle.encode({"result": 0, "handler": handler})

@app.route("/notify/handler", methods=["GET"])
def flask_get_handler():
    handlers = get_handlers()
    return jsonpickle.encode({"result": 0, "handlers": handlers})

@app.route("/notify/handler", methods=["DELETE"])
def flask_purge_handlers():
    purge_handlers()
    return jsonpickle.encode({"result": 0})

@app.route("/notify/broadcast/<transaction_uuid>", methods=["POST"])
def flask_broadcast(transaction_uuid):
    notify_handlers(transaction_uuid)
    return jsonpickle.encode({"result": 0})

