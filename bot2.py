from flask.globals import request
from flask.wrappers import Response
import slack
from flask import Flask
from slack.web import client
from slackeventsapi import SlackEventAdapter
import slackeventsapi
import string
from datetime import datetime, timedelta

#env variables
SLACK_TOEKEN = 'slack-token-here'
SIGNING_SECRET = 'signing-token-here'

#event adapters
app = Flask(__name__)
slack_event_adapter = SlackEventAdapter(SIGNING_SECRET, '/slack/events', app)

#create web client
client = slack.WebClient(token=SLACK_TOEKEN)

#variables
BOT_ID = client.api_call("auth.test")['user_id']
message_counts = {}
welcome_messages = {}
CODE_WORDS = ['hmm', 'no', 'tim'] # these code words are removed by check_if_code_word() fucntion
SCHEDULED_MESSAGES = [
    { 'text': 'First message', 'post_at': (datetime.now() + timedelta(seconds=40)).timestamp(), 'channel': 'C02AJFEM1R6'},
    { 'text': 'Second message', 'post_at': (datetime.now() + timedelta(seconds=50)).timestamp(), 'channel': 'C02AJFEM1R6'}
]
#welcome message
class WelcomeMessage:

    START_TEXT = {
        'type': 'section',
        'text': {
            'type': 'mrkdwn',
            'text': (
                'Welcome to this channel'
                '*Get started by completing the tasks!*'
            )
        } 
    }

    DIVIDER = { 'type': 'divider'}

    def __init__(self, channel, user):
        self.channel = channel
        self.user = user
        self.icon_emoji = ":robot_face:"
        self.timestamp = ''
        self.completed = False

    def get_message(self):
        return {
            'ts': self.timestamp,
            'channel': self.channel,
            'username': 'Welcome Robot',
            'icon_emoji': self.icon_emoji,
            'blocks': [
                self.START_TEXT,
                self.DIVIDER,
                self._get_reaction_task()
            ]
        }
    
    def _get_reaction_task(self):
        checkmark = ':white_check_mark:'
        if not self.completed:
            checkmark = ':white_large_square:'
        
        text = f'{checkmark} *React to this message*'
        return {
            'type': 'section', 
            'text': {
                'type': 'mrkdwn',
                'text': text
            }
            }
def send_welcome_message(channel, user):
    if channel not in welcome_messages:
        welcome_messages[channel] = {}

    if user in welcome_messages[channel]:
        return

    welcome = WelcomeMessage(channel, user)
    message = welcome.get_message()
    response = client.chat_postMessage(**message)
    welcome.timestamp = response['ts']

    if channel not in welcome_messages:
        welcome_messages[channel] = {}
    welcome_messages[channel][user] = welcome

#scheduling the messages
def schedule_messages(messages):
    ids = []
    for msg in messages:
        response = client.chat_scheduleMessage(channel=msg['channel'], text=msg['text'], post_at=msg['post_at'])
        id_ = response.get(id_)
        ids.append(id_)
        return ids


# fuction to check code and remove them 
def check_if_code_words(message):
    msg = message.lower()
    msg = msg.translate(str.maketrans('', '', string.punctuation))
    return any(word in msg for word in CODE_WORDS)

#reply by bot to user messages
@slack_event_adapter.on('message')
def message(payload):
    #print("payload")
    event = payload.get('event', {})
    channel_id = event.get('channel')
    user_id = event.get('user')
    text = event.get('text')

    if((user_id != None) and (user_id != BOT_ID)):
        if user_id in message_counts:
            message_counts[user_id] += 1
        else:
            message_counts[user_id] = 1
        #client.chat_postMessage(channel=channel_id, text=text)

        if text.lower() == 'start':
            #send_welcome_message(channel_id, user_id) #sending welcome msg in channel
            send_welcome_message(f'@{user_id}',user_id) #to DM the user directly
        elif check_if_code_words(text):
            ts = event.get('ts')
            client.chat_postMessage(
                channel=channel_id, thread_ts=ts, text='THAT IS A CODE WORD'
            )


#event for reaction 
@slack_event_adapter.on('reaction_added')
def reaction(payload):
    event = payload.get('event', {})
    #print(event)
    channel_id = event.get('item', {}).get('channel')
    user_id = event.get('user')

    if f'@{user_id}' not in welcome_messages:
        return
    
    welcome = welcome_messages[f'@{user_id}'][user_id]
    welcome.completed = True
    welcome.channel = channel_id
    message = welcome.get_message()
    updated_message = client.chat_update(**message)
    welcome.timestamp = updated_message['ts']


#message-count command
@app.route('/message-count', methods=['POST'])
def count_message():
    data = request.form
    #print(data)
    user_id = data.get('user_id')
    channel_id = data.get('channel_id')
    user_name = data.get('user_name')
    message_count = message_counts.get(user_id, 0)
    client.chat_postMessage(channel=channel_id, text = f"{user_name} sent total {message_count}")
    return Response(), 200

if __name__ == "__main__":
    #schedule_messages(SCHEDULED_MESSAGES)
    app.run(debug=True)
    schedule_messages(SCHEDULED_MESSAGES)
