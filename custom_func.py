###############################################
#Aim : To process Transition stats for block
################################################
#!/usr/local/Caskroom/miniforge/base/bin/python3
# ToDo:
# auto_parse
# cdns_rpt
# AI1 - change how the metric value are appended
# --CHECKING LAST item as IED can be wrong fi we parse only reg to reg
# --  changes in the custom_func/cf
#	--# commenting the followinfg else loop, as it was not working when the thirdpary report was not dump with -nosplit option
# 	chnaged how the net and cells were identified
# 	changed how to append the valus if the cell/net is in one line and the values are in other line
# 	for that added separate regex for the net and cell.
#       Extra space has been appended to the cell regexp -- ^\s+ at the start and \s+ at the end.
#	because of the extra spaces at the begin and end of the cell string, these extra spaces needed to be strip for printTheFile function
# 	ithe new logic is the last elif and else loop which starts after elif normalized slack loop
##
#script flow
#The scripts has 1 mandatory switch '-ct' and 3 mutually exclusive arguments/ Give timing report as an argument to this switch.
#-ct option is mandatory. The temporary files generated to update the metrics  are based on the report name.
#The scripts calls cdns_rpt function which parses timing reports and returns a dictioanry with timing path stats, timing fiedls, startpoint, endpoint dictionary and writes out endpoint pattern list.The endpoint pattern list is written in patternGP.txt.The cdns_rpt func also  dumps a timing paths stat in a file to avod processing timing reports multiple time.
#Script has 3 mutually exclusivley arguments.

#   - stagebystage statis
#timingReportTriagerv2 
# added support to fileter wit startpoint and endpoint.

################################################
import re
import pprint
import argparse
import sys,getopt
#import timing
import calendar
import time
import subprocess
import os
import shutil
import collections
from collections import defaultdict
from collections import OrderedDict
from tabulate import tabulate
import csv
import json
import pickle
from random import random
from itertools import product
import statistics
import gzip
from pathlib import Path
##############################################
#custom help function
################################################
def custom_help (name =None):
	return '''
****************************************************
****************************************************
'''
re_st_ot = re.compile(r'.*Startpoint:.*')
re_et_ot = re.compile(r'.*Endpoint:.*')
re_pnt_ot = re.compile(r'.*Point.*')
re_dash_ot = re.compile(r'.*-$')
re_dat_ot=re.compile(r'.*data\s+arriva\s+time.*')
re_drt_ot=re.compile(r'.*data required time.*$')
re_pg_ot=re.compile(r'.*Path Group:.*$')
re_sigma_ot=re.compile(r'.*Sigma:.*$')
re_cnd_ot=re.compile(r'.*clock network delay.*$')
re_ied_ot=re.compile(r'.*input external delay.*$')
re_csl_ot=re.compile(r'.*clock source latency.*$')
re_brc=re.compile(r'.*\(.*')
re_cl=re.compile(r'.*clock\s+\w+[_]\w+[\']?\s+\(rise edge\)|.*clock\s+\w+[_]\w+[\']\s+\(fall edge\)')
#################################################
nl='\n'
#temp_dir = "run_dir"
###############################################
nested_dict = lambda: defaultdict(nested_dict)
class OrderedDefaultDict(OrderedDict):
	def __init__(self, default_factory=None, *args, **kwargs):
		super(OrderedDefaultDict, self).__init__(*args, **kwargs)
		self.default_factory = default_factory
	def __missing__(self, key):
		if self.default_factory is None:
			raise KeyError(key)
		val = self[key] = self.default_factory()
		return val
def tree():
	return OrderedDefaultDict(tree)
################################################
def deleleRepeateditems(c_n_value1):
	c_n_value3 = c_n_value1
	#c_n=re.findall(r'[-+]?\d+[.]?\d+',str(c_n_name1))
	for i in c_n_value1:
		p=re.sub(r"\s+","",i)
		c_n_value3.append(p)
	return c_n_value3


################################################
# read the file and return list of line read from
# the file.
def read_file(filename):
    if os.path.exists(filename):
        print("Reading file:", filename)
        if (re.match(r'.*.gz',filename)):
            fi1=gzip.open(filename,'rt')
        else:
            fi1=open(filename,'r')
        linelist=fi1.read().splitlines()
        fi1.close()
        cleanlinelist=[]
        for line in linelist:
            if line.strip():
                cleanlinelist.append(line)
        return cleanlinelist    
    else:
        print("File does not exists",filename)
        exit()
####################################
# filter the regex
# filter the CSV file wrt to the pattern and write out the new csv like below
# newSummary.csv
# pattern: <pattern>
# ..paths..
# ..paths..
# remaining paths
# ..paths..
# ..paths..
# repeat this pattern
#

def patternFilt(pattern,unfileteredLines , fc,numFilt=2):
    matchedLines="" ;unmatchedLines="" ;matchCount = 0 ; unmatchedCount =0
    fcn= int(fc) + 1
    matchedLines+="FILTERED:"+str(fcn)+":Start"+","+"Pattern = "+str(pattern)+'\n'
    unmatchedLines+="UNMATCHED:Start" + '\n'
    fldUser=pattern.split(":",)[0]
    pUser=pattern.split(":",)[1].strip()
    #numFilt  1: starpoint 2:endpoint
    #numFilt=2

    #if fldUser == "Startpoint":
    #    numFilt=1
    #print("Func:patternFilt, DBG1",numFilt)
    patSumDict = tree() ; wns = [] ; pg =[] ; capArr = [] ; lcArr = [] ; view = [] ; tns = 0
    for line in unfileteredLines:
        if re.match(r"^Path",line):   # check if the line starts with Path
            filtStr=line.split(",",)[numFilt]
            toMatch=filtStr.split(":",)[1].rstrip().strip()
            p1=pattern.split(":",)[1].strip()
            #print("line", line)
            #print("p1", p1 )
            #print("toMatch", toMatch)
            if re.match(p1,toMatch):
                matchedLines+=line+'\n'
                matchCount+=1
                wns.append(float(line.split(',')[7].split(':')[1]))
                tns += float(line.split(',')[7].split(':')[1])
                pg.append(line.split(',')[6].split(':')[1])
                view.append(line.split(',')[5].split(':')[1])
            else:
                unmatchedLines+=line+'\n'
                unmatchedCount+=1
    matchedLines+="FILTERED:"+str(fcn)+":End"+" Match Count = "+str(matchCount) +"\n"
    unmatchedLines+="UNMATCHED:End"+"\n"

    if matchCount > 0:
        patSumDict[pUser]=min(wns),tns,pg[0],view[0],matchCount
    return matchedLines ,unmatchedLines,patSumDict, matchCount


##
# printer
def printerD(dict1,temp_dir="run_dir"):
    #print(f"DBGINFO:printerD temp_dir is {temp_dir}")
    if  not(os.path.isdir(temp_dir)):
        os.mkdir(temp_dir)
    hdrs=["pattern", "wns","tns","group", "view" ,"count"]
    jhgf = []
    jhg = []
    ln = "pattern,wns,tns,group,view,count"+"\n"
    for k,v in dict1.items():
        #print(k,v)
        jhg.append(k)
        ln += str(k)+","
        ghcnt=0
        for i in v:
            ghcnt+=1
            jhg.append(i)
            if ghcnt == len(v):
                ln+=str(i)
            else:
                ln+=str(i)+','
        jhgf.append(jhg)
        ln += "\n"
        jhg=[]
    #print(jhgf)
    #print(tabulate(jhgf,headers=hdrs,showindex=True,tablefmt="fancy_outline",numalign="right"))
    patSummaryCsv=temp_dir+"/patSummary.csv"
    patSummaryTxt=temp_dir+"/patSummary.txt"
    with open(patSummaryTxt,"w") as fh:
        fh.write(tabulate(jhgf,headers=hdrs,showindex=True,tablefmt="fancy_outline",numalign="right"))
    with open(patSummaryCsv,"w") as fh:
        fh.write(ln)

def writeDict (dict2 , returnStr=0, theCSVname="summary.csv" , temp_dir="run_dir" ):
	#print(f"DBGINFO:writeDict temp_dir is {temp_dir}")
	theCSVDir=temp_dir
	#if  not(os.path.isdir(temp_dir)):
	#	os.mkdir(temp_dir)
	strToPrint = ''
	strToPrintCsv = ''
	strToPrintCsv2 = 'PID,'
	sp_list=[] ; ep_list=[]
	#fieldList= ['VIEW:', 'PG:', 'SP:', 'EP:', 'SIGMA:', 'CP_CLK:CLKM_ASP_CLK', 'LC_CLK:CLKM_ASP_CLK', 'DRV_ADJUST_LC:', 'DRV_ADJUST_CP:', 'SRC_LAT_CP:', 'SRC_LAT_LC:', 'NET_LAT_CP:', 'NET_LAT_LC:', 'ARR_CP:', 'ARR_LC:', 'DAT1:', 'LRT:', 'CLK_UNC:', 'CRPR:', 'DRT:', 'DP:', 'data_path:', 'SLACK:', 'Fields:']
	fieldList= ['SP:', 'EP:', 'LC_CLK:','CP_CLK:','VIEW:', 'PG:','SLACK:', 'SIGMA:','DRV_ADJUST_LC:', 'DRV_ADJUST_CP:', 'SRC_LAT_CP:', 'SRC_LAT_LC:', 'NET_LAT_CP:', 'NET_LAT_LC:', 'ARR_CP:', 'ARR_LC:', 'DAT1:', 'LRT:', 'CLK_UNC:', 'CRPR:', 'DRT:', 'DP:', 'data_path:']
	#fl2=fieldList
	#fl2.insert(0, 'PID')
	ghcnt=0
	for fld in fieldList:
		ghcnt+=1
		if ghcnt == len(fieldList):
			strToPrintCsv2+=str(fld).split(':')[0]+"\n"
		else:
			strToPrintCsv2+=str(fld).split(':')[0]+','
		
	for k,v in dict2.items():
		strToPrint += str(k)+'\t'
		strToPrintCsv += str(k)+','
		strToPrintCsv2 += str(k)+','
		ghcnt =0 
		for fld in fieldList:
			ghcnt +=1
			#print(dict2[k][fld]) 
			if dict2[k][fld] != "OrderedDefaultDict()":
				if  ghcnt == len(fieldList):
					strToPrint += str(fld)+' '+str(dict2[k][fld])+'\n'
					strToPrintCsv += str(fld)+' '+str(dict2[k][fld])+'\n'
					strToPrintCsv2 += str(dict2[k][fld])+'\n'
				else:
					strToPrint += str(fld)+' '+str(dict2[k][fld])+'\t'
					strToPrintCsv += str(fld)+' '+str(dict2[k][fld])+','
					strToPrintCsv2 += str(dict2[k][fld]) +','
		#strToPrint +='\n'
		#strToPrintCsv += '\n'
		#strToPrintCsv2 += '\n'
	#print(fieldList)
	#print(strToPrint)
	writeCsv=1
	if writeCsv ==1 :
			finame=theCSVDir+'/'+theCSVname
			with open(finame ,'w') as f:
				f.write(strToPrintCsv)
			finame2=theCSVDir+'/pure_summary.csv'
			with open(finame2,'w') as f:
				f.write(strToPrintCsv2)
	if returnStr==1:
		return strToPrintCsv


def filterSummaryCsv_ver2(dict2 ,pattern="",fname="",numFilt=2,temp_dir="run_dir"):
    #print(f"DBGINFO:filterSummaryCsv_ver2 temp_dir is {temp_dir}")
    if not(os.path.isdir(temp_dir)): 
       os.mkdir(temp_dir)
    path = temp_dir+'/filtDir'
    obj = Path(path)
    csvName = fname+'_filtered.csv'
    csvDir = path
    #print("FSVV2:Processign pattern",pattern)
    patSumDictPath=temp_dir+'/filtDir/patSumDict.dict'
    patRecordKeeperPath=csvDir+"/patRecordKeeper.txt"
    if obj.exists():
        #not filterng for the first time.
        filteredCsvPath=csvDir+'/'+csvName
        patRecordKeeper=0
        pUser=pattern.split(":",)[1].strip()
        if os.path.exists(patRecordKeeperPath):

            with open(patRecordKeeperPath,'r') as fn:
                flist=fn.read().splitlines()
            if pattern in flist:
                patRecordKeeper =1
                #print("Exiting: Pattern ",pattern ,"is already filtered.")
                #continue
                #break
        if patRecordKeeper == 0:
            if os.path.exists(filteredCsvPath):
                alreadyFilteredlines= ""
                unfileteredLines=""
                matchedLine=""
                unmatchedLine=""
                pUser=pattern.split(":",)[1].strip()
                filt_flag="" ; unmatch_flag = "" ; filt_count=0
                with open(filteredCsvPath, 'r') as f:				## read the csv
                    flist=f.read().splitlines()

                for line in flist:
                    #print(line)
                    if re.match(r"^FILTERED:.*:Start",line) :
                        filt_flag="Yes"
                        filt_count +=1
                        alreadyFilteredlines+=line + '\n'
                        #print('DBG1:filt_flag',filt_flag)
                        #print('DBG1:line',line)
                    elif re.match(r"FILTERED:.*:End", line):
                        filt_flag="No"
                        alreadyFilteredlines+=line + '\n'
                        #print('DBG2:filt_flag',filt_flag)
                        #print('DBG2:line',line)
                    elif re.match(r"^UNMATCHED:Start",line):
                        unmatch_flag="Yes"
                        unfileteredLines+=line+'\n'
                    elif re.match(r"UNMATCHED:End", line):
                        unmatch_flag="No"
                        unfileteredLines+=line+'\n'
                    elif re.match(r"^Path",line):
                        #print ("DBG1:filt_flag ",filt_flag)
                        if filt_flag == "Yes"  : #and  unmatch_flag != "Yes" :
                            alreadyFilteredlines+=line + '\n'
                            #print('DBG3:line',line)
                        elif  unmatch_flag == "Yes":
                            unfileteredLines+=line+'\n'


                ufl = unfileteredLines.split("\n")
                af = alreadyFilteredlines.split("\n")
                tch,Umtch,psd,MC=patternFilt(pattern,ufl, filt_count,numFilt)
                #for jk in af:
                #	print(jk)
                
                tempFiltCSV=temp_dir+"/tempFilt.csv"
                #tempFiltCSV="../tempFilt.csv"
                with open(tempFiltCSV,"w") as f:
                    f.write(alreadyFilteredlines)
                    f.write('\n')
                    #f.write('****************************************************')
                    #f.write('\n')
                    #f.write(unfileteredLines)
                    f.write(tch)
                    f.write('\n')
                    #f.write('****************************************************')
                    #f.write('\n')
                    f.write(Umtch)
                    f.write('\n')
                    #f.write('****************************************************')
                    #replace old csv with new on2
                    #filteredCsvPath
                #print(f"Wrote {tempFiltCSV}")
                replace_cmd = 'cd '+ csvDir + ' ;  pwd ;' + ' mv ' + csvName + ' ' + csvName + '.orig ; cp ../tempFilt.csv ' + csvName
                #print(replace_cmd)
                #print(f"csvDir {csvDir}\ncsvName {csvName}\n")
                os.system(replace_cmd)

                # update and print dict

                if MC > 0:
                    #file2=temp_dir+'/filtDir/patSumDict.dict'
                    if os.path.exists(patSumDictPath) :
                        with open(patSumDictPath,"rb") as handle2:
                            data2=handle2.read()
                            patSumDict=pickle.loads(data2)
                        patSumDict[pUser]=psd[pUser]
                        with open(patSumDictPath,"wb") as f2:
                            pickle.dump(patSumDict,f2)
                        printerD(patSumDict,temp_dir=temp_dir)
                    with open(patRecordKeeperPath,'a') as fn:
                        fn.write("\n")
                        fn.write(pattern)
                    return MC
                    
                else:
                    #print("DBG:Pattern did not match with any lines.Skipped dict update")
                    #print("DBG:Pattern did not match",pUser)
                    return MC
                #print("matchCount",matchCount)
    else:
        #filter the dictinary and create a summary.csv
        #  0      1  2   3          4   5      6    7
        #Path:2,SP:,EP,LC_CLK ,CP_CLK ,VIEW: ,PG: ,SLACK: ,SIGMA: ,DRV_ADJUST_LC: ,DRV_ADJUST_CP: ,SRC_LAT_CP: ,SRC_LAT_LC:,NET_LAT_CP: ,NET_LAT_LC: ,ARR_CP: ,ARR_LC: ,DAT1: ,LRT: ,CLK_UNC: ,CRPR: 0.000,DRT: ,DP: ,data_path: ,
        #Filtering for the first time.
        #1. Generate the summary.csv from the path dict.
        returnStr= writeDict(dict2,1,temp_dir=temp_dir )
        theLines= returnStr.split('\n',)
        #2. Initialize some vars
        patSumDict = tree() ; wns = [] ; pg =[] ; capArr = [] ; lcArr = [] ; view = [] ; tns = 0
        patSumDict1 = {}        
        if pattern != "":
	    #3. Pattern could be EP:ep_name , SP:sp_name&&EP:ep_name,
            # or just use the pure regexes
            fldUser=pattern.split(":",)[0]          #split the pattern get the field
            #print(f"DBGINFO:pattern {pattern}")
            pUser=pattern.split(":",)[1].strip()		# split the pattern get the actual pattern
            #print("pattern split ",pattern.split(":",))
            matchedLines=""  ; matchCount=0
            unmatchedLines="" ; unmatchedCount=0

            matchedLines+="FILTERED:1:Start" +","+"Pattern = "+str(pattern)+'\n'          # setting up start and end flagds
            unmatchedLines+="UNMATCHED:Start" + '\n'
            #numFilt=2
            for line in theLines:   				# fld should be stored in dict
                if re.match(r"^Path",line):   			# check if the line starts with Path
                    filtStr=line.split(",",)[numFilt]
                    toMatch=filtStr.split(":",)[1].rstrip().strip()
                    p1=pattern.split(":",)[1].strip()
                    p2=re.sub('\/','\\\/',p1)
                    #print("line",line)

                    #print("toMatch", toMatch)
                    #print("p1",p1)
                    if re.match(p1,toMatch):
                        matchedLines+=line+'\n'
                        matchCount+=1
                        wns.append(float(line.split(',')[7].split(':')[1]))
                        tns += float(line.split(',')[7].split(':')[1]) 
                        pg.append(line.split(',')[6].split(':')[1])
                        view.append(line.split(',')[5].split(':')[1])
                    else:
                        unmatchedLines+=line+'\n'
                        unmatchedCount+=1
           
            csvName = fname+'_filtered.csv'
            csvDir = temp_dir +'/filtDir'
            os.mkdir(csvDir)

            cmpltName=csvDir+'/'+csvName
            matchedLines+="FILTERED:1:End"+" Match Count = "+str(matchCount)+"\n"
            unmatchedLines+="UNMATCHED:End"+""

            with open(cmpltName,'w') as f:
                f.write(matchedLines)
                f.write('\n'+'\n'+'\n'+'\n')
                f.write(unmatchedLines)
            print("Wrote ",cmpltName)
            # update and write the dict
            pUser1 = pUser+" ("+str(matchCount)+")"
            if matchCount > 0:
                patSumDict[pUser]=min(wns),tns,pg[0],view[0],matchCount
                #file2=temp_dir+'/filtDir/patSumDict.dict'
                with open(patSumDictPath,"wb") as f2:
                    pickle.dump(patSumDict,f2)
                printerD(patSumDict,temp_dir=temp_dir)
                with open(patRecordKeeperPath,'w') as fn:
                    fn.write("\n")
                    fn.write(pattern)
                return matchCount
            else:
                #print("DBG:Pattern did not match with any lines.Skipped dict update")
                #print("DBG: Pattern did not match", pUser)
                return matchCount
            print("matchCount",matchCount)
        else:
            print("pattern not specified")
            print("Only generating summary file")

def filterPureSummaryCsv_ver2(dict2 ,pattern="",fname="",numFilt=2,temp_dir="run_dir"):
    #print(f"DBGINFO:filterSummaryCsv_ver2 temp_dir is {temp_dir}")
    if not(os.path.isdir(temp_dir)): 
       os.mkdir(temp_dir)
    path = temp_dir+'/filtDir'
    obj = Path(path)
    csvName = fname+'_filtered.csv'
    csvDir = path
    #print("FSVV2:Processign pattern",pattern)
    patSumDictPath=temp_dir+'/filtDir/patSumDict.dict'
    patRecordKeeperPath=csvDir+"/patRecordKeeper.txt"
    FL= ['PID','SP', 'EP', 'LC_CLK','CP_CLK','VIEW', 'PG','SLACK', 'SIGMA','DRV_ADJUST_LC', 'DRV_ADJUST_CP', 'SRC_LAT_CP', 'SRC_LAT_LC', 'NET_LAT_CP', 'NET_LAT_LC', 'ARR_CP', 'ARR_LC', 'DAT1', 'LRT', 'CLK_UNC', 'CRPR', 'DRT', 'DP', 'data_path']
    FLD= {'PID':'INT','SP':'STR', 'EP':'STR', 'LC_CLK':'STR','CP_CLK':'STR','VIEW':'STR', 'PG':'STR','SLACK':'FLOAT', 'SIGMA':'FLOAT','DRV_ADJUST_LC':'FLOAT', 'DRV_ADJUST_CP':'FLOAT', 'SRC_LAT_CP':'FLOAT', 'SRC_LAT_LC':'FLOAT', 'NET_LAT_CP':'FLOAT', 'NET_LAT_LC':'FLOAT', 'ARR_CP':'FLOAT', 'ARR_LC':'FLOAT', 'DAT1':'FLOAT', 'LRT':'STR', 'CLK_UNC':'FLOAT', 'CRPR':'FLOAT' , 'DRT':'FLOAT', 'DP':'FLOAT', 'data_path':'STR' } 
    if obj.exists():
        #not filterng for the first time.
        filteredCsvPath=csvDir+'/'+csvName
        patRecordKeeper=0
        pUser=pattern.split(":",)[1].strip()
        if os.path.exists(patRecordKeeperPath):

            with open(patRecordKeeperPath,'r') as fn:
                flist=fn.read().splitlines()
            if pattern in flist:
                patRecordKeeper =1
                #print("Exiting: Pattern ",pattern ,"is already filtered.")
                #continue
                #break
        if patRecordKeeper == 0:
            if os.path.exists(filteredCsvPath):
                alreadyFilteredlines= ""
                unfileteredLines=""
                matchedLine=""
                unmatchedLine=""
                pUser=pattern.split(":",)[1].strip()
                filt_flag="" ; unmatch_flag = "" ; filt_count=0
                with open(filteredCsvPath, 'r') as f:				## read the csv
                    flist=f.read().splitlines()

                for line in flist:
                    #print(line)
                    if re.match(r"^FILTERED:.*:Start",line) :
                        filt_flag="Yes"
                        filt_count +=1
                        alreadyFilteredlines+=line + '\n'
                        #print('DBG1:filt_flag',filt_flag)
                        #print('DBG1:line',line)
                    elif re.match(r"FILTERED:.*:End", line):
                        filt_flag="No"
                        alreadyFilteredlines+=line + '\n'
                        #print('DBG2:filt_flag',filt_flag)
                        #print('DBG2:line',line)
                    elif re.match(r"^UNMATCHED:Start",line):
                        unmatch_flag="Yes"
                        unfileteredLines+=line+'\n'
                    elif re.match(r"UNMATCHED:End", line):
                        unmatch_flag="No"
                        unfileteredLines+=line+'\n'
                    elif re.match(r"^Path",line):
                        #print ("DBG1:filt_flag ",filt_flag)
                        if filt_flag == "Yes"  : #and  unmatch_flag != "Yes" :
                            alreadyFilteredlines+=line + '\n'
                            #print('DBG3:line',line)
                        elif  unmatch_flag == "Yes":
                            unfileteredLines+=line+'\n'


                ufl = unfileteredLines.split("\n")
                af = alreadyFilteredlines.split("\n")
                tch,Umtch,psd,MC=patternFilt(pattern,ufl, filt_count,numFilt)
                #for jk in af:
                #	print(jk)
                
                tempFiltCSV=temp_dir+"/tempFilt.csv"
                with open(tempFiltCSV,"w") as f:
                    f.write(alreadyFilteredlines)
                    f.write('\n')
                    #f.write('****************************************************')
                    #f.write('\n')
                    #f.write(unfileteredLines)
                    f.write(tch)
                    f.write('\n')
                    #f.write('****************************************************')
                    #f.write('\n')
                    f.write(Umtch)
                    f.write('\n')
                    #f.write('****************************************************')
                    #replace old csv with new on2
                    #filteredCsvPath
                replace_cmd = 'cd '+ csvDir + ' ;' + ' mv ' + csvName + ' ' + csvName + '.orig ; cp ../tempFilt.csv  ' + csvName
                print(replace_cmd)
                #print(f"csvDir {csvDir}\ncsvName {csvName}\n")
                os.system(replace_cmd)

                # update and print dict

                if MC > 0:
                    #file2=temp_dir+'/filtDir/patSumDict.dict'
                    if os.path.exists(patSumDictPath) :
                        with open(patSumDictPath,"rb") as handle2:
                            data2=handle2.read()
                            patSumDict=pickle.loads(data2)
                        patSumDict[pUser]=psd[pUser]
                        with open(patSumDictPath,"wb") as f2:
                            pickle.dump(patSumDict,f2)
                        printerD(patSumDict,temp_dir=temp_dir)
                    with open(patRecordKeeperPath,'a') as fn:
                        fn.write("\n")
                        fn.write(pattern)
                    return MC
                    
                else:
                    #print("DBG:Pattern did not match with any lines.Skipped dict update")
                    #print("DBG:Pattern did not match",pUser)
                    return MC
                #print("matchCount",matchCount)
    else:
        print(f"In 1st loop")
        #filter the dictinary and create a summary.csv
        #  0      1  2   3          4   5      6    7
        #Path:2,SP:,EP,LC_CLK ,CP_CLK ,VIEW: ,PG: ,SLACK: ,SIGMA: ,DRV_ADJUST_LC: ,DRV_ADJUST_CP: ,SRC_LAT_CP: ,SRC_LAT_LC:,NET_LAT_CP: ,NET_LAT_LC: ,ARR_CP: ,ARR_LC: ,DAT1: ,LRT: ,CLK_UNC: ,CRPR: 0.000,DRT: ,DP: ,data_path: ,
        #Filtering for the first time.
        #1. Generate the pure_summary.csv from the path dict.
        returnStr= writeDict(dict2,1,temp_dir=temp_dir )
        theLines= returnStr.split('\n',)
        
        #2. Initialize some vars
        patSumDict = tree() ; wns = [] ; pg =[] ; capArr = [] ; lcArr = [] ; view = [] ; tns = 0
        patSumDict1 = {}        
        if pattern != "":
	    #3. Pattern could be EP:ep_name , SP:sp_name&&EP:ep_name, EP:ep_name&&(LC_CLK:lc_clk_name||CP_CLK:cp_clk_name) or any combination
            # or just use the pure regexes
            fldUser=pattern.split(":",)[0]          #split the pattern get the fi
            tnumFilt=FL.index(fldUser)
            print(f"numFilt is {tnumFilt}")
            #print(f"DBGINFO:pattern {pattern}")
            numFilt=tnumFilt
            pUser=pattern.split(":",)[1].strip()		# split the pattern get the actual pattern
            #print("pattern split ",pattern.split(":",))
            matchedLines=""  ; matchCount=0
            unmatchedLines="" ; unmatchedCount=0
            matchedLines+="FILTERED:1:Start" +","+"Pattern = "+str(pattern)+'\n'          # setting up start and end flagds
            unmatchedLines+="UNMATCHED:Start" + '\n'
            #numFilt=2
            for line in theLines:   				# fld should be stored in dict
                if re.match(r"^Path",line):   			# check if the line starts with Path
                    filtStr=line.split(",",)[numFilt]
                    toMatch=filtStr.split(":",)[1].rstrip().strip()
                    p1=pattern.split(":",)[1].strip()
                    p2=re.sub('\/','\\\/',p1)
                    #print("line",line)

                    #print("toMatch", toMatch)
                    #print("p1",p1)
                    if re.match(p1,toMatch):
                        matchedLines+=line+'\n'
                        matchCount+=1
                        wns.append(float(line.split(',')[7].split(':')[1]))
                        tns += float(line.split(',')[7].split(':')[1]) 
                        pg.append(line.split(',')[6].split(':')[1])
                        view.append(line.split(',')[5].split(':')[1])
                    else:
                        unmatchedLines+=line+'\n'
                        unmatchedCount+=1
           
            csvName = fname+'_filtered.csv'
            csvDir = temp_dir +'/filtDir'
            os.mkdir(csvDir)

            cmpltName=csvDir+'/'+csvName
            matchedLines+="FILTERED:1:End"+" Match Count = "+str(matchCount)+"\n"
            unmatchedLines+="UNMATCHED:End"+""

            with open(cmpltName,'w') as f:
                f.write(matchedLines)
                f.write('\n'+'\n'+'\n'+'\n')
                f.write(unmatchedLines)
            print("Wrote ",cmpltName)
            # update and write the dict
            pUser1 = pUser+" ("+str(matchCount)+")"
            if matchCount > 0:
                patSumDict[pUser]=min(wns),tns,pg[0],view[0],matchCount
                #file2=temp_dir+'/filtDir/patSumDict.dict'
                with open(patSumDictPath,"wb") as f2:
                    pickle.dump(patSumDict,f2)
                printerD(patSumDict,temp_dir=temp_dir)
                with open(patRecordKeeperPath,'w') as fn:
                    fn.write("\n")
                    fn.write(pattern)
                return matchCount
            else:
                #print("DBG:Pattern did not match with any lines.Skipped dict update")
                #print("DBG: Pattern did not match", pUser)
                return matchCount
            print("matchCount",matchCount)
        else:
            print("pattern not specified")
            print("Only generating summary file")

def processMultiPatterns(cdns_dict,patterns,fnam,numFilt,temp_dir="run_dir"):
    #print("DBGINFO:processMultiPatterns temp_dir ",temp_dir)
    nf=temp_dir+"/nf.txt"
    nF =open(nf,'w')
    nFC=0
    print("Length of pattern is " ,len(patterns))
    for pat in patterns:
        #print("Processing pattern=",pat)
        nfc=filterSummaryCsv_ver2(cdns_dict,pat,fnam,numFilt,temp_dir)
        if nfc == 0:
            #print("Not found pattern is",pat)
            nF.write(pat)
            nF.write("\n")
            nFC +=1
    nF.close()
    print("Not match count is",nFC)


#####
#if the length of list is 1 - then it is port -- one go substitution
#if the length of list
# default level 0 substitutew all
def generate_pattern(line,level=0):
    sub_level = level * -1
    cnt =0
    if sub_level == 0:
        l1 = re.sub('\.','.*',line)
        l2 = re.sub('\[[0-9]*\]','.*',l1)
        l3 = re.sub('\d+','.*',l2)
        l4 = re.sub('(\.\*)+','.*',l3)
        toReturn=l4
        #print (l4)
        #exit()
        cnt += 1
    else:
        lineList=line.split("/")
        #print("line is",line)

        if len(lineList) == 1:
            l1 = re.sub('\.','.*',line)
            l2 = re.sub('\[[0-9]*\]','.*',l1)
            l3 = re.sub('\d+','.*',l2)
            l4 = re.sub('(\.\*)+','.*',l3)
            toReturn=l4
            #print (l4)
            #exit()
            cnt += 1
        else:                                                 #   if len(ineList) > 1  and len(lineList) < level:
            sl0 = line.split("/")[:-1]
            # Not removing the pins
            #sl0 =  line.split("/")
            for i in range(sub_level,0):
                l1 = re.sub('\.','.*',sl0[i])
                l2 = re.sub('\[[0-9]*\]','.*',l1)
                l3 = re.sub('\d+','.*',l2)
                l4 = re.sub('(\.\*)+','.*',l3)
                sl0[i]=l4
                toReturn = '/'.join(sl0)
            cnt +=1
    '''
    if len(lineList) >= level :
        sl0 = line.split("/")[:-1]
        #Not removing pins
        #sl0 =  line.split("/")
        for i in range(sub_level,0):
            l1 = re.sub('\.','.*',sl0[i])
            l2 = re.sub('\[[0-9]*\]','.*',l1)
            l3 = re.sub('\d+','.*',l2)
            l4 = re.sub('(\.\*)+','.*',l3)
            sl0[i]=l4
            toReturn = '/'.join(sl0)
        cnt+=1
        #print(toReturn)
    '''
    return toReturn

def traceLastCommonPin(l1,l2):
    if len(l1) > 1 or len(l2) > 1:
        if len(l1) > len(l2):
            lbig = l1 ; lsmall = l2
        else:
            lbig = l2 ; lsmall = l1
        for i in range(len(lbig)):
            if len(lsmall) == i:
                return "NA" , 0
            if lbig[i] != lsmall[i]:
                lastCommonPin = lbig[i-1]
                #print("returning",lastCommonPin, i-1)
                return lastCommonPin, i-1
                break
    else: 
        #print("returning","NA",0)
        return "NA" , 0

def fmap(fline2):
    while '#' in fline2:
        fline2.remove('#')
    curr_idx = 0 
    idx=  0
    new_fl=[]
    new_dl={}
    for i in range(len(fline2)):
        idx +=1
        #print(f"FMAP DBGINFO: f  is {fline2[i]}")
        if re.match(".*\s?Timing\s?.*$",fline2[i]):
            if re.match(".*\s?Point\s?.*$",fline2[i+1] ):
                new_fl.insert(idx-1,"timing_point")
                new_dl["timing_point"]="Timing"
        elif re.match(".*\s?Point\s?.*$",fline2[i]) and re.match(".*\s?Timing\s?.*$",fline2[i-1]):
            pass
        elif re.match(".*\s?User\s?.*$",fline2[i]) and re.match(".*\s?Derate\s?.*$",fline2[i+1]):
            lowerR=fline2[i].lower()
            new_fl.insert(idx-1,"user_derate")
            new_dl["user_derate"]="USER"
        elif re.match(".*\s?Total\s?.*$",fline2[i]) and re.match(".*\s?Derate\s?.*$",fline2[i+1]):
            lowerR=fline2[i].lower()
            new_fl.insert(idx-1,"total_derate")
            new_dl["Total"]="total_derate"
        elif re.match(".*\s?Derate\s?.*$",fline2[i]) and ( re.match(".*\s?User\s?.*$",fline2[i-1]) or re.match(".*\s?Total\s?.*$",fline2[i-1]) ):
            pass
        elif re.match(".*\s?Pin\s?.*$",fline2[i]): #and re.match(".*\s?Location\s?.*$",fline2[i+1]):
            new_fl.insert(idx-1,"pin_location")
            new_dl["Pin"]="pin_location"
        #elif re.match(".*\s?Location\s?.*$",fline2[i]) and re.match(".*\s?Pin\s?.*$",fline2[i-1]):
        #    #checker=1
        #    pass
        else:
            lowerR=fline2[i].lower()
            new_fl.insert(idx-1,lowerR)
            new_dl[fline2[i]]=lowerR
    
    #print(new_fl)
    #print(len(new_fl))
    return new_fl
def cd_rpt(fi_list,level=0,numFilt=2,temp_dir="run_dir"):
    if  not(os.path.isdir(temp_dir)):
        os.mkdir(temp_dir)
    #fi_list= is list of lines from timing report file. 
    #level=level of herirachical depth to filter level 0
    #numFilt2=is the filerd with respect to patterns are generated. 2 is wrt endpoint . 1 is wrt startpoint.
    current_GMT = time.gmtime()
    #timeStampStrt = calendar.timegm(current_GMT)
    #print(timeStampStrt,"Running cdns_rpt, filt pattern level is ",level)
    #print("numFilt" ,numFilt)
    dict2= tree()
    pt_str=''
    dict3=OrderedDict()
    path_start_f=''
    path_end_f=''
    sp='' ; sp_str = ''
    ep='' 	;  ep_str = ''
    fields=[]
    pc=0 ; pc_step = 500
    tmng_pth_strt= ''
    tmng_point_strt =''
    dp_strt=''
    arrival_f=''
    dash=''
    ot_strt='' ; lastNetBeforeLaunchFlop_f = ''
    patterns =[] ;  trackEP={} 
    spEpFileNamePath=temp_dir+"/spEpFileNameCdns.rpt"
    spEpFileName=open(spEpFileNamePath,'w')
    f_map_l=[]
    lastCommonPinDict={}
    header_blocks = []
    inside = False 
    block = []

#spFileName=open('spFileNameCdns.rpt','w')
#epFileName=open('epFileNameCdns.rpt','w')
    for i in range (len(fi_list)):
        if re.match(r"^\s?Path\s+\d+:.*",fi_list[i]):
                pc+=1
                pt_str='Path:'+str(pc)
                lpc_net_l =[] ; cpc_net_l= [] ;dpc_net_l =[]; lpc_pin_l =[] ; cpc_pin_l= [] ;dpc_pin_l =[]; lpc_cell_l =[] ; cpc_cell_l= [] ;dpc_cell_l =[];
                if pc == pc_step :
                        #print("-I- Parsed CDNS path count=", str(pc) )
                        pc_step+=1000
        elif(re.match(r"^\s+View:.*",fi_list[i])):
                view=fi_list[i].split(':',)[1].strip()
                dict2[pt_str]['VIEW:']=str(view)
        elif(re.match("^\s+Group:.*",fi_list[i])):
                pg=fi_list[i].split(':',)[1].strip()
                dict2[pt_str]['PG:']=str(pg)
        elif (re_st_ot.match(fi_list[i])):
                path_start_f='yes'
                ot_strt='no'
                if (re_brc.match(fi_list[i])):
                        sp=fi_list[i].split(')',)[1].strip()
                lc_f ='yes'
                #print("DBG2:lc_f: getting set", lc_f)
                dict2[pt_str]['SP:']=str(sp.strip())
                sp_str = sp.strip()
                lastNetBeforeLaunchFlop_f = 'no'
                #print('lastNetBeforeLaunchFlop_f',lastNetBeforeLaunchFlop_f)
                #spFileName.write(sp_str)
                #spFileName.write('\n')
                if numFilt == 1 :
                    pat1 = generate_pattern(sp_str,level)
                    pat = "SP:"+pat1
                    if pat not in patterns:
                        patterns.append(pat)
                        trackEP[sp_str]=pat
        elif(re_et_ot.match(fi_list[i])):
                if (re_brc.match(fi_list[i])):
                        ep=fi_list[i].split(')',)[1].strip()
                cp_f='yes'
                dict2[pt_str]['EP:']=str(ep.strip())
                ep_str = ep.strip()
                #dict3=addValuesToDict(sp_str,dict3,[ep_str])
                ##**

                if sp.strip() not in dict3:
                        dict3[sp.strip()]=list()
                dict3[sp.strip()].extend([ep.strip()])
                ##**

                #spEpFileNameStr=sp_str+' --> '+ep_str+'\n'
                spEpFileNameStr='SP_'+sp_str+'_EP_'+ep_str+'\n'
                spep_str='SP_'+sp_str+'_EP_'+ep_str
                spEpFileName.write(spEpFileNameStr)
                #epFileName.write(ep_str)
                #epFileName.write('\n')
                #if ep_str not in trackEP:
                #print(f"numFilt is {numFilt}")
                if numFilt == 2 :
                    #print(f"Should append the pattern")
                    pat1 = generate_pattern(ep_str,level)
                    pat = "EP:"+pat1
                    if pat not in patterns:
                        patterns.append(pat)
                        trackEP[ep_str]=pat
                #print("DBG5:EP")
        elif (re.match(r"^\s+Clock:.*",fi_list[i])):
                #print("DB1: able to find clock regexp")
                if lc_f =='yes':
                        #print('abe')
                        cp_clk1 =fi_list[i].strip().split(')',)[1]
                        lc_f=''
                        appc_f='yes'
                        cp_clk='CP_CLK:'+str(cp_clk1).strip()
                        #print("DBG3 cp_clk" , cp_clk)
                        dict2[pt_str]['CP_CLK:'] = str(cp_clk1).strip()
                elif cp_f == 'yes':
                        #print('abey')
                        lc_clk1=fi_list[i].strip().split(')',)[1]                                 #cdns report parse loop contd..
                        cp_f =''
                        app_f='yes'
                        lc_clk='LC_CLK:'+str(lc_clk1).strip()
                        #print("DBG4 lc_clk" , lc_clk)
                        dict2[pt_str]['LC_CLK:'] = str(lc_clk1).strip()
        elif(re_sigma_ot.match(fi_list[i])):
                sigma=fi_list[i].split(':',)[1].strip()
                dict2[pt_str]['SIGMA:']=str(sigma)
        elif(re.match(r"^\s+Clock Edge:.*",fi_list[i])):
                c_n_value=re.findall(r'[-+]?\d+[.]?\d+',fi_list[i])
                if (appc_f == 'yes' ):
                        dict2[pt_str]['CP_CLK_PERIOD']=str(c_n_value[0])
                        #print(dict2[pt_str][str(cp_clk)])
                        appc_f='no'
                if (app_f == 'yes' ):
                        dict2[pt_str]['LC_CLK_PERIOD']=str(c_n_value[1])
                        app_f='no'
        #elif(re.match(r"",fi_list[i])):
        elif(re.match(r"^\s+Drv\s+Adjust.*",fi_list[i])):
                drv=re.findall(r'[-+]?\d+[.]?\d+',fi_list[i])
                #dict2[pt_str]['DRV_ADJUST:']=str(drv[0])
                dict2[pt_str]['DRV_ADJUST_LC:']=float(drv[1])
                dict2[pt_str]['DRV_ADJUST_CP:']=float(drv[0])
                #drvAdjustCdns_LC=float(drv[0])
                #drvAdjustCdns_CP=float(drv[1])
        elif(re.match(r"^\s+Src\s+Latency:.*",fi_list[i])):
                src_lat=re.findall(r'[-+]?\d+[.]?\d+',fi_list[i])
                dict2[pt_str]['SRC_LAT_CP:']=str(src_lat[0])
                dict2[pt_str]['SRC_LAT_LC:']=str(src_lat[1])
        elif(re.match(r"^\s+Net\s+Latency:.*",fi_list[i])):
                net_lat=re.findall(r'[-+]?\d+[.]?\d+',fi_list[i])
                dict2[pt_str]['NET_LAT_CP:']=str(net_lat[0])
                dict2[pt_str]['NET_LAT_LC:']=str(net_lat[1])
        elif(re.match(r"^\s+Arrival\:",fi_list[i])):
                arr=re.findall(r'[-+]?\d+[.]?\d+',fi_list[i])
                dict2[pt_str]['ARR_CP:']=str(arr[0])
                dict2[pt_str]['ARR_LC:']=str(arr[1])
                arrival_f = 'yes'
                dict2[pt_str]['DAT1:']=arr[0]
        elif(re.match(r"^\s+Recovery:|^\s+Setup:.*|^\s+Hold:.*",fi_list[i])):                            # librayr recovery time in OT
                rec=re.findall(r'[-+]?\d+[.]?\d+',fi_list[i])
                dict2[pt_str]['LRT:']=str(rec[0])
        elif(re.match(r"^\s+Uncertainty:.*",fi_list[i])):
                #print ("#DBG1 -- unc")
                clk_un=re.findall(r'[-+]?\d+[.]?\d+',fi_list[i])
                dict2[pt_str]['CLK_UNC:']=str(clk_un[0])
        elif(re.match(r"^\s+Cppr\s+Adjust:.*",fi_list[i])):
                crpr=re.findall(r'[-+]?\d+[.]?\d+',fi_list[i])
                dict2[pt_str]['CRPR:']=str(crpr[0])
        elif(re.match(r"^\s+Required\s+Time:.*",fi_list[i])):
                drt=re.findall(r'[-+]?\d+[.]?\d+',fi_list[i])
                dict2[pt_str]['DRT:']=str(drt[0])
        #elif(re.match(r"",fi_list[i])):
        elif(re.match(r"\s+Input\s+Delay:.*",fi_list[i])):
                ied=re.findall(r'[-+]?\d+[.]?\d+',fi_list[i])
                dict2[pt_str]['IED:']=str(ied[0])
        elif(re.match(r"^\s+Data\s+Path:.*",fi_list[i])):
                dp=re.findall(r'[-+]?\d+[.]?\d+',fi_list[i])
                dict2[pt_str]['DP:']=str(dp[0])
                #data_path_f='yes'
                if(arrival_f == 'yes'):
                        dict2[pt_str]['data_path:']=dp[0]+arr[1]
        elif(re.match(r"^\s+Slack:.*",fi_list[i])):
                slack=re.findall(r'[-+]?\d+[.]?\d+',fi_list[i])
                dict2[pt_str]['SLACK:']=str(slack[0])
        elif (re.match(r"^\s+Timing\s+Path:.*",fi_list[i])):
                dp_strt='yes'
                #ot_strt='no'
        elif(re.match(r"^\#\s+Timing\s+Point.*",fi_list[i])):
                tmng_point_strt='yes'
                if (len(fields) == 0) :
                        #print("f")
                        fields=re.sub(r'\s+',' ',fi_list[i]).strip().split(' ',)
                f_map_l=fmap(fields)
                dict2[pt_str]['Fields:']=str(f_map_l)
        elif(re.match(r"^\#-*$",fi_list[i])):
                dash='yes'
                if inside:  # closing block
                    if block:
                        header_blocks.append(block)
                    block = []
                    inside = False
                else:       # opening block
                    inside = True
        elif inside:
                block.append(fi_list[i])
        elif(re.match(r"^\s+Other\s+End\s+Path:",fi_list[i])):
                #print('in ot')
                dash='no'
                dp_strt='no'
                tmng_point_strt='no'
                ot_strt='yes'
        #elif(dash=='yes' and tmng_point_strt=='yes'):
        elif(dp_strt=='yes' or ot_strt=='yes'):  # this elif loop tries to grep cell and net names with there values and check whethere they l DP cel , Cap clk cell or Lau clk cel
            #c_n_name1=re.findall(r'[\w*[_|/]*\w*[/]?[\w]+[\d]?]*',fi_list[i])
            c_n_name1=fi_list[i].strip().split()
            #print(f"c_n_name1 {c_n_name1}")
            #print("c1",fi_list[i].strip().split())
            #c_n_value1=re.findall(r'[-+]?\d+[.]?\d+',fi_list[i])
            #c_n_value1=re.findall(r'\s+[-+]?\d+[.]?\d+',fi_list[i])
            c_n_value1=re.findall(r'\s+[-+]?\d+[.]?\d+|\s\d',fi_list[i])
            if i < (len(fi_list) -1):
                cellName_nxtLine=re.findall(r'[\w*[_|/]*\w*[/]?[\w]+[\d]?]*',fi_list[i+1])
            if (len(c_n_value1) != 0):
                #print('c_n_name',c_n_name1)
                if('arrival' in  c_n_name1):
                    if dash =='yes'  and dp_strt=='yes':
                        c_n_name='LC_pin:'+str(c_n_name1[0])
                        lpc_pin_l.append(c_n_name1[0])
                    elif dash =='yes' and ot_strt=='yes' :
                        c_n_name='CP_CLK_pin:'+str(c_n_name1[0])
                        cpc_pin_l.append(c_n_name1[0])
                elif ('net' in c_n_name1):  #### finding if its a net
                    #c_n_name='net:'+str(c_n_name1[0])
                    if dash =='yes'  and dp_strt=='yes':
                        if lastNetBeforeLaunchFlop_f != 'yes':
                            c_n_name='LC_net:'+str(c_n_name1[0])
                            lpc_net_l.append(c_n_name1[0])
                        else:
                            c_n_name='DP_net:'+str(c_n_name1[0])
                            dpc_net_l.append(c_n_name1[0])
                    elif dash =='yes' and ot_strt=='yes' :
                        c_n_name='CP_CLK_net:'+str(c_n_name1[0])
                        cpc_net_l.append(c_n_name1[0])
                else:
                    if dash =='yes'  and dp_strt=='yes':    
                        if lastNetBeforeLaunchFlop_f != 'yes':
                            c_n_name='LC_cell:'+str(c_n_name1[0])
                            lpc_cell_l.append(c_n_name1[0])
                        else:
                            c_n_name='DP_cell:'+str(c_n_name1[0])
                            dpc_cell_l.append(c_n_name1[0])
                        if(ep_str in c_n_name1):
                            dict2[pt_str]['DAT2:']=float(c_n_value1[-8].strip())
                    elif dash =='yes' and ot_strt=='yes' :
                        c_n_name='CP_CLK_cell:'+str(c_n_name1[0])
                        cpc_cell_l.append(c_n_name1[0])
                dict2[pt_str][str(c_n_name)]=c_n_value1
                # for now always updated
                dict2[pt_str]["LAUNCH_CLK_PATH_LIST"]=lpc_pin_l,lpc_net_l,lpc_cell_l
                dict2[pt_str]["CAPTURE_CLK_PATH_LIST"]=cpc_pin_l,cpc_net_l,cpc_cell_l
                dict2[pt_str]["DATAPATH_LIST"]=dpc_pin_l,dpc_net_l,dpc_cell_l
                if len(lpc_cell_l) > 1 and len(cpc_cell_l) > 1 :
                    #print("Trace starts")
                    #print("lpc_cell_l",lpc_cell_l)
                    #print("cpc_cell_l",cpc_cell_l)
                    lastCommonPin,clk_level=traceLastCommonPin(lpc_cell_l,cpc_cell_l)
                    dict2[pt_str]["lastCommonPin"]=lastCommonPin
                    lastCommonPinDict[spep_str]=lastCommonPin
            if len(cellName_nxtLine) != 0 :
                netNamePrevLine =cellName_nxtLine[0].strip()
                if sp_str == str(netNamePrevLine):
                    lastNetBeforeLaunchFlop_f ='yes'
    ##-fmap-start
    print(f'header_blocks is {header_blocks}')
    if not header_blocks:
        columns=[]
    else:
        # Take the first header block (in case multiple exist)
        header = header_blocks[0]
        # --- Process only lines starting with '#' ---
        header_lines = [l.strip("# ").rstrip() for l in header if l.strip().startswith("#")]
        # Remove any ( ... ) units
        header_lines = [re.sub(r"\([^)]*\)", "", l) for l in header_lines]    
        # Split columns by multiple spaces
        split_lines = [re.split(r"\s{2,}", l.strip()) for l in header_lines]
        # Transpose rows → columns
        max_cols = max(len(row) for row in split_lines)
        for row in split_lines:
            while len(row) < max_cols:
                row.append("")
        columns = ["_".join(filter(None, col)).strip().replace(" ", "_").lower()
                   for col in zip(*split_lines)]
    ##-fmap-end
    #f_map_l=columns
    #print("-I- Done upadting dictionary with CDNS reports ")
    print("Total number of paths parsed from CDNS report is ",pc)
    spEpFileName.close() #;spFileName.close() ; epFileName.close()
    

    dbg_patternGP=temp_dir+'/dbg_patternGP.txt'
    with open(dbg_patternGP,'w') as fh:
        for k,v in trackEP.items():
            strY=str(k)+','+str(v)+"\n"
            fh.write(strY)
    #timeStampEnd = calendar.timegm(current_GMT)
    #print(timeStampEnd,"Done running cdns_rpt, filt pattern level is ",level)
    #AMTINFO: Write the summary csv after first pass and display this instead of paths summary.
    returnStr= writeDict(dict2,1,temp_dir=temp_dir )
    print(f'column is {columns}')
    print(f'f_map_l is {f_map_l}')
    return dict2,f_map_l,dict3,patterns,lastCommonPinDict
#def cd_rpt -end
######################################################
#Sub Routines end
######################################################
