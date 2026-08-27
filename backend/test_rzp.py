import os
import sys

from dotenv import load_dotenv
load_dotenv('../.env')

from razorpay_service.client import rzp

try:
    items = rzp.item.all()
    print('Razorpay API is WORKING.')
    print('Items fetched:', len(items['items']))
    for i in items['items'][:3]:
        print(f" - {i['name']} ({(i['amount']/100):.2f} INR)")
except Exception as e:
    print('Razorpay API FAILED:', str(e))
