"""Utils 使用示例。

演示如何使用 utils 包中的各种工具函数。
"""

import python_template.utils as utils
from python_template.utils import (
    ContextTimer,
    get_logger,
    read_json,
    timing_decorator,
    write_json,
)


def example_logger():
    """日志使用示例。"""
    logger = get_logger(__name__)

    logger.debug("这是一条调试信息")
    logger.info("这是一条普通信息")
    logger.warning("这是一条警告信息")
    logger.error("这是一条错误信息")


@timing_decorator
def example_timing_decorator():
    """计时装饰器示例。"""
    import time

    time.sleep(0.1)
    return "完成"


def example_context_timer():
    """上下文计时器示例。"""
    import time

    with ContextTimer("数据处理"):
        time.sleep(0.2)
        print("处理数据中...")


def example_json_operations():
    """JSON 操作示例。"""
    # 写入 JSON
    data = {
        "name": "Python Template",
        "version": "1.0.0",
        "features": ["logging", "utils", "testing"],
    }

    write_json(data, "example.json")

    # 读取 JSON
    loaded_data = read_json("example.json")
    print(f"读取的数据: {loaded_data}")

    # 安全的 JSON 操作
    json_str = '{"key": "value"}'
    parsed = utils.safe_json_loads(json_str)
    print(f"解析结果: {parsed}")


def example_file_operations():
    """文件操作示例。"""
    # 确保目录存在
    utils.ensure_directory("temp/data")

    # 写入文本文件
    utils.write_text_file("Hello, World!", "temp/data/hello.txt")

    # 读取文本文件
    content = utils.read_text_file("temp/data/hello.txt")
    print(f"文件内容: {content}")

    # 获取文件大小
    size = utils.get_file_size("temp/data/hello.txt")
    formatted_size = utils.format_file_size(size)
    print(f"文件大小: {formatted_size}")


def example_date_operations():
    """日期时间操作示例。"""
    from datetime import datetime, timedelta

    # 获取当前时间戳
    timestamp = utils.get_timestamp()
    print(f"当前时间戳: {timestamp}")

    # 获取当前日期和时间
    current_date = utils.get_current_date()
    current_time = utils.get_current_time()
    print(f"当前日期: {current_date}")
    print(f"当前时间: {current_time}")

    # 时间计算
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    print(f"明天: {utils.format_datetime(tomorrow)}")

    # 人性化时间差
    time_str = utils.humanize_timedelta(3665)  # 1小时1分5秒
    print(f"时间差: {time_str}")


def example_dict_operations():
    """字典操作示例。"""
    # 展平字典
    nested = {"a": {"b": {"c": 123}}}
    flattened = utils.flatten_dict(nested)
    print(f"展平后: {flattened}")

    # 还原字典
    unflattened = utils.unflatten_dict(flattened)
    print(f"还原后: {unflattened}")

    # 安全获取值
    value = utils.safe_get(nested, "a.b.c")
    print(f"获取的值: {value}")

    # 合并字典
    dict1 = {"a": 1, "b": 2}
    dict2 = {"b": 3, "c": 4}
    merged = utils.merge_dicts(dict1, dict2)
    print(f"合并后: {merged}")


def example_list_operations():
    """列表操作示例。"""
    # 分块处理
    data = list(range(10))
    chunks = list(utils.chunk_list(data, 3))
    print(f"分块结果: {chunks}")

    # 批量处理
    def process_batch(items):
        return [x * 2 for x in items]

    results = utils.batch_process(data, 3, process_batch)
    print(f"批量处理结果: {results}")


def example_utility_functions():
    """其他实用函数示例。"""
    # 生成 UUID
    uuid_str = utils.generate_uuid()
    print(f"UUID: {uuid_str}")

    # 清理文件名
    filename = 'invalid<>:"/\\|?*name.txt'
    sanitized = utils.sanitize_filename(filename)
    print(f"清理后的文件名: {sanitized}")


def main():
    """运行所有示例。"""
    print("=" * 50)
    print("Utils 包使用示例")
    print("=" * 50)

    print("\n1. 日志示例:")
    example_logger()

    print("\n2. 计时装饰器示例:")
    result = example_timing_decorator()
    print(f"返回值: {result}")

    print("\n3. 上下文计时器示例:")
    example_context_timer()

    print("\n4. JSON 操作示例:")
    example_json_operations()

    print("\n5. 文件操作示例:")
    example_file_operations()

    print("\n6. 日期时间操作示例:")
    example_date_operations()

    print("\n7. 字典操作示例:")
    example_dict_operations()

    print("\n8. 列表操作示例:")
    example_list_operations()

    print("\n9. 其他实用函数示例:")
    example_utility_functions()

    print("\n" + "=" * 50)
    print("所有示例运行完成!")
    print("=" * 50)


if __name__ == "__main__":
    # 设置日志
    from python_template.utils import setup_logging

    setup_logging(level="INFO")

    main()
