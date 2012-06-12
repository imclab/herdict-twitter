"""
TODO:

Write main docstring
Fix exponential backoff

"""

import json
import logging
import time
import smtplib

import redis
import tweepy


# Import parameters.
with open('/home/rosspetchler/GSoC/Parameters.json') as f:
    par = json.loads(f.read())


# Connect to Redis.
r = redis.StrictRedis()


# Set up logging.
logging.basicConfig(filename=par['logfile'],
                    format='%(asctime)s %(levelname)-8s %(message)s',
                    level=logging.DEBUG)


# Add to Tweepy a status element object containing raw JSON.
@classmethod
def parse(cls, api, raw):
    status = cls.first_parse(api, raw)
    setattr(status, 'json', json.dumps(raw))
    return status

tweepy.models.Status.first_parse = tweepy.models.Status.parse
tweepy.models.Status.parse = parse


def email(body, subject='Herdict Twitter Error', to_addrs=par['to_addrs']):
    """Sends an email message.
    
    Sends an email message with the given subject and body message to the
    recipients specified in parameters file.
    
    Args:
        body: A string sent as the body message of the email.
        subject: A string sent as the subject line of the email.
        to_addrs: An optional list of strings, corresponding to the email
            addresses of the email recipients. Defaults to the email addresses
            specified in the parameters file.
    """
    msg = 'From: {}\r\nTo: {}\r\nSubject: {}\r\n\r\n{}\r\n'.format(
           par['from_addr'], ', '.join(to_addrs), subject, body)
    s = smtplib.SMTP('smtp.mail.yahoo.com')
    s.login(user=par['from_addr'], password=par['from_addr_password'])
    s.sendmail(par['from_addr'], to_addrs, msg)
    s.quit()


class Listener(tweepy.StreamListener):
    """Caches JSON returned by the Streaming API and handles errors."""

    def on_status(self, tweet):
        """Caches JSON returned by the Streaming API."""
        try:
            # The Twitter Streaming API mysteriously returns both JSON and
            # strings of JSON, so convert to a string for consistency.
            r.rpush('cached', str(tweet.json))
        except Exception as e:
            logging.exception(e)
            pass

    def on_error(self, status_code):
        """If an error occurs, log the error and keep the connection alive."""
        message = 'Encountered status code {}'.format(status_code)
        logging.warning(message)
        email(message)
        return True

    def on_timeout(self):
        """If a timeout occurs, log the error and keep the connection alive."""
        message = 'Timeout'
        logging.warning(message)
        email(message)
        return True


def main():
    
    # Define OAuth parameters for the Twitter API connection.
    auth = tweepy.OAuthHandler(par['twitter_consumer_key'],
                               par['twitter_consumer_secret'])
    auth.set_access_token(par['twitter_access_token'],
                          par['twitter_access_token_secret'])
    
    # Convert empty lists of parameters to None.
    follow = None if par['follow'] == [] else par['follow']
    track = None if par['track'] == [] else par['track']
    
    # Stream and filter Tweets.
    delay = 10
    for max_errors in range(20):
        try:
            stream = tweepy.Stream(auth=auth, listener=Listener(),
                                   timeout=None, secure=True)
            stream.filter(follow, track)
        except Exception as e:
            logging.exception(e)
            email(e.message)
            time.sleep(delay)
            delay = delay ** 2
            if delay >= 240:
                delay = 240
    
    # Send termination email notice and shut down.
    email('Herdict Twitter Termination')
    logging.shutdown()


if __name__ == '__main__':
    
    main()


