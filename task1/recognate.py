from tinkoff_voicekit_client import ClientSTT
from fuzzywuzzy import fuzz
from datetime import datetime
from nltk import ngrams
import uuid
import psycopg2
import os

conf_ans = {
	'negative' : ['нет', 'неудобно', 'не могу'], 
	'positive' : ['говорите', 'да конечно', 'слушаю', 'удобно'],
	'max_phrase_len' : 2
}

API_KEY = '***'
SECRET_KEY = '***'

DBNAME = '***'
USER = '***'
PASSWORD = '***'
HOST = '***'

def input_data():
	WAV_PATH = input("Input path to .wav file: ") or ''
	PHONE_NUMBER = input("Input phone number: ") or ''
	DB_FLAG = input("Input flag of db record: ") or ''
	RECOGNITION_STAGE = input("Input stage of recognition: ") or ''

	return {'wav_path' : WAV_PATH, 'phone' : PHONE_NUMBER, 'db_flag' : DB_FLAG, 'stage' : RECOGNITION_STAGE}


def send_for_recognition(api_key, secret_key, filename):
	client = ClientSTT(api_key, secret_key)

	audio_config = {
		"encoding": "LINEAR16",
        "sample_rate_hertz": 11025,
    	"num_channels": 1
	}

	response = client.recognize(filename, audio_config)

	if not response:
		error_logger("SpeechException", "send for recognation", "Unknown error")
		raise SpeechException("Unknown error\n")

	return response


def first_stage_rec(response):
	transcript = response[0]['alternatives'][0]['transcript']
	tokens = transcript.split()

	for token in tokens: 
		if fuzz.ratio(token, 'автоответчик') >= 80:
			return 0
	return 1


def second_stage_rec(response, config):
	transcript = response[0]['alternatives'][0]['transcript']
	tokens = []

	for n in range(1, config['max_phrase_len']+1):
		n_grams = ngrams(transcript.split(), n)

		for grams in n_grams:
			tokens.append(' '.join(grams))

	result = -1
	changes = 0

	phrase_contrast = {'negative' : 0, 'positive' : 1}

	for contrast in phrase_contrast:
		for phrase in config[contrast]:
			for token in tokens:
				if fuzz.ratio(token, phrase) >= 95:
					result = phrase_contrast[contrast]
					changes += 1
					break
			if result == phrase_contrast[contrast]:
				break


	if result == -1 or changes > 1: 
		error_logger("ClassificationException", "second stage recognation",
		             "Impossible to determine the class of the transcript")
		raise ClassificationException("Impossible to determine the class of the transcript")

	return result
	

def logger_file(data):
	with open('logger.txt', 'a') as file: 
		file.write("date: {0}, time: {1}, uuid: {2}, result of act: {3}, phone number: {4}, duration: {5}, result of recognation: {6}\n".format(
				data['date'], data['time'], data['uuid'], data['res_a'], data['phone'], data['duration'], data['res_r'] 
			)
		)


def logger_db(data):
	conn = psycopg2.connect(dbname=DBNAME, user=USER,
                         password=PASSWORD, host=HOST
						 )

	cursor = conn.cursor()

	cursor.execute("""CREATE TABLE IF NOT EXISTS recognation(
                    date date,
                    time time, 
                    uid uuid,
                    result_m varchar(50), 
                    phone varchar(20),
                    duration real,
                    result_r varchar(50)
                );""")
	
	cursor.execute("INSERT INTO recognation VALUES ('{0}', '{1}', '{2}', '{3}', '{4}', {5}, '{6}');".format(
		data['date'], data['time'], data['uuid'], data['res_a'], data['phone'], data['duration'], data['res_r']
	))
	
	cursor.close()
	conn.close()


def main_classifier():
	request = input_data()

	if request['wav_path']:
		response = send_for_recognition(API_KEY, SECRET_KEY, request['wav_path'])
	else:
		error_logger("Exception", "input_data", "File path was not entered")
		raise Exception("File path was not entered")

	result = -1

	if request['stage'] == '1':
		result = first_stage_rec(response)
	elif request['stage'] == '2':
		result = second_stage_rec(response, conf_ans)
	else:
		error_logger("Exception", "input_data", "Wrong format of recognation stage")
		raise Exception ("Wrong format of recognation stage\n")

	date = datetime.now()
	uid = uuid.uuid4().hex
	result_recognition = response[0]['alternatives'][0]['transcript']
	phone = request['phone']
	duration = float(response[0]['end_time'][:-1]) - \
            float(response[0]['start_time'][:-1])

	data = {
		'date': "{0}-{1}-{2}".format(date.year, date.month, date.day),
		'time' : "{0}:{1}:{2}".format(date.hour, date.minute, date.second),
		'uuid' : uid,
		'res_a': result,
		'phone': phone,
		'duration' : duration,
		'res_r': result_recognition
	}

	logger_file(data)

	if request['db_flag'] == '-db':
		logger_db(data)

	path = os.path.join(os.path.abspath(os.path.dirname(__file__)), request['wav_path'])
	os.remove(path)


def error_logger(err_type, part, err):
	with open('errors.txt', 'a') as file:
		file.write("{0} - {1} - {2}\n".format(err_type, part, err))


class ClassificationException(Exception):
	pass


class SpeechException(Exception):
	pass

# if __name__ == "__main__":
# 	main_classifier()


	
