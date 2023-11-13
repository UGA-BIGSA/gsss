"""
Command: ```python3 parseqsf.py {gsss_questions.txt} {blank_survey.qsf} {out.qsf}```

To use, make a new survey in Qualtrics, name it whatever you want, then go to Tools > Import/Export > Export Survey. 
This should download a file with a .qsf extension. Use the path to that as input for this program (blank_survey.qsf above) as well as the .txt file where we've been writing our survey questions.
This program will parse those questions and write them in a .qsf format (which is really just a JSON file with specific structure).
If you don't specify an output file path (third arg) it will make a new file replacing the .txt with .qsf in the questions input.

Update: switched the order of questions and blank_qsf & made it so that blank_qsf is not required.

"""
import os
import sys
import json

#olivers_utils functions
from functools import reduce
from operator import getitem

def getdict(dictionary, map_list):
    return reduce(getitem, map_list, dictionary)
    
def setdict(dictionary, map_list, value):
    if type(map_list) is str: map_list = [map_list]
    try:
        getdict(dictionary, map_list[:-1])[map_list[-1]] = value
    except:
        if(len(map_list) > 1): 
            setdict(dictionary, map_list[:-1],{})
            setdict(dictionary, map_list, value)
        else:
            raise Exception

#Program

class Survey:
    def __init__(self, qsf, input_questions, keep_questions = False):
        self.qsf = qsf
        for item in self.qsf["SurveyEntry"]:
            name = item.replace("Survey","")
            self.__dict__[name] = self.qsf["SurveyEntry"][item]
        self.elements = getdict(self.qsf,["SurveyElements"])
        self.blocks = self.Blocks(self)
        self.flow = self.Flow(self)
        self.count = self.Question_Count(self)
        if not keep_questions:
            self.blocks.empty()
            self.count.empty()
            self.flow.empty()
            self.questions = []
        else: self.questions = [element for element in self.elements if element["Element"] == "SQ"]
        setdict(self.qsf,["SurveyElements"],[element for element in self.elements if element["Element"] != "SQ"])
        self.elements = getdict(self.qsf,["SurveyElements"])

        with open(input_questions,"r") as input:
            text = input.read()
            text = "\n".join([line.strip() for line in text.split("\n") if not line.strip()[:2] == "#?"])

        text = text.split("[[Block:")[1:]
        for block in text:
            self.blocks.add_block(block)

        self.blocks.extract()
        self.count.extract()
        self.flow.extract()
        for x in range(len(self.questions)):
            if isinstance(self.questions[x],self.Question):
                self.questions[x] = self.questions[x].extract()

    class Blocks:
        def __init__(self, survey):
            self.survey = survey
            abbrev = "BL"
            self.index = self.survey.elements.index([element for element in self.survey.elements if element["Element"] == abbrev][0])
            self.__dict__.update(self.survey.elements[self.index])
        
        def empty(self):
            trash = [block for block in self.Payload if block["Type"] == "Trash"]
            self.Payload = {}
            if len(trash) > 0:
                self.Payload["0"] = trash[0]

        def add_block(self, block_text):
            name = block_text.split("]]")[0].strip()
            info = [self.Payload[blindex] for blindex in self.Payload if self.Payload[blindex]["Description"] == name]
            if len(info) > 0: info = info[0]
            else: info = {
                "Description":name,
                "Type":"Standard",
                "BlockElements":[]
            }
            description = block_text.split("]]")[1].split("[[")[0].strip()
            if description: pass#add description later
            strindex = str(len(self.Payload))
            if not "ID" in info:
                info["ID"] = f'BL_{"".join(["0" for x in range(15-len(strindex))])}{len(self.Payload)}'

            try: 
                block_text = block_text.replace("[[PageBreak]]","[[Question:PageBreak]]").split("[[Question:")[1:]
            except:
                info.pop("BlockElements")
                self.Payload.insert(-1,info)
                return

            for question in block_text:
                question = self.survey.Question(self.survey,question)
                info["BlockElements"].append(question.block_info)

            self.Payload[strindex] = info
            self.survey.flow.add_block(info)
            

        def extract(self):
            index = self.__dict__.pop("index")
            self.__dict__.pop("survey").elements[index] = self.__dict__

    class Flow:
        def __init__(self, survey):
            self.survey = survey
            abbrev = "FL"
            self.index = self.survey.elements.index([element for element in self.survey.elements if element["Element"] == abbrev][0])
            self.__dict__.update(self.survey.elements[self.index])
        
        def empty(self):
            self.Payload["Flow"] = []
            self.Payload["Properties"]["Count"] = 1

        def add_block(self, block):
            self.Payload["Flow"].append({
                "ID": block["ID"],
                "Type": "Block",
                "FlowID": f"FL_{int(block['ID'].split('_')[-1])+1}"
            })
            self.Payload["Properties"]["Count"] += 1
            

        def extract(self):
            index = self.__dict__.pop("index")
            self.__dict__.pop("survey").elements[index] = self.__dict__

    class Question_Count:
        def __init__(self, survey):
            self.survey = survey
            abbrev = "QC"
            self.index = self.survey.elements.index([element for element in self.survey.elements if element["Element"] == abbrev][0])
            self.__dict__.update(self.survey.elements[self.index])
        
        def empty(self):
            self.SecondaryAttribute = 0

        def plus(self):
            self.SecondaryAttribute += 1
            return self.SecondaryAttribute

        def extract(self):
            index = self.__dict__.pop("index")
            self.SecondaryAttribute = str(self.SecondaryAttribute)
            self.__dict__.pop("survey").elements[index] = self.__dict__

    class Question:
        def __init__(self, survey,question_text):
            self.survey = survey
            question_types = question_text.split("]]")[0].split(":")
            if question_types[0] == "PageBreak":
                self.block_info = {"Type": "Page Break"}
                return
            qtype = {"MC":"MC","TE":"TE","CS":"CS","ConstantSum":"CS","Slider":"Slider","Text":"DB","Matrix":"Matrix"}[question_types[0]]

            self.count = survey.count.plus()
            self.name = question_text.split("\n")[1].strip()
            selectors = {
                "MC": {True:"M",False:"S"}["MultipleAnswer" in question_types] + "A" + {True:"H",False:"V"}["Horizontal" in question_types] + "R",
                "TE": {True:"SL",False:"ML"}["Short" in question_types],
                "Matrix":"Likert",
                "Slider":"HSLIDER",
                "CS":"VRTL",
                "DB":"TB"
            }
            configurations = {
                "MC":{"QuestionDescriptionOption": "UseText"},
                "TE":{"QuestionDescriptionOption": "UseText"},
                "Matrix":{
                    "QuestionDescriptionOption": "UseText",
                    "TextPosition": "inline",
                    "ChoiceColumnWidth": 25,
                    "RepeatHeaders": "none",
                    "WhiteSpace": "OFF",
                    "MobileFirst": True
                    },
                "Slider":{
                    "QuestionDescriptionOption": "UseText",
                    "CSSliderMin": 0,
                    "CSSliderMax": 100,
                    "GridLines": 10,
                    "SnapToGrid": False,
                    "NumDecimals": "0",
                    "ShowValue": True,
                    "CustomStart": False,
                    "NotApplicable": False,
                    "MobileFirst": True
                },
                "CS":{"QuestionDescriptionOption": "UseText"},
                "DB":{"QuestionDescriptionOption": "UseText"}
            }

            self.info = {
                "SurveyID":survey.ID,
                "Element":"SQ",
                "PrimaryAttribute":f"QID{self.count}",
                "SecondaryAttribute":self.name,
                "TertiaryAttribute":None,
                "Payload":{
                    "QuestionText":f"{self.name}<br>",
                    "DataExportTag":f"Q{self.count}",
                    "QuestionType":qtype,
                    "Selector":selectors[qtype],
                    "Configuration": configurations[qtype],
                    "QuestionDescription":self.name,
                    "Validation": {
                        "Settings": {
                            "ForceResponse": "OFF",
                            "Type": "None"
                        }
                    },
                    "Language": [],
                    "NextChoiceId": 4,
                    "NextAnswerId": 1,
                    "QuestionID":f"QID{self.count}"
                }
            }
            Payload = getdict(self.info,["Payload"])
            if qtype == "DB":
                text = "<br>".join([line.strip() for line in question_text.split("\n")[1:]])
                Payload["QuestionText"] = text
        
            if qtype == "CS" or qtype == "MC": Payload["SubSelector"] = "TX"
            elif qtype == "Matrix": Payload["SubSelector"] = "SingleAnswer"

            if len({"MC","MultipleAnswer"}.intersection(set(question_types))) == 2:
                Payload["QuestionText"] = "(Choose all that apply) " + Payload["QuestionText"]

            if "[[Choices]]" in question_text:
                choices = [choice.strip() for choice in question_text.split("[[Choices]]")[1].split("[[")[0].split("\n") if choice.strip()]
                choice_dict = {}
                orders = []
                for x in range(len(choices)):
                    choice_dict[str(x+1)] = {"Display":choices[x]}
                    if choices[x].strip().lower() == "other (specify below)":
                        choice_dict[str(x+1)].update({"TextEntry": "true","TextEntrySize": "Small"})
                    orders.append(str(x+1))
                Payload["Choices"] = choice_dict
                Payload["ChoiceOrder"] = orders

            if "[[Answers]]" in question_text:
                answers = [answer.strip() for answer in question_text.split("[[Answers]]")[1].split("[[")[0].split("\n") if answer.strip()]
                answer_dict = {}
                orders = []
                for x in range(len(answers)):
                    answer_dict[str(x+1)] = {"Display":answers[x]}
                    orders.append(str(x+1))
                Payload["Answers"] = answer_dict
                Payload["AnswerOrder"] = orders

            self.block_info = {
                "Type":"Question",
                "QuestionID":self.info["PrimaryAttribute"]
            }
            self.survey.elements.append(self.info)

        def extract(self):
            return self.info        


def main(input_questions, blank_qsf=False, out_qsf = False):
    if blank_qsf:
        blank_qsf = os.path.expanduser(blank_qsf)
        with open(blank_qsf,"r") as input:
            blank_qsf = json.load(input)
    else:
        blank_qsf = json.loads('''{"SurveyEntry":{"SurveyID":"SV_8uYCLiVlYVfp0Ee","SurveyName":"empty survey","SurveyDescription":null,"SurveyOwnerID":"UR_82hSeBo3AjuxM5U","SurveyBrandID":"ugeorgia","DivisionID":"DV_42V8qKI9A0TWwfj","SurveyLanguage":"EN","SurveyActiveResponseSet":"RS_5b4MXbkTJ9ytYmG","SurveyStatus":"Inactive","SurveyStartDate":"0000-00-00 00:00:00","SurveyExpirationDate":"0000-00-00 00:00:00","SurveyCreationDate":"2023-09-05 13:33:48","CreatorID":"UR_82hSeBo3AjuxM5U","LastModified":"2023-09-05 13:33:52","LastAccessed":"0000-00-00 00:00:00","LastActivated":"0000-00-00 00:00:00","Deleted":null},"SurveyElements":[{"SurveyID":"SV_8uYCLiVlYVfp0Ee","Element":"BL","PrimaryAttribute":"Survey Blocks","SecondaryAttribute":null,"TertiaryAttribute":null,"Payload":[{"Type":"Default","Description":"Default Question Block","ID":"BL_difdaPHqcsix9TU","BlockElements":[{"Type":"Question","QuestionID":"QID1"}]},{"Type":"Trash","Description":"Trash \/ Unused Questions","ID":"BL_2cbDhi6RmHXbnF4"}]},{"SurveyID":"SV_8uYCLiVlYVfp0Ee","Element":"FL","PrimaryAttribute":"Survey Flow","SecondaryAttribute":null,"TertiaryAttribute":null,"Payload":{"Flow":[{"ID":"BL_difdaPHqcsix9TU","Type":"Block","FlowID":"FL_2"}],"Properties":{"Count":2},"FlowID":"FL_1","Type":"Root"}},{"SurveyID":"SV_8uYCLiVlYVfp0Ee","Element":"PL","PrimaryAttribute":"Preview Link","SecondaryAttribute":null,"TertiaryAttribute":null,"Payload":{"PreviewType":"Brand","PreviewID":"d49ee847-c5fd-4bdd-bba8-ae2e1dc499de"}},{"SurveyID":"SV_8uYCLiVlYVfp0Ee","Element":"SO","PrimaryAttribute":"Survey Options","SecondaryAttribute":null,"TertiaryAttribute":null,"Payload":{"BackButton":"false","SaveAndContinue":"true","SurveyProtection":"PublicSurvey","BallotBoxStuffingPrevention":"false","NoIndex":"Yes","SecureResponseFiles":"true","SurveyExpiration":"None","SurveyTermination":"DefaultMessage","Header":"","Footer":"","ProgressBarDisplay":"None","PartialData":"+1 week","ValidationMessage":"","PreviousButton":"","NextButton":"","SurveyTitle":"Qualtrics Survey | Qualtrics Experience Management","SkinLibrary":"ugeorgia","SkinType":"MQ","Skin":"skin1_new","NewScoring":1,"SurveyMetaDescription":"The most powerful, simple and trusted way to gather experience data. Start your journey to experience management and try a free account today."}},{"SurveyID":"SV_8uYCLiVlYVfp0Ee","Element":"SCO","PrimaryAttribute":"Scoring","SecondaryAttribute":null,"TertiaryAttribute":null,"Payload":{"ScoringCategories":[],"ScoringCategoryGroups":[],"ScoringSummaryCategory":null,"ScoringSummaryAfterQuestions":0,"ScoringSummaryAfterSurvey":0,"DefaultScoringCategory":null,"AutoScoringCategory":null}},{"SurveyID":"SV_8uYCLiVlYVfp0Ee","Element":"PROJ","PrimaryAttribute":"CORE","SecondaryAttribute":null,"TertiaryAttribute":"1.1.0","Payload":{"ProjectCategory":"CORE","SchemaVersion":"1.1.0"}},{"SurveyID":"SV_8uYCLiVlYVfp0Ee","Element":"STAT","PrimaryAttribute":"Survey Statistics","SecondaryAttribute":null,"TertiaryAttribute":null,"Payload":{"MobileCompatible":true,"ID":"Survey Statistics"}},{"SurveyID":"SV_8uYCLiVlYVfp0Ee","Element":"QC","PrimaryAttribute":"Survey Question Count","SecondaryAttribute":"1","TertiaryAttribute":null,"Payload":null},{"SurveyID":"SV_8uYCLiVlYVfp0Ee","Element":"SQ","PrimaryAttribute":"QID1","SecondaryAttribute":"Click to write the question text","TertiaryAttribute":null,"Payload":{"QuestionText":"Click to write the question text","DataExportTag":"Q1","QuestionType":"MC","Selector":"SAVR","SubSelector":"TX","Configuration":{"QuestionDescriptionOption":"UseText"},"QuestionDescription":"Click to write the question text","Choices":{"1":{"Display":"Click to write Choice 1"},"2":{"Display":"Click to write Choice 2"},"3":{"Display":"Click to write Choice 3"}},"ChoiceOrder":["1","2","3"],"Validation":{"Settings":{"ForceResponse":"OFF","Type":"None"}},"Language":[],"NextChoiceId":4,"NextAnswerId":1,"QuestionID":"QID1"}},{"SurveyID":"SV_8uYCLiVlYVfp0Ee","Element":"RS","PrimaryAttribute":"RS_5b4MXbkTJ9ytYmG","SecondaryAttribute":"Default Response Set","TertiaryAttribute":null,"Payload":null}]}''')
    input_questions = os.path.expanduser(input_questions)
    if not out_qsf: out_qsf = input_questions.replace(".txt",".qsf")
    else: out_qsf = os.path.expanduser(out_qsf)
    
    survey = Survey(blank_qsf, input_questions, False)

    with open(out_qsf,"w") as output:
        json.dump(survey.qsf, output)


if __name__ == "__main__":
    main(*sys.argv[1:])