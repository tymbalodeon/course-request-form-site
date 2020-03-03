# script that creates Requests in the CRF based on the final SIS ID file.
# the requests are then all approved and proceed from this script
# also any additional site configurations are then implemented 


## ONLY RUN THIS FROM home/crf2/ in $ python3 manage.py shell 
## file = the 2nd file created in create_course_list that contains sis ids of courses that haven't been created yet.

from canvasapi import Canvas
from canvasapi.exceptions import CanvasException
from course.models import *
from datawarehouse import datawarehouse
import datetime
import os 
from .logger import canvas_logger
from .logger import crf_logger
import sys
from course.tasks import create_canvas_site
from .create_course_list import sis_id_status

"""
BEFORE YOU DO ANYTHING PLEASE SYNC INSTRUCTORS AND COURSES WITH SRS!!!
"""


######## TESTS / HELPERS ########

def test_CRF_App():
	x = Course.objects.all()
	print(x[1])

def test_reading(file):
	my_path = os.path.dirname(os.path.abspath(__file__))
	print("path",my_path)
	file_path = os.path.join(my_path, "data/", file)
	print("file path", file_path)
	dataFile = open(file_path, "r") 
	for line in dataFile:
		course = line.replace('\n',"")
		print("'"+course+"'")
		
def test_log():
	canvas_logger.info("canvas test")
	crf_logger.info("crf test?!")

def get_or_none(classmodel, **kwargs):
    try:
        return classmodel.objects.get(**kwargs)
    except classmodel.DoesNotExist:
        return None




######## CODE TO USE ########


def create_requests(inputfile='notUsedSIS.txt',copy_site=''):
	# copy_site is the canvas id of a Canvas site inwhich we'd like to copy content from. 
	owner = User.objects.get(username='mfhodges')
	my_path = os.path.dirname(os.path.abspath(sys.argv[0]))
	print("path",my_path)
	file_path = os.path.join(my_path, "ACP/data", inputfile)
	print("file path", file_path)
	dataFile = open(file_path, "r") 
	for line in dataFile:
		#FIND IN CRF	
		id = line.replace('\n',"").replace(" ","").replace("-","")
		course = get_or_none(Course,course_code=id)
		if course: #test this and? 
			# create request
			try:
				r = Request.objects.create(
					course_requested = course,
					copy_from_course = copy_site,
					additional_instructions = 'Created In Emergency Provisioning, contact courseware support for more info.',
					owner = owner,
					created= datetime.datetime.now()
				)
				r.status = 'APPROVED' # mark request as approved
				r.save()
				c.save() ## you have to save the course to update its request status !
			except:
				# report that this was failed to be created
				crf_logger.info("Failed to create request for: %s", line)

		else:
			#LOG
			crf_logger.info("Not in CRF : %s", line)
	print("-> Finished Creating Requests in CRF")
	print("-> Please now run `process_requests`")

def gather_request_process_notes(inputfile='notUsedSIS.txt'):
	# Gathers the `process_notes` for all processed requests
	# Creates a file of all of the process notes for each request (this can be used to find who has a new account)
	# Creates a file of canvas sites that have been created. 
	my_path = os.path.dirname(os.path.abspath(sys.argv[0]))
	file_path = os.path.join(my_path, "ACP/data", inputfile)
	print("file path", file_path)
	dataFile = open(file_path, "r") 
	requestResultsFile = open(os.path.join(my_path,"ACP/data","requestProcessNotes.txt"),"w+")
	canvasSitesFile = open(os.path.join(my_path,"ACP/data","canvasSitesFile.txt"),"w+")
	for line in dataFile:
		#FIND IN CRF	
		id = line.replace('\n',"").replace(" ","").replace("-","")
		course = get_or_none(Course,course_code=id)
		request = get_or_none(Request,course_requested=course)
		if request: # the request exists
			# check if stuck in process -> log error
			if request.status == 'COMPLETED':
				#find canvas site id and write that to a file with the SIS ID
				canvasSitesFile.write("%s,%s\n" % (id, request.canvas_instance.canvas_id))
				requestResultsFile.write("%s | %s\n" %(id,request.process_notes))
			else:
				canvas_logger.info("request incomplete for %s", id)
		else:
			# no request exists? thats concerning.. lets log that
			crf_logger.info("couldnt find request for %s", id)



def process_requests(file='notUsedSIS.txt'):
	# Processes in batch ? lets just see how creating 1k will work. 
	# per
	create_canvas_site() # runs the task 
	# should wait till the above task is done... 
	gather_request_process_notes(file)
	print("-> Finished Processing Requests in CRF")
	print("->(OPTIONAL) Please now run `config_sites` to ")
	pass
	


"""
		Pre-populate with Resources: copy content from a site that has resources for first time Canvas users and for async/sync online instruction. Also set on the homepage that this site has been created for ‘Academic Continuity During Disruption’. Info about the closure could also be shared.
		Storage Quota: increase the storage quota from the standard 1GB to 2GB.
		Enable LTIs: automatically configure Panopto.
		Automatically publish the site once created.
"""

"""
def config_sites(inputfile="canvasSitesFile.txt",capacity=2,tool):
	
	inc_storage(inputfile,capacity=2)
	enable_lti(inputfile,tool)
	publish_sites(inputfile)
"""

def copy_content(file,source_site):
	#check that the site exists
	try:
		pass
	except:
		# log that there is an issue
		pass
	pass

def publish_sites(file):

	pass

def enable_lti(file,tool):
	
	pass

def inc_storage(file,capacity=2):

	pass

