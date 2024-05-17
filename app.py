import os

from slack_bolt import App


app = App(
    token=os.getenv('AWS_MANAGER_SLACK_BOT_TOKEN'),
    signing_secret=os.getenv('AWS_MANAGER_SLACK_SIGNING_SECRET'),
)


@app.message()
def handle_user_message(message, say):
    text = message['text']
    ...


if __name__ == '__main__':
    app.start(port=int(os.getenv('AWS_MANAGER_DEV_SLACK_PORT')))
