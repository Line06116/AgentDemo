from langchain_core.tools import tool
from rag.rag_service import RagSummarizeService
import random
import requests
from utils.config_handler import agent_conf
from utils.path_tool import get_abs_path
from utils.logger_handler import logger

rag = RagSummarizeService()
user_ids = ["1001","1002","1003","1004","1005","1006","1007","1008","1009","1010"]
month_arr = ["2025-01","2025-02","2025-03","2025-04","2025-05","2025-06","2025-07","2025-08","2025-09","2025-10","2025-11","2025-12"]

external_data = {}


@tool(description="从向量存储中检索资料")
def rag_summarize(query: str) -> str:
    return rag.rag_summarize(query)

def get_city_adcode(city: str) -> str:
    """获取城市编码"""
    api_key = agent_conf["weather_api"]
    if not api_key:
        logger.warning("未配置高德地图API密钥，使用模拟数据")
        return None

    url = "https://restapi.amap.com/v3/geocode/geo"
    params = {
        "address": city,
        "key": api_key
    }

    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        if data["status"] == "1" and data["geocodes"]:
            return data["geocodes"][0]["adcode"]
        else:
            logger.warning(f"未能获取城市{city}的编码")
            return None
    except Exception as e:
        logger.error(f"获取城市编码失败: {str(e)}")
        return None


def fetch_real_weather(city: str) -> str:
    """获取真实天气数据"""
    api_key = agent_conf["weather_api"]

    if not api_key:
        logger.warning("未配置高德地图API密钥，返回模拟数据")
        return f"城市{city}天气为阴天，气温26摄氏度，空气湿度50%，南风二级，AQI21，最近6小时有降雨概率"

    adcode = get_city_adcode(city)
    if not adcode:
        return f"无法获取城市{city}的天气信息"

    url = "https://restapi.amap.com/v3/weather/weatherInfo"
    params = {
        "city": adcode,
        "key": api_key,
        "extensions": "all"
    }

    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        if data["status"] == "1" and data["forecasts"]:
            forecast = data["forecasts"][0]
            casts = forecast["casts"][0]

            weather_info = (
                f"城市{city}天气信息：\n"
                f"- 日期：{casts['date']}\n"
                f"- 白天天气：{casts['dayweather']}\n"
                f"- 夜间天气：{casts['nightweather']}\n"
                f"- 白天温度：{casts['daytemp']}°C\n"
                f"- 夜间温度：{casts['nighttemp']}°C\n"
                f"- 白天风向：{casts['daywind']}\n"
                f"- 白天风力：{casts['daypower']}\n"
                f"- 夜间风向：{casts['nightwind']}\n"
                f"- 夜间风力：{casts['nightpower']}"
            )
            logger.info(f"成功获取城市{city}的天气信息")
            return weather_info
        else:
            logger.warning(f"获取城市{city}天气数据失败")
            return f"无法获取城市{city}的天气信息"

    except requests.exceptions.Timeout:
        logger.error(f"获取天气信息超时")
        return "获取天气信息超时，请稍后重试"
    except requests.exceptions.RequestException as e:
        logger.error(f"获取天气信息失败: {str(e)}")
        return f"获取天气信息失败：{str(e)}"


@tool(description="获取指定城市天气信息，并以消息字符串的方式返回")
def get_weather(city: str) -> str:
    return fetch_real_weather(city)


@tool(description="获取用户ID，以字符串形式返回")
def get_user_id() -> str:
    return random.choice(user_ids)


@tool(description="获取当前月份，以纯字符串形式返回")
def get_current_month() -> str:
    return random.choice(month_arr)

def generate_external_data():
    if not external_data:
        external_data_path = get_abs_path(agent_conf["external_data_path"])
        if not external_data_path:
            raise FileNotFoundError(f"未找到外部数据文件{external_data_path}")
        with open(external_data_path,"r",encoding="utf-8") as f:
            for line in f.readlines()[1:]:
                arr: list[str] = line.strip().split(",")

                user_id = arr[0].replace('"',"")
                feature: str = arr[1].replace('"',"")
                efficiency: str = arr[2].replace('"',"")
                consumables: str = arr[3].replace('"',"")
                comparison: str = arr[4].replace('"',"")
                time: str = arr[5].replace('"',"")
                if user_id not in external_data:
                    external_data[user_id] = {}
                external_data[user_id][time] = {
                    "特征":feature,
                    "效率":efficiency,
                    "消耗品":consumables,
                    "对比":comparison,
                }

@tool(description="从外部系统中获取用户的使用记录，以字符串形式返回，如果未检索到返回空字符串")
def fetch_external_data(user_id: str,month: str) -> str:
    generate_external_data()
    try:
        return external_data[user_id][month]
    except KeyError:
        logger.warning(f"[fetch_external_data]未能检索到用户：{user_id}在{month}的使用记录")
        return ""



@tool(description="无入参，无返回值，调用后出发中间件为报告生成的场景动态注入上下文信息，为后续提示词切换提供上下文信息")
def fill_context_for_report():
    return "fill_context_for_report已调用"


if __name__ == '__main__':
    # 测试天气查询
    print(get_weather.invoke({"city": "漳州"}))
