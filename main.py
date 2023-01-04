import os
import sys
import datetime
import time
from pyicloud import PyiCloudService
from geopy.geocoders import GoogleV3
from geographiclib.geodesic import Geodesic
from geographiclib.constants import Constants
from twilio.rest import Client
from geopy.geocoders import Nominatim
import yaml

with open ("C:/Users/Ugly/OneDrive/Desktop/CS/Programming/Projects 2/GeoFencer/config.yml", 'r') as ymlfile:
    cfg = yaml.safe_load(ymlfile)
os.environ["TZ"] = "America/New_York"

account_sid = cfg['account_sid']
auth_token = cfg['auth_token']
client = Client(account_sid, auth_token)
geolocation = GoogleV3(api_key=cfg['google_api_key'])
api = PyiCloudService(cfg['username'], cfg['pass'], verify=True)

if api.requires_2fa:
    print("Two-factor authentication required.")
    code = input("Enter the code you received of one of your approved devices: ")
    result = api.validate_2fa_code(code)
    print("Code validation result: %s" % result)

    if not result:
        print("Failed to verify security code")
        sys.exit(1)
    if not api.is_trusted_session:
        print("Session is not trusted. Requesting trust...")
        result = api.trust_session()
        print("Session trust result %s" % result)
    if not result:
        print("Failed to request trust.")
        sys.exit(1)

def geoFence(id, dist):
    friend = api.friends.location_of(id)
    if friend is not None:
        fence = [] 
        fence = getFence((friend['latitude'], friend['longitude']), dist)
        return fence
    else:
        print("Friend not found")
        return False
def getEndpoint(lat1, lon1, bearing, d):
    geod = Geodesic(Constants.WGS84_a, Constants.WGS84_f)
    d = geod.Direct(lat1, lon1, bearing, d)
    return d['lat2'], d['lon2']

def getFence(coord, dist):
    lat1 = coord[0]
    lon1 = coord[1]
    north = getEndpoint(lat1, lon1, 0, dist)
    east = getEndpoint(lat1, lon1, 90, dist)
    south = getEndpoint(lat1, lon1, 180, dist)
    west = getEndpoint(lat1, lon1, 270, dist)
    return [north, east, south, west]

def isInside(coord, fence):
    lat = coord[0]
    lon = coord[1]

    if lat > fence[2][0] and lat < fence[0][0] and lon > fence[3][1] and lon < fence[1][1]:
        return True
    else:
        return False
def SelfFence(dist):
    myself = api.iphone.location()
    fence = []
    fence = getFence((myself['latitude'], myself['longitude']), dist)
    return fence

def getInfo():
    print("Friends:")
    for friend in api.friends.contact_details:
        print(f"Name: {friend.get('firstName')} {friend.get('lastName')} -- Phone: {friend.get('phones')} -- ID: {friend.get('id')}")

def get_components(address):
    geolocator = Nominatim(user_agent="geoapiExercises")
    #address = geolocation.geocode(components={'country': 'US', 'postal_code': '33409', 'route': '2700 Vandiver Dr', 'locality': 'West Palm Beach', 'administrative_area': 'FL', })
    location = geolocator.geocode(address)
    return location.latitude, location.longitude

def trackFriend(id, dist, method="inside", addressToFence=None):
    contacts = api.friends.contact_details
    for contact in contacts:
        if ''.join(ch for ch in contact['firstName'] if ch.isalnum()).lower() == id.lower() or ''.join(ch for ch in contact['lastName'] if ch.isalnum()).lower() == id.lower():
            name = contact['firstName'] + " " + contact['lastName']
            id = contact['id']
            break
        if contact['id'] == id:
            name = contact['firstName'] + " " + contact['lastName']
            break

    friend = api.friends.location_of(id)
    try:
        address = geolocation.reverse((friend['latitude'], friend['longitude']))
    except:
        print(friend)
        return
    fence = geoFence(id, dist)

    if addressToFence is not None:
        latitude = get_components(addressToFence)[0]
        longitude = get_components(addressToFence)[1]
        fence = getFence((latitude, longitude), dist)

    tracking = True
    if not friend:
        print("Friend ID not valid")
        return
    if method=="inside":
        while(tracking):
             friend = api.friends.location_of(id)
             if isInside((friend['latitude'], friend['longitude']), fence):
                print(f"{datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')}: {name} is within {dist} meters of {address.address}")
             elif not isInside((friend['latitude'], friend['longitude']), fence):
                print(f"{datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')}: {name} has left the area of {address.address} and is now at {friend['latitude']}, {friend['longitude']}. Tracking will continue until {name} is within {dist} meters of {address.address}")

                message = client.messages \
                    .create(
                         body=f"{datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')}: {name} has left the area of {address.address} and is now at {friend['latitude']}, {friend['longitude']}. Tracking will continue until {name} is within {dist} meters of {address.address}",
                        from_='+13515296587',
                        to='+17034022341'
                    )
                time.sleep(300)
             time.sleep(30)
    elif method=="outside":
        while(tracking):
                friend = api.friends.location_of(id)
                if not isInside((latitude, longitude), fence):
                    print(f"{datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')}: {name} is outside of {dist} meters of {addressToFence}")
                elif isInside((latitude, longitude), fence):
                    print(f"{datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')}: {name} has entered the area of {addressToFence} and is now at {friend['latitude']}, {friend['longitude']}. Tracking will continue until {name} is outside of {dist} meters of {addressToFence}")
    
                    message = client.messages \
                        .create(
                            body=f"{datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')}: {name} has entered the area of {addressToFence} and is now at {friend['latitude']}, {friend['longitude']}. Tracking will continue until {name} is outside of {dist} meters of {addressToFence}",
                            from_='+13515296587',
                            to='+17034022341'
                        )
                    time.sleep(300)
                time.sleep(30)


def trackSelf(dist, method="inside"):
    myself = api.iphone.location()
    tracking = True
    address = geolocation.reverse((myself['latitude'], myself['longitude']))
    fence = SelfFence(dist)
    if method=="inside":
        while(tracking):
             myself = api.iphone.location()
             if isInside((myself['latitude'], myself['longitude']), fence):
                print(f"{datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')}: You are within {dist} meters of {address.address}")
             elif not isInside((myself['latitude'], myself['longitude']), fence):
                print(f"{datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')}: You have left the area of {address.address} and are now at {myself['latitude']}, {myself['longitude']}. Tracking will continue until you are within {dist} meters of {address.address}")

                message = client.messages \
                    .create(
                         body=f"{datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')}: You have left the area of {address.address} and are now at {myself['latitude']}, {myself['longitude']}. Tracking will continue until you are within {dist} meters of {address.address}",
                        from_='+13515296587',
                        to='+17034022341'
                    )
                time.sleep(300)
             time.sleep(30)


