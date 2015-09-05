from flask import request

import time
import sys

import jsonpickle

import gator.models
import gator.common

from gator import app
from gator.models import Customer, Message, Delegator, Transaction
from gator.common import Errors, TransactionStatus

@app.after_request
def after_request(response):
    #TODO - Important Security - replace '*' with name of the server hosting the delegator web client
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
    return response

@app.route('/')
def index():
    return "GatorRestService is up and running!"

@app.route('/core/customer', methods=['POST'])
def create_customer():
    data_dict = jsonpickle.decode(request.data.decode("utf-8"))

    if not set(["phone_number"]) <= set(data_dict.keys()):
        return gator.common.error_to_json(Errors.DATA_NOT_PRESENT)

    customer = Customer.create_from_dict(data_dict)

    if not customer.is_unique():
        return gator.common.error_to_json(Errors.CUSTOMER_ALREADY_EXISTS)

    gator.models.customers.put_item(data=customer.get_data())

    return jsonpickle.encode({"result": 0, "uuid": customer.uuid}, unpicklable=False)

@app.route('/core/customer/<uuid>', methods=['GET'])
def customer(uuid):
    if not gator.models.customers.has_item(uuid=uuid, consistent=True):
        return gator.common.error_to_json(Errors.CUSTOMER_DOES_NOT_EXIST)

    customer = gator.models.customers.get_item(uuid=uuid, consistent=True)

    to_return = {"result": 0}
    to_return.update(customer._data)
    return jsonpickle.encode(to_return, unpicklable=False)

@app.route('/core/delegator', methods=['POST'])
def create_delegator():
    data_dict = jsonpickle.decode(request.data.decode("utf-8"))

    if not set(["phone_number", "email", "first_name", "last_name"]) <= set(data_dict.keys()):
        return gator.common.error_to_json(Errors.DATA_NOT_PRESENT)

    delegator = Delegator(
            first_name=data_dict["first_name"],
            last_name=data_dict["last_name"],
            phone_number=data_dict["phone_number"],
            email=data_dict["email"])

    if not delegator.is_unique():
        return gator.common.error_to_json(Errors.DELEGATOR_ALREADY_EXISTS)

    gator.models.delegators.put_item(data=delegator.get_data())

    return jsonpickle.encode({"result": 0, "uuid": delegator.uuid}, unpicklable=False)

@app.route('/core/delegator', methods=['GET'])
def list_delegators():
    query = gator.models.delegators.scan()
    return jsonpickle.encode({
        "result": 0,
        "delegators": [delegator._data for delegator in query]},
        unpicklable=False)

@app.route('/core/delegator/<uuid>', methods=['GET', 'PUT'])
def delegator(uuid):
    if not gator.models.delegators.has_item(uuid=uuid, consistent=True):
        return gator.common.error_to_json(Errors.DELEGATOR_DOES_NOT_EXIST)

    delegator = gator.models.delegators.get_item(uuid=uuid, consistent=True)

    to_return = {"result": 0}
    to_return.update(delegator._data)
    return jsonpickle.encode(to_return, unpicklable=False)

@app.route('/core/send_message/<transaction_uuid>', methods=['POST'])
def send_message(transaction_uuid):
    data_dict = jsonpickle.decode(request.data.decode("utf-8"))

    if not set(["from_customer", "content", "platform_type"]) <= set(data_dict.keys()):
        return gator.common.error_to_json(Errors.DATA_NOT_PRESENT)

    if not gator.models.transactions.has_item(uuid=transaction_uuid, consistent=True):
        return gator.common.error_to_json(Errors.TRANSACTION_DOES_NOT_EXIST)

    transaction = gator.models.transactions.get_item(uuid=transaction_uuid, consistent=True)

    message = Message(
        from_customer=data_dict["from_customer"],
        content=data_dict["content"],
        platform_type=data_dict["platform_type"])

    if transaction["messages"] is None:
        transaction["messages"] = []

    transaction["messages"].append(message.get_data())

    # Save data to the database
    transaction.save()

    return jsonpickle.encode({
            "result": 0,
            "timestamp": message.timestamp
        }, unpicklable=False)

@app.route('/core/get_messages/<transaction_uuid>', methods=['GET'])
def get_messages(transaction_uuid):
    if not gator.models.transactions.has_item(uuid=transaction_uuid, consistent=True):
        return gator.common.error_to_json(Errors.TRANSACTION_DOES_NOT_EXIST)

    transaction = gator.models.transactions.get_item(uuid=transaction_uuid, consistent=True)

    to_return = {"result": 0}

    if transaction["messages"] is not None:
        to_return.update({"messages": [message for message in transaction["messages"]]})
    else:
        to_return.update({"messages": None})

    return jsonpickle.encode(to_return, unpicklable=False)

@app.route('/core/transaction', methods=['POST'])
def create_transaction():
    data_dict = jsonpickle.decode(request.data.decode("utf-8"))

    if not set(["customer_uuid"]) <= set(data_dict.keys()):
        return gator.common.error_to_json(Errors.DATA_NOT_PRESENT)

    if not gator.models.customers.has_item(uuid=data_dict["customer_uuid"], consistent=True):
        return gator.common.error_to_json(Errors.CUSTOMER_DOES_NOT_EXIST)

    customer = gator.models.customers.get_item(uuid=data_dict["customer_uuid"], consistent=True)

    # NOTE: client can only make transactions in the started state
    transaction = Transaction(
            customer_uuid=data_dict["customer_uuid"],
            status=TransactionStatus.STARTED)

    # Add the transaction to the transaction table
    gator.models.transactions.put_item(data=transaction.get_data())

    # Add the transaction uuid to the customer
    if customer["transaction_uuids"] is None:
        customer["transaction_uuids"] = []

    customer["transaction_uuids"].append(transaction.uuid)
    customer.save()

    return jsonpickle.encode({"result": 0, "uuid": transaction.uuid}, unpicklable=False)

@app.route('/core/transaction/<uuid>', methods=['GET', 'PUT'])
def transaction(uuid):
    if not gator.models.transactions.has_item(uuid=uuid, consistent=True):
        return gator.common.error_to_json(Errors.TRANSACTION_DOES_NOT_EXIST)

    if request.method == 'PUT':
        data_dict = jsonpickle.decode(request.data.decode("utf-8"))

        transaction = gator.models.transactions.get_item(uuid=uuid, consistent=True)
        transaction._data.update(data_dict)

        transaction.save()

        return jsonpickle.encode({"result": 0}, unpicklable=False)
    elif request.method == 'GET':
        transaction = gator.models.transactions.get_item(uuid=uuid, consistent=True)

        to_return = {"result": 0, "transaction": transaction._data}
        return jsonpickle.encode(to_return, unpicklable=False)
