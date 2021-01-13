import json
import datetime
import time
import os
import dateutil.parser
import logging
import boto3
import random

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


# --- Helpers that build all of the responses ---


def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit,
            'message': message
        }
    }


def confirm_intent(session_attributes, intent_name, slots, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ConfirmIntent',
            'intentName': intent_name,
            'slots': slots,
            'message': message
        }
    }


def close(session_attributes, fulfillment_state, message):
    response = {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState': fulfillment_state,
            'message': message
        }
    }

    return response


def delegate(session_attributes, slots):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Delegate',
            'slots': slots
        }
    }


# --- Helper Functions ---


def safe_int(n):
    """
    Safely convert n value to int.
    """
    if n is not None:
        return int(n)
    return n


def try_ex(func):
    """
    Call passed in function in try block. If KeyError is encountered return None.
    This function is intended to be used to safely access dictionary.

    Note that this function would have negative impact on performance.
    """

    try:
        return func()
    except KeyError:
        return None


def isvalid_date(date):
    try:
        dateutil.parser.parse(date)
        return True
    except ValueError:
        return False


def get_day_difference(later_date, earlier_date):
    later_datetime = dateutil.parser.parse(later_date).date()
    earlier_datetime = dateutil.parser.parse(earlier_date).date()
    return abs(later_datetime - earlier_datetime).days


def add_days(date, number_of_days):
    new_date = dateutil.parser.parse(date).date()
    new_date += datetime.timedelta(days=number_of_days)
    return new_date.strftime('%Y-%m-%d')


""" --- Functions that control the bot's behavior --- """


def check_order(intent_request):

    order_num = try_ex(lambda: intent_request['currentIntent']['slots']['OrderNumber'])
    order_num = str(order_num)

    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}

    order_query = json.dumps({
        'Order_number': order_num
    })

    session_attributes['orderQuery'] = order_query

    if intent_request['invocationSource'] == 'DialogCodeHook':
        return delegate(session_attributes, intent_request['currentIntent']['slots'])

    # backend stuff
    logger.debug(' Pulling order info for={}'.format(order_query))
    dynamodb = boto3.client('dynamodb')
    
    response = dynamodb.scan(TableName='Product-Orders')
    logger.debug(response)
    
    response_items = response['Items']
    
    content_message = ""
    order_details = {}
    for order in response_items:
        if order['OrderNumber']['S'] == order_num:
            order_details = order
    
    for key, value in order_details.items():
        content_message += key + ": " + list(value.values())[0] + " | "
    
    if not content_message:
        content_message += "No items for that criteria found!"

    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': content_message
        }
    )
    
    
    
    
    
def place_order(intent_request):

    prod_name = try_ex(lambda: intent_request['currentIntent']['slots']['ProductName'])
    prod_name = str(prod_name)

    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}

    prod_query = json.dumps({
        'Prod_name': prod_name
    })

    session_attributes['prodQuery'] = prod_query

    if intent_request['invocationSource'] == 'DialogCodeHook':
        return delegate(session_attributes, intent_request['currentIntent']['slots'])

    # backend stuff
    logger.debug(' Pulling product availability for={}'.format(prod_query))
    dynamodb = boto3.client('dynamodb')
    
    response = dynamodb.scan(TableName='Product-Information')
    logger.debug(response)
    
    response_items = response['Items']
    
    content_message = ""
    prod_avail = {}
    for prod in response_items:
        item_name = prod['item']['S']
        if prod['product_id']['S'].lower() == prod_name.lower() and int(prod['inventory']['N']) > 0:
            
            inventory_amount = int(prod['inventory']['N'])
            
            # putitem into table-orders and update_item inventory -1
            order_check_response = dynamodb.scan(TableName='Product-Orders')
            order_check_response_items = order_check_response['Items']
            
            existing_orders = []
            for item in order_check_response_items:
                for key, value in item.items():
                    if key == 'OrderNumber':
                        existing_orders.append(int(list(value.values())[0]))
            
            # create unique order number
            new_order_number = 0
            while True:
                new_order_number = random.randint(10000, 99999)
                if new_order_number not in existing_orders:
                    break
            
            # get timestamp
            new_order_timestamp = datetime.datetime.now()
            
            # insert order
            dynamodb = boto3.resource('dynamodb')
            put_order_table = dynamodb.Table('Product-Orders')
            put_order_table.put_item(
                Item = {
                    'OrderNumber': str(new_order_number),
                    'OrderTimestamp': str(new_order_timestamp),
                    'Product': str(item_name),
                    'Status': 'In Transit',
                    'ProductID': prod_name.upper()
                }    
            )
            # inventory_amount -= 1
            
            # dynamodb = boto3.resource('dynamodb')
            # update_inventory_table = dynamodb.Table('Product-Information')
            # update_inventory_table.update_item(
            #     Key = {
            #         'product_id': prod_name.upper()
            #     },
            #     UpdateExpression = 'SET inventory = :newInventory',
            #     ExpressionAttributeValues = {
            #         ':newInventory': inventory_amount
            #     }
            # )
            
            content_message += "Success! Your order for " + item_name + "has been placed. "
            content_message += "Use the order number " + str(new_order_number) + " to check the progress of your order. Thank you!"
            
        elif prod['product_id']['S'].lower() == prod_name.lower() and int(prod['inventory']['N']) <= 0:
            content_message += "No " + item_name + "s in stock! Please try again at a later time."

    
    # for key, value in prod_avail.items():
    #     content_message += key + ": " + list(value.values())[0] + " | "
    
    if not content_message:
        content_message += "No items for that criteria found!"

    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': content_message
        }
    )


# --- Intents ---


def dispatch(intent_request):
    """
    Called when the user specifies an intent for this bot.
    """

    logger.debug('dispatch userId={}, intentName={}'.format(intent_request['userId'], intent_request['currentIntent']['name']))

    intent_name = intent_request['currentIntent']['name']

    # Dispatch to your bot's intent handlers
    if intent_name == 'CheckOrderStatus':
        return check_order(intent_request)
    elif intent_name == 'PlaceOrder':
        return place_order(intent_request)

    raise Exception('Intent with name ' + intent_name + ' not supported')


# --- Main handler ---


def lambda_handler(event, context):
    """
    Route the incoming request based on intent.
    The JSON body of the request is provided in the event slot.
    """
    # By default, treat the user request as coming from the America/New_York time zone.
    os.environ['TZ'] = 'America/New_York'
    time.tzset()
    logger.debug('event.bot.name={}'.format(event['bot']['name']))

    return dispatch(event)
