import hashlib
import re
import pandas as pd
from .models import *
import random
from datetime import datetime

# ==========Validate Mobile number function===============
def mobile_number_validation(mobileno):

    mobile_startwith = '6,7,8,9'
    mobile_length = 10

    regex = re.compile('[@_!#$%^&*()<>?/}{~:.+=`?,;"| ]')
    if pd.isnull(mobileno) or mobileno == '':
        return 'mobile number should not be empty..!'
    elif not mobileno.isdigit():
        return 'Please give only numbers.'
    elif not mobileno.startswith(tuple(mobile_startwith)):
        return 'mobile number should start with {}..!'.format(mobile_startwith)
    elif regex.search(mobileno) is not None:
        return 'mobile number should not contain any special character (@_!#$%^&*()<>?/}{~:.+=`?,;"| )'
    elif len(mobileno) < mobile_length:
        return 'mobile number length not less than {}..!'.format(mobile_length)
    elif len(mobileno) > mobile_length:
        return 'mobile number length not greater than {}..!'.format(mobile_length)