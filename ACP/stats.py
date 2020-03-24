
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



########### HELPERS ################

def code_to_sis(course_code):
    middle=course_code[:-5][-6:]
    sis_id="SRS_%s-%s-%s %s" % (course_code[:-11], middle[:3],middle[3:], course_code[-5:] )
    return(sis_id)


####################################


def get_requests(outputfile='RequestSummary.csv'):
    canvas = Canvas(API_URL, API_KEY)
    my_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    #file_path = os.path.join(my_path, "ACP/data", inputfile)
    outFile = open(os.path.join(my_path, "ACP/data", outputfile),"w+")
    requests = Request.objects.all()
    outFile.write('course_code, subaccount, status, provisioned, date_created\n')
    total  = requests.count()
    counter = 1
    for r in requests:
        if counter % 25 == 0:
            print("%s/%s done" % (counter,total))
        course_code = r.course_requested.course_code
        try:
            subaccount = r.course_requested.course_schools.abbreviation
        except:
            subaccount = 'NA'
        try:
            status = r.canvas_instance.workflow_state
        except:
            status = 'NA'

        try:
            canvas_course = canvas.get_course(r.canvas_instance.canvas_id)
            datecreated = canvas_course.created_at
        except:
            datecreated = 'NA'
        
        provisioned = ''
        outFile.write('%s,%s,%s,%s,%s\n' % (course_code, subaccount, status, provisioned, datecreated))
        counter +=1


def NA_times():
    requests = ['ECON0012012020C','ESE2241042020A','ESE2241032020A','ESE2241022020A','ESE2241012020A','VPTH7890222020A','VPTH7890212020A','VPTH7890202020A','VPTH7890192020A','VPTH7114252020A','VPTH7114242020A','VPTH7114232020A','VPTH7114222020A','VPTH7114212020A','VPTH7114202020A','VPTH7114192020A','VPTH7114182020A','VPTH7114172020A','VPTH7114012020A','VPTH7104252020A','VPTH7104242020A','VPTH7104232020A','VPTH7104222020A','VPTH7104212020A','VPTH7104202020A','VPTH7104192020A','VPTH7104182020A','VPTH7104172020A','VPTH7104032020A','VPTH7104012020A','VPTH6150012020A','VMED7010222020A','VMED7000252020A','VMED7000242020A','VMED7000232020A','VMED7000222020A','VMED7000202020A','VMED7000172020A','VMED6180012020A','VISR7991412020A','VISR7991402020A','VISR7991392020A','VISR7991382020A','VISR7991372020A','VISR7991362020A','VISR7991352020A','VISR7991342020A','VISR7991332020A','VISR7991322020A','VISR7991312020A','VISR7991302020A','VISR7991292020A','VISR7991282020A','VISR7991272020A','VISR7991262020A','VISR7991252020A','VISR7991242020A','VISR7991232020A','VISR7991222020A','VISR7991212020A','VISR7991202020A','VISR7991192020A','VISR7991182020A','VISR7991172020A','VISR7991162020A','VISR7991152020A','VISR7991142020A','VISR7991132020A','VISR7991122020A','VISR7991112020A','VISR7991102020A','VISR7991092020A','VISR7991082020A','VISR7991072020A','VISR7991062020A','VISR7991052020A','VISR7991042020A','VISR7991032020A','VISR7991022020A','VISR7991012020A','VISR7991002020A','VISR7990992020A','VISR7990982020A','VISR7990972020A','VISR7990962020A','VISR7990952020A','VISR7990942020A','VISR7990932020A','VISR7990922020A','VISR7990912020A','VISR7990902020A','VISR7990892020A','VISR7990882020A','VISR7990872020A','VISR7990862020A','VISR7990852020A','VISR7990842020A','VISR7990832020A','VISR7990822020A','VISR7990812020A','VISR7990802020A','VISR7990792020A','VISR7990782020A','VISR7990772020A','VISR7990762020A','VISR7990752020A','VISR7990742020A','VISR7990732020A','VISR7990722020A','VISR7990712020A','VISR7990702020A','VISR7990692020A','VISR7990682020A','VISR7990672020A','VISR7990662020A','VISR7990652020A','VISR7990642020A','VISR7990632020A','VISR7990622020A','VISR7990612020A','VISR7990602020A','VISR7990592020A','VISR7990582020A','VISR7990572020A','VISR7990562020A','VISR7990552020A','VISR7990542020A','VISR7990532020A','VISR7990522020A','VISR7990512020A','VISR7990502020A','VISR7990492020A','VISR7990482020A','VISR7990472020A','VISR7990462020A','VISR7990452020A','VISR7990442020A','VISR7990432020A','VISR7990422020A','VISR7990412020A','VISR7990402020A','VISR7990392020A','VISR7990382020A','VISR7990372020A','VISR7990362020A','VISR7990352020A','VISR7990342020A','VISR7990332020A','VISR7990322020A','VISR7990312020A','VISR7990302020A','VISR7990292020A','VISR7990282020A','VISR7990272020A','VISR7990262020A','VISR7990252020A','VISR7990242020A','VISR7990232020A','VISR7990222020A','VISR7990212020A','VISR7990202020A','VISR7990192020A','VISR7990182020A','VISR7990172020A','VISR7990162020A','VISR7990152020A','VISR7990142020A','VISR7990132020A','VISR7990122020A','VISR7990112020A','VISR7990102020A','VISR7990092020A','VISR7990082020A','VISR7990072020A','VISR7990062020A','VISR7990052020A','VISR7990042020A','VISR7990032020A','VISR7990022020A','VISR7990012020A','VISR6990852020A','VISR6990402020A','VISR6990192020A','VISR6990182020A','VISR6990172020A','VISR6990162020A','VISR6990152020A','VISR6990142020A','VISR6990132020A','VISR6990122020A','VISR6990112020A','VISR6990102020A','VISR6990092020A','VISR6990072020A','VISR6990062020A','VISR6990052020A','VISR6990042020A','VISR6990022020A','VISR6990012020A','VCSP8800252020A','VCSP8800242020A','VCSP8800232020A','VCSP8800222020A','VCSP8800212020A','VCSP8800202020A','VCSP8800192020A','VCSP8800182020A','VCSP8800172020A','VCSP8800012020A','VCSP8790252020A','VCSP8790242020A','VCSP8790232020A','VCSP8790222020A','VCSP8790212020A','VCSP8790202020A','VCSP8790192020A','VCSP8790182020A','VCSP8790172020A','VCSP8780252020A','VCSP8780242020A','VCSP8780232020A','VCSP8780222020A','VCSP8780212020A','VCSP8780202020A','VCSP8780192020A','VCSP8780182020A','VCSP8780172020A','VCSP8780012020A','VCSP8770012020A','VCSP8760252020A','VCSP8760242020A','VCSP8760232020A','VCSP8760222020A','VCSP8760212020A','VCSP8760202020A','VCSP8760192020A','VCSP8760182020A','VCSP8760172020A','VCSP8760022020A','VCSP8760012020A','VCSP8750012020A','VCSP8734032020A','VCSP8734022020A','VCSP8734012020A','VCSP8720252020A','VCSP8720242020A','VCSP8720232020A','VCSP8720222020A','VCSP8720212020A','VCSP8720202020A','VCSP8720192020A','VCSP8720182020A','VCSP8720172020A','VCSP8720012020A','VCSP8714022020A','VCSP8174252020A','VCSP8174242020A','VCSP8174232020A','VCSP8174222020A','VCSP8174212020A','VCSP8174202020A','VCSP8174192020A','VCSP8174182020A','VCSP8174172020A','VCSP8154252020A','VCSP8154242020A','VCSP8154232020A','VCSP8154222020A','VCSP8154212020A','VCSP8154202020A','VCSP8154192020A','VCSP8154182020A','VCSP8154172020A','VCSP8154012020A','VCSP8144252020A','VCSP8144242020A','VCSP8144232020A','VCSP8144222020A','VCSP8144212020A','VCSP8144202020A','VCSP8144192020A','VCSP8144182020A','VCSP8144172020A','VCSP8134252020A','VCSP8134242020A','VCSP8134232020A','VCSP8134222020A','VCSP8134212020A','VCSP8134202020A','VCSP8134192020A','VCSP8134182020A','VCSP8134172020A','VCSP8134012020A','VCSP8114252020A','VCSP8114242020A','VCSP8114232020A','VCSP8114222020A','VCSP8114212020A','VCSP8114202020A','VCSP8114192020A','VCSP8114182020A','VCSP8114172020A','VCSP8114022020A','VCSP8004252020A','VCSP8004242020A','VCSP8004232020A','VCSP8004222020A','VCSP8004212020A','VCSP8004202020A','VCSP8004192020A','VCSP8004182020A','VCSP8004172020A','VCSP8004012020A','VCSP8000012020A','VCSP7824222020A','VCSP7774012020A','VCSP7224252020A','VCSP7224242020A','VCSP7224232020A','VCSP7224222020A','VCSP7224212020A','VCSP7224202020A','VCSP7224192020A','VCSP7224182020A','VCSP7224172020A','VCSP7214252020A','VCSP7214242020A','VCSP7214232020A','VCSP7214222020A','VCSP7214212020A','VCSP7214202020A','VCSP7214192020A','VCSP7214182020A','VCSP7214172020A','VCSP7214012020A','VCSP7184252020A','VCSP7184242020A','VCSP7184232020A','VCSP7184222020A','VCSP7184212020A','VCSP7184202020A','VCSP7184192020A','VCSP7184182020A','VCSP7184172020A','VCSP7174252020A','VCSP7174242020A','VCSP7174232020A','VCSP7174222020A','VCSP7174212020A','VCSP7174202020A','VCSP7174192020A','VCSP7174182020A','VCSP7174172020A','VCSP7164252020A','VCSP7164242020A','VCSP7164232020A','VCSP7164222020A','VCSP7164212020A','VCSP7164202020A','VCSP7164192020A','VCSP7164182020A','VCSP7164172020A','VCSP7160012020A','VCSP7154252020A','VCSP7154242020A','VCSP7154232020A','VCSP7154222020A','VCSP7154212020A','VCSP7154202020A','VCSP7154192020A','VCSP7154182020A','VCSP7154172020A','VCSP7154012020A','VCSP7124252020A','VCSP7124242020A','VCSP7124232020A','VCSP7124222020A','VCSP7124212020A','VCSP7124202020A','VCSP7124192020A','VCSP7124182020A','VCSP7124172020A','VCSP7104252020A','VCSP7104242020A','VCSP7104232020A','VCSP7104222020A','VCSP7104212020A','VCSP7104202020A','VCSP7104192020A','VCSP7104182020A','VCSP7104172020A','VCSP7000242020A','VCSP7000222020A','VCSP7000192020A','VCSP7000172020A','VCSP6680012020A','VCSP6670012020A','VCSN8850252020A','VCSN8850232020A','VCSN8850212020A','VCSN8850202020A','VCSN8850192020A','VCSN8840252020A','VCSN8840242020A','VCSN8840232020A','VCSN8840222020A','VCSN8840212020A','VCSN8840202020A','VCSN8840192020A','VCSN8840182020A','VCSN8840172020A','VCSN8830252020A','VCSN8830242020A','VCSN8830232020A','VCSN8830222020A','VCSN8830212020A','VCSN8830202020A','VCSN8830192020A','VCSN8830182020A','VCSN8830172020A','VCSN8810202020A','VCSN8790252020A','VCSN8790242020A','VCSN8790232020A','VCSN8790222020A','VCSN8790212020A','VCSN8790202020A','VCSN8790192020A','VCSN8790172020A','VCSN8780252020A','VCSN8780242020A','VCSN8780232020A','VCSN8780222020A','VCSN8780212020A','VCSN8770222020A','VCSN8770212020A','VCSN8754182020A','VCSN8710222020A','VCSN8710212020A','VCSN8704212020A','VCSN8704022020A','VCSN8704012020A','VCSN8164232020A','VCSN8164222020A','VCSN8164212020A','VCSN8164202020A','VCSN8154252020A','VCSN8154242020A','VCSN8154232020A','VCSN8154222020A','VCSN8154212020A','VCSN8154202020A','VCSN8154192020A','VCSN8154182020A','VCSN8154172020A','VCSN8144252020A','VCSN8144242020A','VCSN8144232020A','VCSN8144222020A','VCSN8144172020A','VCSN8004252020A','VCSN8004242020A','VCSN8004232020A','VCSN8004222020A','VCSN8004212020A','VCSN8004202020A','VCSN8004192020A','VCSN8004182020A','VCSN8004172020A','VCSN8000012020A','VCSN7770252020A','VCSN7770242020A','VCSN7770232020A','VCSN7770222020A','VCSN7770212020A','VCSN7760212020A','VCSN7740252020A','VCSN7740242020A','VCSN7740232020A','VCSN7740222020A','VCSN7730012020A','VCSN7164252020A','VCSN7164242020A','VCSN7164232020A','VCSN7164222020A','VCSN7164212020A','VCSN7154252020A','VCSN7154242020A','VCSN7154232020A','VCSN7154222020A','VCSN7154212020A','VCSN7134252020A','VCSN7134242020A','VCSN7134232020A','VCSN7134222020A','VCSN7134212020A','VCSN7134202020A','VCSN7134192020A','VCSN7134182020A','VCSN7134172020A','VCSN7014252020A','VCSN7014242020A','VCSN7014232020A','VCSN7014222020A','VCSN7014212020A','VCSN7014202020A','VCSN7014192020A','VCSN7014182020A','VCSN7014172020A','VCSN7010012020A','VCSN7004252020A','VCSN7004242020A','VCSN7004232020A','VCSN7004222020A','VCSN7004212020A','VCSN7004202020A','VCSN7004192020A','VCSN7004182020A','VCSN7004172020A','VCSN7004022020A','VCSN7004012020A','VBMS6010012020A','PSCI2377892020A','PSCI2372032020A','PSCI2372022020A','PSCI2372012020A','NURS2980032020A','NURS2552102020A','LARP5440032020A','GOMD9810012020A','GOMD9800012020A','GOMD9790012020A','GOMD9780012020A','GOMD9720012020A','GOMD9710012020A','GOMD9690012020A','CHEM0531732020A','CHEM0531722020A','CHEM0223012020A','ANCH3534012020A','HPR6129202020B','HPR5039202020B','NURS5260012020A','ENVS1003012020A','AFRC3213012020A','GRMN3010012020A','NURS2250012020A','CLST1230012020A','EALC2424012020A','MEAM3330012020A','CHIN3820022020A','AAMW6044012020A','PHIL5513012020A','ANTH3313012020A','MEAM3481042020A','MEAM3481032020A','MEAM3481022020A','MEAM3481012020A','MEAM1011052020A','MEAM1011042020A','MEAM1011032020A','MEAM1011022020A','MEAM1011012020A','BIOE5800012020A','SPAN1403102020A','ECON0010022020A','ECON0010012020A','PSCI1312042020A','PSCI1312032020A','PSCI1312022020A','PSCI1312012020A','AFRC5874012020A','PHYS1400122020A','ESE4444022020A','CHEM1026022020A','CHEM1020052020A','ENM3750012020A','SPAN1213022020A','INTR2900172020A','PSYC2530012020A','SOCI1354012020A','AFRC4204012020A','BIBB4403012020A','CHIN0320032020A','CHIN0120052020A','CHIN0120062020A','AFRC1694012020A','SWRK7980022020A','MATH1140052020A','ESE2900012020A','NURS6492012020A','ITAL1123012020A','FREN1123012020A','FREN2123042020A','FREN2143022020A','LEAD3306202020A','MUSC3303012020A','LEAD3106102020A','CHIN0120032020A','HIST2343022020A','NURS7980012020A','VCSP7784012020A','COMM8743012020A','COMM7603012020A','FREN2273022020A','NURS7960012020A','PROW1006112020A','PROW1006102020A','RUSS0024012020A','NURS5350022020A','DTCH5744012019C','FREN2253022019C','HIST2313012019C','GRMN5034012019C','PSYC4294012019C','ANTH2584012019C','BIOM5990092019B','HSOC3483012019C','FNAR5234012019C','ESE5424012019C','ARCH5354022019C','ASAM2080012019C','PHYS5614012019C','SPAN2123052019C','NELC0314012019C','NELC1014012019C','HIST1734012019C','AFRC0784012019C','LARP7610012019C','BE5180012019C','FREN1403032019C','FREN1403012019C','IPD5250012019C','PHIL0150012019C','ENGL1123012019C','ANTH0224012019C','SWRK6040042019C','CAMB7134012019C','SPAN1303042019C','GEOL1030012019C','ANTH3003012019C','SPAN2123012019C','SPAN1303022019C','ANTH0010012019C','SPAN1403052019C','SPAN2123032019C','SPAN1403022019C','NELC1364012019C','RELS1434012019C','URDU4314012019C','ARTH5804012019C','HIST2334032019C','SPAN1213092019C','SPAN1213072019C','SPAN2023032019C','SPAN2023012019C','MSE5000012019C','BIOL1231012019C','SPAN1403042019C']

    for r in requests:
        rt = Request.objects.get(course_requested=r)
        print(rt.created.strftime("%Y-%m-%dT%H:%M:00Z"))






