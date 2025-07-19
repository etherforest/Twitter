import os

from path import PATH



from jproperties import Properties

prop = Properties()


def getProps(pathname) -> dict:
    prop.clear()
    with open(pathname, 'rb') as config_stream:
        prop.load(config_stream)
    return prop.properties

def listToMap(list: []) -> dict:
    result = {}
    for i in range(len(list)):
        result[list[i]] = list[i]
    return result

def listToMapWithSep(list: [],sep:str=":") -> dict:
    result = {}
    for i in range(len(list)):
        split = list[i].split(sep)
        result[split[0]] =split[1]
    return result

class CommonConfig:
    def __init__(self,activation_code):
        self.activation_code = activation_code

class CommonParser(object):
    def __init__(self):
        pass

    def parse(self)->CommonConfig:
        activation_code = None
        for k, v in getProps(PATH.root_dir_path + os.sep + 'common.properties').items():
            value = str(v).replace(" ", "")
            k = str(k).replace(" ", "")
            if not value or value == None or value == '':
                continue
            if 'activation_code'.__eq__(k):
                activation_code = value
        return CommonConfig(activation_code)

