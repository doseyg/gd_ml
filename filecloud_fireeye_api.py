#!/usr/bin/env python
import requests
import xmltodict
import json
import datetime, dateutil.parser, time

filecloud_server="https://hostname/"
filecloud_user="user"
filecloud_pass="pass"
filecloud_path="/path/"
fireeye_server="https://hostname/"
fireeye_user="user"
fireeye_pass="pass"
tmp_file_dir="./"
verify_ssl=False



filecloud_auth={"userid":filecloud_user , "password": filecloud_pass}
cookies=""
submissions=[]
if verify_ssl == False:
	requests.packages.urllib3.disable_warnings() 

ZERO = datetime.timedelta(0)
class UTC(datetime.tzinfo):
  def utcoffset(self, dt):
    return ZERO
  def tzname(self, dt):
    return "UTC"
  def dst(self, dt):
    return ZERO
utc = UTC()


def filecloud_authenticate():
	global filecloud_auth, cookies
	url = filecloud_server + "/core/" + "loginguest"
	r = requests.post(url, params=filecloud_auth)
	text = r.text
	cookies = r.cookies
	try:
		my_xml = xmltodict.parse(text)
	except:
		## Not XML
		print("Page did not return valid XML")
	
	if my_xml["commands"]["command"]["result"] == str(1):
		print("DEBUG: Successful login")
		return r.cookies
	else:
		print("Login failed:" + str(my_xml["commands"]["command"]["message"]) )
		exit()
		
def filecloud_getfilelist(path):
	global cookies
	params={"path":path}
	r = requests.post(filecloud_server + "/core/" + "getfilelist", cookies=cookies, params=params)
	text = r.text
	##print("Debug: " + text)
	try:
		my_xml = xmltodict.parse(text)
	except:
		## Not XML
		print("Page did not return valid XML")
	#print("Debug: " + str(my_xml))
	#print(my_xml["entries"]["entry"]["name"])
	##FIXME if no files or a single file, return an appropriate result
	return my_xml["entries"]["entry"]


			
def filecloud_downloadfile(path,filename):
	global cookies
	params={"filepath":entry["path"], "filename": entry["name"]}
	r = requests.get(filecloud_server + "downloadfile", cookies=cookies, params=params)
	data = r.content
	f = open(tmp_file_dir + entry["name"], "wb")
	f.write(data)
	f.close

def fireeye_authenticate():
        #url = "http://10.101.2.39/wsapis/v2.0.0/auth/login"
        url = fireeye_server + "/wsapis/v2.0.0/auth/login"
        headers = {"X-FeClient-Token":"doe-api"}
        r = requests.post(url, auth=requests.auth.HTTPBasicAuth(fireeye_user,fireeye_pass), headers=headers, verify=False)
        auth_token = r.headers["x-feapi-token"]
        headers.update({"X-FeApi-Token": auth_token})
        return headers

def fireeye_submit(filename):
		global headers
		url = fireeye_server + "/wsapis/v1.1.0/submissions"
		payload = { "options": '{"application":"0", "timeout":"120", "priority":"0", "profiles":["winxp-sp3"],"analysistype":"0","force":"false","prefetch":"1"}' }
		global headers
		with open(filename, 'rb') as file_content:
			submitted_file = {'filename': file_content}
			r = requests.post(url, headers=headers, verify=False, data=payload, files=submitted_file)
		if r.status_code == 200:
				print("Submitted file" + filename)
				submission_id = r.json()[0]['ID']
				#print("DEBUG: " + submission_id)
				return submission_id
		else:
			print("Error submitting file" + filename)

def fireeye_submission_status(submission_id):
		global headers
		url = fireeye_server + "/wsapis/v1.1.0/submissions/status/" + submission_id
		r = requests.get(url, headers=headers, verify=False)
		status = json.loads(r.text)
		return status['submissionStatus']

def fireeye_submission_results(submission_id):
		global headers
		url = fireeye_server + "/wsapis/v1.1.0/submissions/results/" + submission_id
		r = requests.get(url, headers=headers, verify=False)
		report = r.text
		return report
	
cookies = filecloud_authenticate()
file_list = filecloud_getfilelist(filecloud_path,)
new_date = datetime.datetime.now(utc) - datetime.timedelta(minutes=95) - datetime.timedelta(minutes=240)
headers = fireeye_authenticate()
for entry in file_list:
	##print(entry)
	modified_date = dateutil.parser.parse(entry["modifiediso"])
	##print(str(new_date) + "  " + str(modified_date))
	if modified_date > new_date:
		print ("Downloading from FileCloud: " + str(entry["name"]) )
		filecloud_downloadfile(entry["path"],entry["name"])
		submission_id = fireeye_submit(tmp_file_dir + entry["name"])
		submissions.append(submission_id)
	else:
		print ("Debug: file is too old: " + entry["name"] )

loop = True
while loop == True:
	time.sleep(5)
	for submission_id in submissions:
		print ("Querying " + submission_id)
		status = fireeye_submission_status(submission_id)
		if status == "Done":
			report = fireeye_submission_results(submission_id)
			print (report)
			submissions.remove(submission_id)
	if len(submissions) == 0:
		print ("All reports finished, exiting...")
		loop = False
exit()
