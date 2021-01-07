from flask import Flask,request,make_response,jsonify
import uuid
import requests
import sqlite3
import re, sys
import constants

infermedica_url = 'https://api.infermedica.com/v2/{}'
auth_string = '2876b43e:bdf95f2d0b8ea55069b381d15eeb1f6f'

mentions = []
diagnoses = []
context = []
evidence = []
case_id = uuid.uuid4().hex
db = sqlite3.connect('data.db', check_same_thread = False)
cursor = db.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS ageSex(age INT,sex VARCAHR(10),id VARCHAR)')
cursor.execute('CREATE TABLE IF NOT EXISTS evidence(id VARCAHR(10),choice_id VARCHAR(10),initial VARCHAR(10))')
db.commit()

def _remote_headers():
    app_id, app_key = auth_string.split(':')
    headers = {
        'Content-Type': 'application/json',
        'Interview-Id': case_id,
        'App-Id': app_id,
        'App-Key': app_key}
    return headers

def call_endpoint(endpoint, request_spec):
    print('calling endpoint...')
    url = infermedica_url.format(endpoint)
    headers = _remote_headers()
    if request_spec:
        resp = requests.post(
            url,
            json=request_spec,
            headers=headers)
    else:
        resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()

def call_parse(text, context=(),conc_types=('symptom', 'risk_factor',)):
    request_spec = {'text': text, 'context': list(context),'include_tokens': True, 'concept_types': conc_types}
    return call_endpoint('parse', request_spec)

def call_diagnosis(no_groups = True):
    for row in cursor.execute("SELECT age,sex FROM ageSex"):
        age = row[0]
        sex = row[1]
    db.commit()
    evidence = [ { 'id' : row[0], 'choice_id' : row[1], 'initial' : row[2] } for row in cursor.execute("SELECT id,choice_id,initial FROM evidence ") ]
    db.commit()
    print(evidence)
    
    request_spec = {
        'age': age,
        'sex': sex,
        'evidence': evidence,
        'extras': {
            'enable_adaptive_ranking': True,
            'disable_groups': no_groups
        }
    }
    return call_endpoint('diagnosis', request_spec)

def context_from_mentions(mentions):
    return [m['id'] for m in mentions if m['choice_id'] == 'present']

def get_observation_names():
    obs_structs = []
    obs_structs.extend(
        call_endpoint('risk_factors', None))
    obs_structs.extend(
        call_endpoint('symptoms', None))
    return {struct['id']: struct['name'] for struct in obs_structs}

def read_complaints(text):
    portion = read_complaint_portion(text,context)
    if portion:
        mentions.extend(portion)
        context.extend(context_from_mentions(portion))
        mentions_to_evidence(mentions)
        return 'Done...'

def read_complaint_portion(text,context):
    resp = call_parse(text, context)
    return resp.get('mentions', [])

def mentions_to_evidence(mentions):
    for m in mentions:
        cursor.execute("INSERT INTO evidence VALUES('%s','%s','%s')"%(m['id'],m['choice_id'],True))
    db.commit()

def extract_keywords(text, keywords):
    pattern = r"|".join(r"\b{}\b".format(re.escape(keyword))for keyword in keywords)
    mentions_regex = re.compile(pattern, flags=re.I)
    return mentions_regex.findall(text)

def extract_decision(text, mapping):
    decision_keywrods = set(extract_keywords(text, mapping.keys()))
    return mapping[decision_keywrods.pop().lower()]

def display(diagnoses):
    text = "Diagnoses:\n"
    for key in diagnoses:
        medical_name = str(key['name'])
        common_name = str(key['common_name'])
        text += medical_name + '( ' + common_name + ' )\n'
    cursor.execute("DELETE FROM ageSex")
    cursor.execute("DELETE FROM evidence")
    db.commit()
    text += 'This is not a complete diagnosis. Do visit your physician.'
    return text

def conduct_interview():
    while True:
        resp = call_diagnosis()
        question_struct = resp['question']
        diagnoses = resp['conditions']
        should_stop_now = resp['should_stop']
        if should_stop_now:
            text = display(diagnoses)
            return text
        question_items = question_struct['items']
        assert len(question_items) == 1
        question_item = question_items[0]
        id = question_item.get('id')
        cursor.execute("UPDATE ageSex SET id='%s'"%id)
        db.commit()
        return question_struct['text']

app = Flask(__name__)
mentions = []
context = []
evidence = []

@app.route('/')
def home():
    return 'HomePage'

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    result = req.get('queryResult')
    if result.get('action') == 'getAgeSex':
        cursor.execute("DELETE FROM ageSex")
        cursor.execute("DELETE FROM evidence")
        print(result.get('parameters'))
        age = int(result.get('parameters').get('age').get('amount'))
        sex = result.get('parameters').get('sex')
        cursor.execute("INSERT INTO ageSex VALUES('%i','%s','NULL')"%(age,sex))
        db.commit
        print('Age : ' + str(age) + ', sex : '+ sex)
        return 'Processing...'

    elif result.get('action') == 'followup':
        print(result.get('parameters'))
        for row in cursor.execute("SELECT id FROM ageSex"):
            id = row[0]
        print("test ",id)
        observation_value = extract_decision(result.get('queryText'), constants.ANSWER_NORM)
        cursor.execute("INSERT INTO evidence VALUES('%s','%s','%s')"%(id,observation_value,False))
        text = conduct_interview()
        return make_response(jsonify({
            'fulfillmentText' : text
        })) 
    
    elif result.get('action') == 'givesymptoms':
        print(result.get('parameters'))
        if result.get('queryText').lower() == 'stop':
            text = conduct_interview()
            return make_response(jsonify({
                'fulfillmentText' : text
            })) 
        else:
            read_complaints(result.get('queryText'))
            text = ""
            for element in mentions:
                text += element.get('name') + ", "
            return make_response(jsonify({
                'fulfillmentText' : text + "reported.\nType 'STOP' when done."
            }))
    elif result.get('action') == 'exit':
        sys.exit()
if __name__ == '__main__':
    app.run(debug=True)
