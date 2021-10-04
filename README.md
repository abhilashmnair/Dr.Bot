# Dr.Bot 🤖

A symptom checker with DialogFlow and Infermedica API using Flask Webhook. Infermedica is a NLP based health diagnosis and patient triage checker.

### How it works?
DialogFlow acts as the interface between user and the webhook. Text received from user is transformed into wordings and passed to the Python webhook which calls the Infermedica API endpoint and receives the response. The response is then formatted and passed back to the DialogFlow agent.

### How to run?

* Import the DialogFlow agent.

* Add the Firebase Config and Infermedica Credentials in `drbot.py`

* Run `pip install -r requirements.txt`

* Run the Python Flask App and provide the webhook URL in fulfillment of DialogFlow.

That's it!

Test your chatbot in Telegram or integrate into your website! 

**Enjoy**

---

*This is made from the [Infermedica Python Demo](https://github.com/infermedica/symptom-checker-chatbot-example). Infermedica Documentation is available [here](https://developer.infermedica.com/docs/introduction). <br>
Make a PR if you get a bug. :)*
