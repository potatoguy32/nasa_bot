import requests
import sys
from PIL import Image
import tweepy
import os
from io import BytesIO
import json

NASA_KEY = os.getenv('NASA_KEY')
DEEPL_KEY = os.getenv('DEEPL_KEY')
TWITTER_KEY = os.getenv('TWITTER_KEY')
TWITTER_SECRET = os.getenv('TWITTER_SECRET')
TWITTER_TOKEN = os.getenv('TWITTER_TOKEN')
TWITTER_TOKEN_SECRET = os.getenv('TWITTER_TOKEN_SECRET')


def make_request(method, url, params=None, headers=None):
    r = requests.request(method=method, url=url, params=params, headers=headers)
    return r.json() if r.status_code == 200 else None


def lambda_handler(event, context):
    images_url = 'https://api.nasa.gov/planetary/apod'
    translator_url = 'https://api-free.deepl.com/v2/translate'
    content = make_request(method='GET', url=images_url, params={'api_key': NASA_KEY})
    if content is None:
        content = make_request(method='GET', url=images_url, params={'api_key': NASA_KEY, 'count': 1})
        content = content[0]

    translator_response = make_request(method='POST', url=translator_url,
                                       params={'text': content['explanation'], 'target_lang': 'ES'},
                                       headers={'Authorization': f'DeepL-Auth-Key {DEEPL_KEY}'})

    translated_description = translator_response['translations'][0]['text']
    if translated_description is None:
        return {
            'body': json.dumps('There is no translation!')
        }

    tweets = translated_description.split('. ')
    if 'copyright' in content.keys():
        new_text = 'Copyright: ' + content['copyright'] + '\n' + tweets.pop(0)
        tweets.insert(0, new_text)

    # Get the image in a stream object
    hd_url = content['hdurl']
    hd_img_format = hd_url.split('.')[-1]
    hd_format = hd_img_format.upper()
    if hd_img_format == 'jpg':
        hd_format = 'JPEG'

    hd_request = requests.get(hd_url, stream=True)
    hd_img = Image.open(hd_request.raw)
    hd_bytes = BytesIO()
    hd_img.save(hd_bytes, format=hd_format)
    hd_bytesio = BytesIO(hd_bytes.getvalue())
    hd_filename = 'todays_image' + hd_format.lower()

    regular_url = content['url']
    regular_img_format = regular_url.split('.')[-1]
    regular_format = regular_img_format.upper()
    if regular_img_format == 'jpg':
        regular_format = 'JPEG'

    regular_filename = 'todays_image' + regular_format.lower()
    regular_request = requests.get(regular_url, stream=True)
    regular_img = Image.open(regular_request.raw)
    regular_bytes = BytesIO()
    regular_img.save(regular_bytes, format=regular_format)
    regular_bytesio = BytesIO(regular_bytes.getvalue())

    # Post the thread
    auth = tweepy.OAuth1UserHandler(
        consumer_key=TWITTER_KEY,
        consumer_secret=TWITTER_SECRET
    )

    auth.set_access_token(TWITTER_TOKEN, TWITTER_TOKEN_SECRET)
    api = tweepy.API(auth)
    hd_image = True
    try:
        media_response = api.chunked_upload(filename=hd_filename, file=hd_bytesio, media_category='tweet_image',
                                            wait_for_async_finalize=True, file_type=hd_format)
    except:
        media_response = api.chunked_upload(filename=regular_filename, file=regular_bytesio,
                                            media_category='tweet_image', wait_for_async_finalize=True,
                                            file_type=regular_format)
        hd_image = False

    if not hd_image:
        tweets.append(f"Puedes encontrar la imagen en HD aquí: {content['hdurl']}")

    tweet_status = api.update_status(status=tweets.pop(0), media_ids=[media_response.media_id_string, ])
    prev_tweet_id = tweet_status.id_str
    for tweet in tweets:
        current_tweet = api.update_status(status=tweet, in_reply_to_status_id=prev_tweet_id)
        prev_tweet_id = current_tweet.id_str

    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
