from utils.config_handler import  prompts_conf
from utils.logger_handler import logger
from utils.path_tool import get_abs_path


def load_system_prompt():
    """
    加载系统提示语
    :return:
    """
    try:
        system_prompt_path = get_abs_path(prompts_conf["main_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_system_prompts]在yaml配置项中没有main_prompt_path配置项")
        raise e
    try:
        return open(system_prompt_path,"r",encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_system_prompts]解析系统提示此出错，{str(e)}")
        raise e



def load_rag_prompt():
    """
    加载rag提示语
    :return:
    """
    try:
        system_prompt_path = get_abs_path(prompts_conf["rag_summarize_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_rag_prompt]在yaml配置项中没有load_rag_prompt配置项")
        raise e
    try:
        return open(system_prompt_path,"r",encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_rag_prompt]解析rag总结提示词出错，{str(e)}")
        raise e



def load_report_prompt():
    """
    加载报告提示语
    :return:
    """
    try:
        system_prompt_path = get_abs_path(prompts_conf["report_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_report_prompt]在yaml配置项中没有report_prompt_pathh配置项")
        raise e
    try:
        return open(system_prompt_path,"r",encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_report_prompt]解析报告生成提示此出错，{str(e)}")
        raise e




def load_extract_prompt(config_path: str | None = None):
    if config_path is None:
        config_path = prompts_conf["extract_prompt_path"]
    with open(get_abs_path(config_path), "r", encoding="utf-8") as f:
        return f.read()


if __name__ == '__main__':
    print(load_rag_prompt() )