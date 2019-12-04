import json
from ast import literal_eval
import rdflib
from rdflib.plugins.sparql import *
import re
import yaml
import copy


def fromSPARQLtoMapping(mapping, query, parsedQuery):
    uris = getUrisFromQuery(parsedQuery)
    print('\n\n\n**********URIS*********\n\n\n')
    print(str(uris).replace('\'', '"') + '\n\n\n')
    testUris = {}
#    find_triples_in_query(prepareQuery(query).algebra, testUris)
    translatedMapping = simplifyMappingAccordingToQuery(uris,mapping)
    csvColumns = findCsvColumnsInsideTheMapping(translatedMapping)
    print('\n\n\n************NEW MAPPING********\n\n\n' + str(translatedMapping).replace('\'', '"') + '\n\n\n')
    print('\n\nCSVCOLUMNS:\n' + str(csvColumns) + '\n\n\n')
    return csvColumns, translatedMapping

def getUrisFromQuery(query):
    result = []
    for el in query['where']:
        for tm in el['triples']:
            uri = tm['predicate']['value']
            if uri == 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type':
                uri = tm['object']['value']
            result.append(uri)
            '''
            subject  = tm['subject']['value']
            if subject not in result.keys():
                result[subject] = {'predicates':[], 'types':[]}
            '''
    return result

def find_triples_in_query(algebra, uris):
    for node in algebra:
        if 'triples' in node:
            for tp in algebra['triples']:
                obtainURISfromTP(tp, uris)
        elif isinstance(algebra[node], dict) and bool(algebra[node].keys()):
            find_triples_in_query(algebra[node], uris)


def obtainURISfromTP(tp, uris):#Simplificable
    if str(tp[0]) not in uris.keys():
        uris[str(tp[0])] = {"predicates": [], "types": []}
    for value in tp:
        if re.match(".*URIRef.*", str(type(value))):
            if str(value) == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type":
                uris[str(tp[0])]["types"].append(str(tp[2]))
            elif str(tp[1]) != "http://www.w3.org/1999/02/22-rdf-syntax-ns#type" and value == tp[1]:
                uris[str(tp[0])]["predicates"].append(str(value))

def simplifyMappingAccordingToQuery(uris, minMapping):
    mapping = substitutePrefixes(minMapping)
    newMapping = {'prefixes':mapping['prefixes'], 'mappings':{}}
    for tm in mapping['mappings']:
        for po in mapping['mappings'][tm]['po']:
            if(type(po) is list):
                if(isPoInUris(po, uris)):
                    if(tm not in newMapping['mappings'].keys()):
                        newMapping['mappings'][tm] = {
                                'sources':mapping['mappings'][tm]['sources'],
                                's':mapping['mappings'][tm]['s'],
                                'po':[]
                                }
                    newMapping['mappings'][tm]['po'].append(po)
            else:
                if(isPoInUris([po['p']], uris)):
                    if(tm not in newMapping['mappings'].keys()):
                        newMapping['mappings'][tm] = {
                            'sources':mapping['mappings'][tm]['sources'],
                            's':mapping['mappings'][tm]['s'],
                            'po':[]
                            }

                    newMapping['mappings'][tm]['po'].append(po)
    newMapping = removeUnnecesaryTM(newMapping)
    newMapping  = addReferencesOfTheJoins(mapping, newMapping)
    return newMapping

def addReferencesOfTheJoins(oldMapping, mapping):
    newMapping = mapping.copy()
    for tm in mapping['mappings']:
        for po in mapping['mappings'][tm]['po']:
            if type(po) is dict:
                for o in po['o']:
                    newMapping = checkIfReferenceIsDefined(mapping, newMapping, o)
    return newMapping

def checkIfReferenceIsDefined(mapping, newMapping, o):
    joinReferences = getJoinReferences(o)
    print('\n\nJoin: \n' + str(o))
    print('\n\nJOIN REFERENCES: ' + str(joinReferences))
    if joinReferences['outerRef'] not in getColPatterns(newMapping['mappings'][o['mapping']]):
        for i,po in enumerate(mapping['mappings'][o['mapping']]['po']):
            if(joinReferences['outerRef'] in getColPatterns(po)):
                print('Hay que añadir a: \n' + str(po)) 
                newMapping['mappings'][o['mapping']]['po'].append(po)
    return newMapping

def getJoinReferences(join):
    result = {'innerRef': join['condition']['parameters'][1][1], 'outerRef':join['condition']['parameters'][0][1]}
    return result
def removeUnnecesaryTM(mapping):
    tripleMaps = mapping['mappings'].keys()
    newMapping = mapping.copy()
    for tm in mapping['mappings']:
        for i,po in enumerate(mapping['mappings'][tm]['po']):
            if(type(po) is dict):
                for j,o in enumerate(po['o']):
                    if(o['mapping'] not in tripleMaps):                             
                        del newMapping['mappings'][tm]['po'][i]['o'][j]
                if (len(newMapping['mappings'][tm]['po'][i]['o']) == 0):
                    del newMapping['mappings'][tm]['po'][i]
    newMapping = removeEmptyTM(newMapping)
    return newMapping

def removeEmptyTM(mapping):
    newMapping = mapping.copy()
    tmToRemove = []
    types = [ po[1] 
            for tm in mapping['mappings']
            for po in mapping['mappings'][tm]['po']
            if (type(po) is list and po[0] == 'a')]
    for tm in mapping['mappings']:
        if(len(mapping['mappings'][tm]['po']) == 1 and 
            mapping['mappings'][tm]['po'][0][0] == 'a'
            and types.count(mapping['mappings'][tm]['po'][0][1]) > 1):
            types.pop(types.index(mapping['mappings'][tm]['po'][0][1]))
            tmToRemove.append(tm)
    for tm in tmToRemove:
        del newMapping['mappings'][tm]
    return newMapping

def findCsvColumnsInsideTheMapping(mapping):
    columns = {}
    for tm in mapping['mappings']:
        columns[tm] = {
                'source':str(mapping['mappings'][tm]['sources'][0]).split('/')[-1:][0].split('~')[0],
                'columns':[]
                }
        columns[tm]['columns'].extend(cleanColPattern(mapping['mappings'][tm]['s']))
        for po in mapping['mappings'][tm]['po']:
            if(type(po) is dict):
                for o in po['o']:
                    references = getJoinReferences(o)
                    colReference = cleanColPattern(references['innerRef'] )
                    if(not bool(set(colReference)& set(columns[tm]['columns']))):
                        columns[tm]['columns'].extend(cleanColPattern(references['innerRef']))
            else:
                matches = cleanColPattern(po)
                columns[tm]['columns'].extend(matches)
    return columns

def getColPatterns(element): 
    colPattern  = '(\$\((?!\$\(\)).\))'
    result = []
    matches = re.findall(colPattern, str(element))
    result.extend(matches)
    return result

def cleanColPattern(columns):
    columns = getColPatterns(columns)
    print('COLUMNS:' + str(columns))
    result = []
    for col in columns:
        result.append(str(col)[2:-1])
    return result

def isPoInUris(po, uris):
    for item in po:
        if item in uris:
            return True
    return False
def getRelevantTM(uris, mapping):#Simplificable
    mapping = substitutePrefixes(mapping)
    #print('\n\n\n\n********************************************MAPPING***************************************\n\n\n\n' + str(mapping).replace('\'', '"') + '\n\n\n\n')
    relevantTM = {}
    csvColumns = {}
    parentcolumns = {}
    for subject in uris:
        lensubject = len(uris[subject]["predicates"]) + len(uris[subject]["types"])
        predicates = uris[subject]["predicates"]
        types = uris[subject]["types"]
        for tm in mapping["mappings"]:
            pomcount = 0
            equals = 0
            relevantpos = []
            columns = []
            for pom in mapping["mappings"][tm]["po"]:
                if 'p' in pom:
                    if mapping["mappings"][tm]["po"][pomcount]["p"] in predicates:
                        equals += 1
                        relevantpos.append(pomcount)
                        aux, auxparentcolumns, parent = getColumnsfromJoin(mapping["mappings"][tm]["po"][pomcount]["o"])
                        parentcolumns[parent] = auxparentcolumns
                        columns.extend(aux)
                elif mapping["mappings"][tm]["po"][pomcount][0] in predicates:
                    equals += 1
                    relevantpos.append(pomcount)
                    columns.extend(getColumnsfromOM(mapping["mappings"][tm]["po"][pomcount][1]))
                elif mapping["mappings"][tm]["po"][pomcount][0] == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type":
                    if mapping["mappings"][tm]["po"][pomcount][1] in types:
                        equals += 1
                        relevantpos.append(pomcount)
                pomcount += 1
            if lensubject == equals:
                source = re.sub("~csv", "", mapping["mappings"][tm]["sources"][0][0].split("/")[
                    len(mapping["mappings"][tm]["sources"][0][0].split("/")) - 1])
                columns.extend(getColumnsfromOM(mapping["mappings"][tm]["s"]))
                columns = list(dict.fromkeys(columns))
                relevantTM[tm] = relevantpos
                csvColumns[tm] = {"source": source, "columns": columns}
                break

    for parent in parentcolumns:
        for tm in csvColumns:
            if parent in csvColumns[tm]:
                csvColumns[tm]["columns"].extend(parentcolumns[parent])
                csvColumns[tm]["columns"] = list(dict.fromkeys(csvColumns["columns"][parent]))

    mappingcopy = copy.deepcopy(mapping["mappings"])
    for tm in mappingcopy:
        if tm not in relevantTM:
            del mapping["mappings"][tm]
        else:
            pomcount = 0
            while pomcount < len(mapping["mappings"][tm]["po"]):
                if pomcount not in relevantTM[tm]:
                    del mapping["mappings"][tm]["po"][pomcount]
                    count = 0
                    for x in relevantTM[tm]:
                        if x >= pomcount:
                            relevantTM[tm][count] = x - 1
                        count += 1
                else:
                    pomcount += 1

    return mapping, csvColumns


def getColumnsfromOM(om):
    columns = []
    aux = om.split("$(")
    for references in aux:
        if re.match(".*\\).*", references):
            columns.append(references.split(")")[0])
    return columns


def getColumnsfromJoin(join):
    columns = []
    joinscount = 0
    while joinscount < len(join):
        for i in [0, 1]:
            if join[joinscount]["condition"]["parameters"][i][0] == "str1":
                columns.extend(getColumnsfromOM(join[joinscount]["condition"]["parameters"][i][1]))
            else:
                parentColumns = getColumnsfromOM(join[joinscount]["condition"]["parameters"][i][1])
                parent = join[joinscount]["mapping"]
        joinscount += 1
    return columns, parentColumns, parent


def substitutePrefixes(mapping):
    prefixes = mapping["prefixes"]
    strMapping = str(mapping['mappings'])
    for prefix in prefixes:
        strMapping = strMapping.replace('\'' + prefix + ':', '\'' + prefixes[prefix])
#    strMapping = strMapping.replace('\'','"')
    expandedMapping  = literal_eval(strMapping)
    newMapping = {'prefixes':prefixes,'mappings':dict(expandedMapping)}
    return newMapping
    '''
    for tm in mapping["mappings"]:
        pomcount = 0
        for pom in mapping["mappings"][tm]["po"]:
            if 'p' in pom:
                value = mapping["mappings"][tm]["po"][pomcount]["p"]
                join = True
            else:
                value = mapping["mappings"][tm]["po"][pomcount][0]
                join = False
            if re.match(".*:.*", value):
                aux = atomicprefixsubtitution(prefixes, value)
                if join:
                    mapping["mappings"][tm]["po"][pomcount]["p"] = aux[0] + aux[1]
                else:
                    mapping["mappings"][tm]["po"][pomcount][0] = aux[0] + aux[1]
            elif "a" == value:
                mapping["mappings"][tm]["po"][pomcount][0] = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
                aux = atomicprefixsubtitution(prefixes, mapping["mappings"][tm]["po"][pomcount][1])
                mapping["mappings"][tm]["po"][pomcount][1] = aux[0] + aux[1]
            pomcount += 1
    '''


def atomicprefixsubtitution(prefixes, value):
    aux = value.split(":")
    for prefix in prefixes.keys():
        if aux[0] == prefix:
            aux[0] = prefixes[prefix]
            break
    return aux


def getColumnsFromFunctions(csvColumns, functions):
    for tm in functions:
        if(tm in csvColumns.keys()):
            for csv in csvColumns:
                sourceColumns = csvColumns[tm]["columns"]
                for column in sourceColumns:
                    if column in functions[tm]:
                        columns = []
                        extractReferencesFromFno(functions[tm][column], columns)
                        csvColumns[tm]["columns"].remove(column)
                        csvColumns[tm]["columns"].extend(columns)
                        csvColumns[tm]["columns"] = list(dict.fromkeys(csvColumns[tm]["columns"]))
    return csvColumns


def extractReferencesFromFno(functions, columns):
    if 'parameter' in functions:
        functions = functions["value"]
    for parameters in functions["parameters"]:
        if 'parameter' in parameters:
            extractReferencesFromFno(parameters, columns)
        else:
            if re.match("\\$\\(.*\\)", parameters[1]):
                columns.extend(getColumnsfromOM(parameters[1]))


# From a dict with sources a columns name, return the same dict with the indexes of the columns
def getIndexFromColumns(csvColumns, all_columns):
    print(csvColumns)
    print(all_columns)
    result = {}
    for tm in all_columns:
        result[csvColumns[tm['source']]['source']] = []
        for col in csvColumns[tm['source']]['columns']:
            result[csvColumns[tm['source']]['source']].append(tm['columns'].index(col))
    #
    # for tm in csvColumns:
    #    columns = csvColumns[tm]["columns"]
    #    source = csvColumns[tm]["source"]
    #    aux = []
    #    for file in all_columns:
    #        if file["source"] == source:
    #
    #            for column in columns:
    #                aux.extend(file["columns"].index(column))
    #    csvColumns[tm][columns] = aux
    return result
