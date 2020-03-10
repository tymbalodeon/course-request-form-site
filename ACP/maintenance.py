

"""
This code is to help do some maintence in the CRF and  in Canvas

"""

from course.models import *
from datawarehouse import datawarehouse
from datawarehouse.helpers import *
import datetime
import os 
from .logger import canvas_logger
from .logger import crf_logger
import sys
from configparser import ConfigParser
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException


config = ConfigParser()
config.read('config/config.ini')
API_URL = config.get('canvas','prod_env') #'prod_env')
API_KEY = config.get('canvas', 'prod_key')#'prod_key')


################ HELPERS ################

def get_or_none(classmodel, **kwargs):
    try:
        return classmodel.objects.get(**kwargs)
    except classmodel.DoesNotExist:
        return None


def get_user_by_sis(login_id):
    # Initialize a new Canvas object
    canvas = Canvas(API_URL, API_KEY)
    #canvas.get_user(123)
    try:
        login_id_user = canvas.get_user(login_id, 'sis_login_id')
        return login_id_user
    except:
        #print("CanvasException: ", e)
        return None


def enroll_instructors(sis_id,instructors):
    # Initialize a new Canvas object
    canvas = Canvas(API_URL, API_KEY)
    canvas_course = canvas.get_course(sis_id)
    section = canvas_course.get_sections()[0]
    for instructor in instructors:
        user = get_user_by_sis(instructor)
        if user:
            canvas_course.enroll_user(user.id, 'TeacherEnrollment' ,enrollment={'enrollment_state':'active', 'course_section_id':section.id})
        else:
            print("cant find %s" % instructor)
    print(canvas_course)



################ MAIN CODE ################

def create_instructor_updates(yearterm):
    term = yearterm[-1]
    year = yearterm[:-1]
    requests = Request.objects.filter(course_requested__course_term=term,course_requested__year=year)
    my_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    file_path = os.path.join(my_path, "ACP/data/", outputfile)
    f= open(file_path,"w+")
    for r in requests:
        course = r.course_requested

    pass



def check_canceled(yearterm,outputfile='checkingCanceled.txt'):
    term = yearterm[-1]
    year = yearterm[:-1]
    requests = Request.objects.filter(course_requested__course_term=term,course_requested__year=year)
    my_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    file_path = os.path.join(my_path, "ACP/data/", outputfile)
    f= open(file_path,"w+")
    for r in requests: 
        course = r.course_requested
        is_cancel = is_canceled(course.course_code)
        if is_cancel ==True:
            f.write("CANCELED:%s\n" % course.course_code)
        if is_cancel =='ERROR':
            f.write("ERROR:%s\n" % course.course_code)


def delete_canceled(inputfile='checkingCanceled.txt',outputfile='deletingCanceled.txt'):
    canvas = Canvas(API_URL, API_KEY)
    my_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    file_path = os.path.join(my_path, "ACP/data", inputfile)
    dataFile = open(file_path, "r") 
    outFile = open(os.path.join(my_path, "ACP/data", outFile),"w+")
    for line in dataFile:
        #FIND IN CRF	
        id = line.replace('\n',"").replace("ERROR:","").replace("CANCELED:","")
        crf_course = get_or_none(Course,course_code=id)
        sis_id = 'SRS_'+crf_course.srs_format()
        canvas_course= canvas.get_course(sis_id, use_sis_id=True)
        try:
            canvas_course.conclude()
            outFile.write("deleted %s canvas site\n" % sis_id)
        except:
            print("didnt delete %s site" % sis_id)
        try:
            crf_course.delete()
            outFile.write("deleted %s request\n" % sis_id)
        except:
            print("didnt delete %s request" % sis_id)


def update_not_in_crf(yearterm):
    term = yearterm[-1]
    year = yearterm[:-1]
    canvas = Canvas(API_URL, API_KEY)
    # EDIT THIS FOLLOWING LINE AS U NEED!
    courses =Course.objects.filter(course_term=term,year=year,requested_override=True,course_schools__visible=True,primary_crosslist='')
    for course in courses:
        # check if the sis id is in use
        sis_id = 'SRS_' + course.srs_format()
        try:
            section = canvas.get_section(sis_id, use_sis_id=True)
        except:
            #no section
            print(" no canvas section for %s" % sis_id)
            section =None
        if section:
            course.requested_override =True
            course.save()
        other_courses = Course.objects.filter(primary_crosslist=course.course_code,course_term=term,year=year,requested=False,requested_override=False,course_schools__visible=True)
        for other_course in other_courses:
            other_course.requested_override =True
            other_course.save()
        

def check_requests(yearterm):
    """
    for a given term make sure that if a crosslisted course is requested that it has its secondary pointing to the request.
    """
    term = yearterm[-1]
    year = yearterm[:-1]
    courses = Course.objects.filter(
        year=year,
        course_term=term,
        primary_crosslist__isnull=False,
        requested=False
        )
    for course in courses:
        primary_cx = get_or_none(Course,course_code=course.primary_crosslist)
        if primary_cx:
            try:
                primary_req = primary_cx.request
            except:
                #no request??? 
                print("no request found for primary course %s" % primary_cx.course_code)
                primary_req = None
            if primary_req:
                course.crosslisted_request = primary_req
                course.save()



            
