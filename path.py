import os
from pathlib import Path

from loguru import logger


class PathOperator:
    def __init__(self):
        temp = str(os.path.abspath(__file__))
        # logger.info(f"dir {temp}")
        temp = temp[0:temp.rindex(os.sep)]
        if temp.endswith("_internal"):
            temp = temp[0:temp.rindex(os.sep)]
        self.root_dir_path = temp

        # self.image_path = self.root_dir_path + os.sep + 'img'
        # if not os.path.exists(self.image_path):
        #     os.makedirs(self.image_path)

        # for f in os.listdir(self.image_path):
        #     if f.endswith('jpg'):
        #         os.remove(self.image_path + os.sep + f)

    def ensure_parent_dir(self,pathname: str):
        """
        给定一个完整的文件路径 pathname，
        如果它的父目录不存在，就自动创建。
        """
        p = Path(pathname)
        parent = p.parent
        if parent:
            # parents=True：创建所有父级目录； exist_ok=True：已存在时不报错
            parent.mkdir(parents=True, exist_ok=True)

PATH = PathOperator()