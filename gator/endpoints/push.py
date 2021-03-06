import jsonpickle
import logging
from boto.exception import BotoServerError

from flask import request
from gator.flask import app
from gator.core.service import sns
from gator.core.models import push_endpoints
from gator.core.common import GatorException, Errors

@app.route("/push/send_push_notification/<customer_uuid>/<transaction_uuid>", methods=["POST"])
def send_push_notification(customer_uuid, transaction_uuid):
    """
        Sends push notifications to all of the devices registered to the
        given `customer_uuid`
    """
    data = jsonpickle.decode(request.data.decode("utf-8"))

    if not set(["message"]) <= set(data.keys()):
        raise GatorException(Errors.DATA_NOT_PRESENT)

    # Get all device id's associated with a customer
    query_result = push_endpoints.query_2(
        index="customer_uuid-index",
        customer_uuid__eq=customer_uuid
    )

    # Publish to all of the push_endpoints
    for item in query_result:
        try:
            sns.publish(
                target_arn=item["endpoint_arn"],
                message=data["message"]
            )
        except BotoServerError as e:
            # Ignore these. It probably means that the user didn't allow
            # push notifications
            logging.exception(e)

    return jsonpickle.encode({"result": 0})
