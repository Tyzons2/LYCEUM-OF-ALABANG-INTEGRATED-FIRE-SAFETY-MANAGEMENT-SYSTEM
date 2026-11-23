"""Form definitions shared by the local API and browser."""
HEAD = "LOCATION|FE #|TYPE OF FE|WEIGHT|DATE REFILLED|REFILLING DATE|SAFETY SEAL|VALVE ASSEMBLY|RELEASE LEVER|HANDLE|SAFETY PIN|PRESSURE GAUGE|HOSE|CYLINDRICAL TANK|REMARKS".split("|")
TYPES = "ABC Dry Chemical|CO2|Foam|Wet Chemical|Water|Other".split("|")
COND = "Good|Defective|Damaged|Missing|Needs Maintenance|Not Applicable".split("|")
RESULT = "Operational|Defective|For Maintenance|For Recharging|For Replacement|For Verification".split("|")
ROLES = ["Super Administrator","President / Executive Management","Vice President for Administration","Chief Administrative Officer","EHS&S Director","Safety Officer / Fire Safety Practitioner","Facilities and Maintenance Personnel","Security Office Personnel","Department Heads / Principals / Deans","Auditor / Read-Only User"]
NAMES = dict(dashboard="Executive Dashboard", fe="Fire Extinguisher Registry", inspections="Fire Extinguisher Inspection Log", equipment="Other Fire Safety Equipment", maintenance="Preventive Maintenance", capa="Corrective and Preventive Actions", hirac="HIRAC Fire Risk Assessment", incidents="Fire Incident Reporting", training="Fire Safety Training", drills="Fire Drills", emergency="Emergency Operations", fsmr="Annual FSMR Generator", compliance="Regulatory Compliance", documents="Document Repository", reports="Reports and Analytics", audit="Audit Trail", users="User Management", settings="System Settings")
FIELDS = dict(fe=HEAD+"Manufacturer|Model|Serial Number|Installation Date|Next Inspection Date|Next Service Date|Assigned Department|Maintenance Contractor".split("|"),
 inspections=["FE #","Inspection Date","Inspector"]+HEAD[6:]+["Inspection Result","Corrective Action"],
 equipment="Equipment ID|Category|LOCATION|Condition|Inspection Date|Next Service Date|Remarks",
 maintenance="Work Order|FE #|Equipment ID|LOCATION|Service Type|Assigned To|Contractor|Target Date|Completion Date|Status|Service Findings",
 capa="Deficiency|Inspection Reference|FE #|LOCATION|Priority|Immediate Control|Recommended Action|Assigned To|Target Date|Completion Date|Status|Resolution",
 hirac="Hazard|LOCATION|Activity|Exposed Persons|Likelihood|Severity|Existing Controls|Additional Controls|Assigned To|Review Date",
 incidents="Incident|Incident Date|LOCATION|Reported By|Injuries|Damage|Immediate Response|Investigation|Recommendations",
 training="Training Title|Training Date|Trainer|Department|Attendance|Evaluation|Remarks",
 drills="Drill Title|Drill Date|LOCATION|Participants|Evacuation Time|Observations|Recommendations",
 emergency="Operation|Activation Date|Incident Commander|LOCATION|Response Team|Resources|Communications|Situation Report|Outcome",
 compliance="Regulation|Legal Reference|Requirement Type|Applicable Provision|Requirement|Responsible Office|Required Evidence|Status|Verification Date|Next Review Date|Remarks",
 documents="Document Title|Category|Issue Date|Expiration Date|Responsible Office|Revision|Remarks",
 settings="Location Name|Building|Floor|Room|Department")
FIELDS={k:v.split("|") if isinstance(v,str) else v for k,v in FIELDS.items()}
CHOICES={"TYPE OF FE":TYPES, **dict.fromkeys(HEAD[6:14],COND),"PRESSURE GAUGE":["Normal","Low Pressure","High Pressure","Damaged Gauge","Not Applicable"],"Inspection Result":RESULT,"Priority":["Critical","High","Medium","Low"],"Requirement Type":["For review","Legal obligation","Recommended practice"],"Likelihood":list("12345"),"Severity":list("12345")}
STATUS={"maintenance":"Pending|Assigned|In Progress|Awaiting Parts|Awaiting Contractor|For Verification|Completed|Cancelled","capa":"Open|Assigned|In Progress|For Verification|Closed","compliance":"For Review|Evidence Pending|Verified Compliant|Deficiency Identified|Not Applicable"}
PREFIX=dict(fe="FE",inspections="FEI",maintenance="FEM",capa="FECA",drills="FD",training="FST",fsmr="FSMR")
REQUIRED={"fe":HEAD[:4],"inspections":["FE #","Inspection Date","Inspector","Inspection Result"]+HEAD[6:14],"maintenance":["Work Order","Assigned To","Target Date","Status"],"capa":["Deficiency","Status"],"training":["Training Title","Training Date"],"drills":["Drill Title","Drill Date"],"incidents":["Incident","Incident Date"]}
def writable(role):
    if role==ROLES[0]: return list(FIELDS)
    if role in ROLES[4:6]: return [k for k in FIELDS if k!="settings"]
    return {ROLES[6]:["maintenance"],ROLES[7]:["incidents","emergency"],ROLES[8]:["training","drills","incidents"]}.get(role,[])

