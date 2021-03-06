from flask import request

from gator.flask import app
import gator.core.models as models
import gator.logic.transactions as transactions
import gator.config as config

from gator.core.models import Model, Customer, CFields, Transaction, TFields, MTypes
from gator.core.common import TransactionStates, Platforms, Errors, GatorException, \
                              validate_phonenumber
from gator.core.auth import validate_permission, Permission, validate_token
from gator.core.service import sms

import jsonpickle
import re

def get_sms_customer(phone_number):
    query = [c for c in models.customers.query_2(index="phone_number-index",
            phone_number__eq=phone_number, limit=1)]
    if len(query) == 0:
        customer = Customer.create_new({
            CFields.PHONE_NUMBER: phone_number
        })
        customer.create()
        return customer
    else:
        customer = Customer(query[0])
        return customer

def get_sms_transaction(customer_uuid):
    open_sms = transactions.get_open_sms_transaction(customer_uuid)
    if open_sms is not None:
        return open_sms

    transaction = transactions.create_transaction({
        TFields.CUSTOMER_UUID: customer_uuid,
        TFields.CUSTOMER_PLATFORM_TYPE: Platforms.SMS
    })
    transaction.create()
    return transaction

@app.route('/sms/handle_sms', methods=["POST"])
def handle_sms():
    # Authenticate the request
    token = request.args.get("token", "")
    validate_permission(validate_token(token), [Permission.API_SMS])

    customer_phone_number = request.values["From"]
    text_message_body = request.values["Body"]

    # Check to see if the message was a HELP message
    if re.match("^\s*HELP\s*$", text_message_body, flags=re.IGNORECASE) is not None:
        sms.send_msg(body=config.HELP_MESSAGE_1, to=customer_phone_number)
        sms.send_msg(body=config.HELP_MESSAGE_2, to=customer_phone_number)
        return jsonpickle.encode({"result": 0})

    customer = get_sms_customer(customer_phone_number)
    transaction = get_sms_transaction(customer[CFields.UUID])
    transactions.send_message(transaction, text_message_body, True, MTypes.TEXT)

    # Send the customer a confirmation message if its the first message
    if len(transaction[TFields.MESSAGES]) == 1:
        sms.send_msg(body=config.CONFIRMATION_MESSAGE, to=customer_phone_number)

    return jsonpickle.encode({"result": 0})

@app.route('/sms/open/<phone_number>', methods=["POST"])
def open_sms(phone_number):
    validate_phonenumber(phone_number)
    validate_permission(validate_token(request.args.get("token", "")),
                        [Permission.ALL_DELEGATORS])

    data = jsonpickle.decode(request.data.decode("utf-8"))
    if TFields.DELEGATOR_UUID not in data:
        raise GatorException(Errors.DATA_NOT_PRESENT)

    customer = get_sms_customer(phone_number)
    open_sms = transactions.get_open_sms_transaction(customer[CFields.UUID])
    if open_sms is not None:
        raise GatorException(Errors.OPEN_SMS_EXISTS)

    transaction = transactions.create_transaction({
        TFields.CUSTOMER_UUID: customer[CFields.UUID],
        TFields.CUSTOMER_PLATFORM_TYPE: Platforms.SMS,
        TFields.DELEGATOR_UUID: data[TFields.DELEGATOR_UUID]
    })
    transaction.create()
    return jsonpickle.encode({
        "transaction_uuid": transaction[TFields.UUID],
        "customer_uuid": customer[CFields.UUID],
        "result": 0
    })

phones_greeted = set({})
@app.route("/sms/sendgreeting/<phone_number>", methods=["POST"])
def send_greeting(phone_number):
    global phones_greeted

    # Make sure we only text this number once (from this node)
    if phone_number in phones_greeted:
        raise GatorException(Errors.PERMISSION_DENIED)

    phones_greeted.add(phone_number)

    # Send help message and app link
    sms.send_msg(body=config.HELP_MESSAGE_1,   to=phone_number)
    sms.send_msg(body=config.APP_LINK_MESSAGE, to=phone_number)

    # Create the customer items
    customer = Customer.create_new({CFields.PHONE_NUMBER: phone_number})
    customer.create()

    return jsonpickle.encode({"result": 0})
