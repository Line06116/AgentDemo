import os,hashlib
from utils.logger_handler import logger
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader,TextLoader
#获取文件的md5的十六进制字符串
def get_file_md5_hex(filepath:str):
    if not os.path.exists(filepath):
        logger.error(f"[md5计算]文件{filepath}不存在]")
        return
    if not os.path.isfile(filepath):
        logger.error(f"[md5计算]路径{filepath}不是文件]")
        return
    md5_obj = hashlib.md5()

    chunk_size = 4096       #4kb,避免文件过大
    try:
        with open(filepath,"rb") as f:  #以二进制方式只读文件
            while chunk :=f.read(chunk_size):       #:= 先赋值再使用
                md5_obj.update(chunk)

            md5_hex = md5_obj.hexdigest()       #hexdigest() 返回md5的十六进制字符串
            return md5_hex
    except Exception as e:
        logger.error(f"计算文件{filepath}md5失败,错误信息:{str(e)}")
        return None

#返回文件夹内的文件列表
def list_with_allowed_type(path:str,allowed_types:tuple[str]):
    files = []

    if not os.path.isdir(path):     #判断是否是文件夹
        logger.error(f"[listdir_with_allowed_type]{path}不是文件夹")
        return allowed_types
    for f in os.listdir(path):
        if f.endswith(allowed_types):          #判断文件类型
            files.append(os.path.join(path,f))

    return tuple(files)     #tuple类型不可变，防止误修改



def pdf_loader(filepath: str,password = None) -> list[Document]:
    return PyPDFLoader(filepath,password).load()


def txt_loader(filepath: str) -> list[Document]:
    return TextLoader(filepath,encoding="utf-8").load()



"""
定义get_file_md5_hex(filepath:str)方法，传入一个文件路径，先判断是否存在及是否为文件，
随后调用hashlib中的md5（）方法，创建MD5对象，用于后续转化字符串

按照实现定义好的chunk_size大小，分段存入MD5对象中，避免内存过大
"""


