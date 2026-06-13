
import yaml
from utils.path_tool import get_abs_path

def load_rag_config(config_path: str = get_abs_path("config/rag.yml"),encoding:str = "utf-8"):
    with open(config_path, "r",encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)

def load_chroma_config(config_path: str = get_abs_path("config/chroma.yml"),encoding:str = "utf-8"):
    with open(config_path, "r",encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)

def load_prompts_config(config_path: str = get_abs_path("config/prompts.yml"),encoding:str = "utf-8"):
    with open(config_path, "r",encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)

def load_agent_config(config_path: str = get_abs_path("config/agent.yml"),encoding:str = "utf-8"):
    with open(config_path, "r",encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)

rag_conf = load_rag_config()
chroma_conf = load_chroma_config()
prompts_conf = load_prompts_config()
agent_conf = load_agent_config()

if __name__ == '__main__':
    print(agent_conf)



"""
此文件创建了4个函数用于加载不同功能所需要的配置项
分4个对象调用4个方法，方便后续调用（只需要调用对象即可获得其中的配置）
返回的数据类型为字典，使用时直接对象+【所需字段】
"""
