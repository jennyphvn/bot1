import json
import datetime
import time
import os
import dateutil.parser
import logging
import boto3

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


def getProductInformation(intent_request):
    
    product_category = try_ex(lambda: intent_request['currentIntent']['slots']['ProductCategory'])
    product_category = str(product_category)
    min_price = try_ex(lambda: intent_request['currentIntent']['slots']['MinPrice'])
    min_price = float(min_price)
    max_price = try_ex(lambda: intent_request['currentIntent']['slots']['MaxPrice'])
    max_price = float(max_price)
    
    if product_category.lower() == "computers":
        product_category = "PCs"
    elif product_category.lower() == "accessories":
        product_category = "Accessories"
    elif product_category.lower() == "printers":
        product_category = "Printers"
        
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}

    # Load confirmation history and track the current reservation.
    product_query = json.dumps({
        'ProductCategory': product_category,
        'min_price': min_price,
        'max_price': max_price
    })

    session_attributes['productQuery'] = product_query

    if intent_request['invocationSource'] == 'DialogCodeHook':
        return delegate(session_attributes, intent_request['currentIntent']['slots'])

    # Booking the hotel.  In a real application, this would likely involve a call to a backend service.
    logger.debug('Pulling item info for={}'.format(product_query))
    dynamodb = boto3.client('dynamodb')
    
    response = dynamodb.scan(TableName='Product-Information')
    logger.debug(response)
    
    response_items = response['Items']
    
    content_message = ""
    for product in response_items:
        if product['item category']['S'] == product_category and max_price > float(product['price']['N']) > min_price:
            content_message += product['item']['S'] + ": $" + str(product['price']['N']) + " Product ID: " + product['product_id']['S'] + " | "
    
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


# may remove this one if no time
def compare_products(intent_request):
    
    product_category = try_ex(lambda: intent_request['currentIntent']['slots']['ProductCategory'])
    product_category = str(product_category)
    min_price = try_ex(lambda: intent_request['currentIntent']['slots']['MinPrice'])
    min_price = float(min_price)
    max_price = try_ex(lambda: intent_request['currentIntent']['slots']['MaxPrice'])
    max_price = float(max_price)
    
    if product_category.lower() == "computers":
        product_category = "PCs"
    elif product_category.lower() == "accessories":
        product_category = "Accessories"
    elif product_category.lower() == "printers":
        product_category = "Printers"
        
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}

    # Load confirmation history and track the current reservation.
    product_query = json.dumps({
        'ProductCategory': product_category,
        'min_price': min_price,
        'max_price': max_price
    })

    session_attributes['productQuery'] = product_query

    if intent_request['invocationSource'] == 'DialogCodeHook':
        return delegate(session_attributes, intent_request['currentIntent']['slots'])

    # Booking the hotel.  In a real application, this would likely involve a call to a backend service.
    logger.debug('Pulling item info for={}'.format(product_query))
    dynamodb = boto3.client('dynamodb')
    
    response = dynamodb.scan(TableName='HP-Product-Info')
    logger.debug(response)
    
    response_items = response['Items']
    
    content_message = ""
    for product in response_items:
        if product['item category']['S'] == product_category and max_price > float(product['price']['N']) > min_price:
            content_message += product['item']['S'] + ": $" + str(product['price']['N']) + " | "
    
    if not content_message:
        content_message += "No items for that criteria found!"
    
    return close(
        session_attributes,
        'Fulfilled',
        {
            # https://docs.aws.amazon.com/lex/latest/dg/howitworks-manage-prompts.html#message-groups
            'contentType': 'PlainText',
            'content': content_message
        }
    )


def product_details(intent_request):
    
    product_id = try_ex(lambda: intent_request['currentIntent']['slots']['ProductID'])
    product_id = str(product_id)
        
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}

    product_query = json.dumps({
        'ProductSearched': product_id,
    })

    session_attributes['productQuery'] = product_query

    if intent_request['invocationSource'] == 'DialogCodeHook':
        return delegate(session_attributes, intent_request['currentIntent']['slots'])

    # backend response
    logger.debug('Pulling item info for={}'.format(product_query))
    
    dynamodb = boto3.client('dynamodb')
    
    response = dynamodb.scan(TableName='Product-Information')
    logger.debug(response)
    
    response_items = response['Items']
    
    content_message = ""
    product_details = {}
    for product in response_items:
        if product['product_id']['S'].lower() == product_id:
            product_details = product
    
    for key, value in product_details.items():
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


# --- Intents ---


def dispatch(intent_request):
    """
    Called when the user specifies an intent for this bot.
    """

    logger.debug('dispatch userId={}, intentName={}'.format(intent_request['userId'], intent_request['currentIntent']['name']))

    intent_name = intent_request['currentIntent']['name']

    # Dispatch to your bot's intent handlers
    if intent_name == 'GetProductInfo':
        return getProductInformation(intent_request)
    elif intent_name == 'CompareProducts':
        return compare_products(intent_request)
    elif intent_name == 'SpecificProductDetails':
        return product_details(intent_request)

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
